import os
import time
import logging
from datetime import datetime
from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import RPCError, MessageNotModified
from urllib.parse import urlparse
import requests
import humanize
from functools import partial
import mimetypes
import subprocess
from PIL import Image

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Environment variables
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
LOG_CHANNEL = int(os.getenv("LOG_CHANNEL"))
API_BASE_URL = "https://teraboxredirect1.nkweb.workers.dev/?url="
THUMBNAIL_DIR = "thumbnails"

# Video extensions
VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.webm', '.mov', '.avi', '.wmv', '.flv', '.3gp'}

# Initialize Pyrogram client
app = Client(
    "terabox_downloader_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

def is_valid_terabox_url(url: str) -> bool:
    """Check if URL is valid TeraBox URL"""
    parsed = urlparse(url)
    return parsed.netloc.endswith(("terabox.com", "teraboxapp.com", "1024terabox.com"))

def generate_thumbnail(video_path: str) -> str:
    """Generate thumbnail from video using ffmpeg"""
    try:
        os.makedirs(THUMBNAIL_DIR, exist_ok=True)
        thumbnail_path = os.path.join(THUMBNAIL_DIR, f"thumb_{os.path.basename(video_path)}.jpg")
        
        # Use ffmpeg to extract thumbnail at 5 seconds
        cmd = [
            'ffmpeg',
            '-i', video_path,
            '-ss', '00:00:05',
            '-vframes', '1',
            '-q:v', '2',
            thumbnail_path
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Resize thumbnail to Telegram requirements
        with Image.open(thumbnail_path) as img:
            img.thumbnail((320, 320))
            img.save(thumbnail_path, "JPEG")
            
        return thumbnail_path
    except Exception as e:
        logger.error(f"Thumbnail generation failed: {e}")
        return None

def is_video_file(file_path: str) -> bool:
    """Check if file is video by extension and MIME type"""
    ext = os.path.splitext(file_path)[1].lower()
    if ext in VIDEO_EXTENSIONS:
        return True
    
    mime_type, _ = mimetypes.guess_type(file_path)
    return mime_type and mime_type.startswith('video/')

def download_file(url: str, message: Message) -> str:
    """Download file with progress tracking"""
    try:
        start_time = time.time()
        last_update = start_time
        downloaded = 0
        
        # Get filename from URL or headers
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        # Try to get filename from Content-Disposition
        filename = None
        if 'content-disposition' in response.headers:
            cd = response.headers['content-disposition']
            if 'filename=' in cd:
                filename = cd.split('filename=')[1].strip('"\'')
        
        # Fallback to URL filename
        if not filename:
            filename = url.split('/')[-1].split('?')[0] or f"video_{int(time.time())}.mp4"
        
        file_path = os.path.join("downloads", filename)
        os.makedirs("downloads", exist_ok=True)
        
        total_size = int(response.headers.get('content-length', 0))
        chunk_size = 1024 * 1024  # 1MB chunks
        
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    
                    # Update progress every 3 seconds or when done
                    current_time = time.time()
                    if current_time - last_update >= 3 or downloaded == total_size:
                        elapsed = current_time - start_time
                        percent = (downloaded / total_size) * 100
                        
                        # Calculate speed and ETA
                        speed = downloaded / elapsed if elapsed > 0 else 0
                        eta = (total_size - downloaded) / speed if speed > 0 else 0
                        
                        progress_text = (
                            f"📥 Downloading...\n"
                            f"⏳ {percent:.1f}% of {humanize.naturalsize(total_size)}\n"
                            f"🚀 {humanize.naturalsize(speed)}/s\n"
                            f"🕒 ETA: {humanize.naturaldelta(eta)}"
                        )
                        
                        try:
                            app.edit_message_text(
                                chat_id=message.chat.id,
                                message_id=message.id,
                                text=progress_text
                            )
                            last_update = current_time
                        except MessageNotModified:
                            pass
                        except RPCError as e:
                            logger.error(f"Progress update failed: {e}")
        
        return file_path
    
    except Exception as e:
        logger.error(f"Download failed: {e}")
        raise

async def upload_file(file_path: str, message: Message):
    """Upload file with proper type detection and progress"""
    try:
        file_size = os.path.getsize(file_path)
        start_time = time.time()
        last_update = start_time
        uploaded = 0
        
        # Generate thumbnail for videos
        thumbnail_path = None
        if is_video_file(file_path):
            thumbnail_path = generate_thumbnail(file_path)
        
        async def progress(current, total):
            nonlocal uploaded, last_update
            current_time = time.time()
            
            # Update every 3 seconds or when done
            if current_time - last_update >= 3 or current == total:
                elapsed = current_time - start_time
                percent = (current / total) * 100
                speed = current / elapsed if elapsed > 0 else 0
                eta = (total - current) / speed if speed > 0 else 0
                
                progress_text = (
                    f"📤 Uploading...\n"
                    f"⏳ {percent:.1f}% of {humanize.naturalsize(total)}\n"
                    f"🚀 {humanize.naturalsize(speed)}/s\n"
                    f"🕒 ETA: {humanize.naturaldelta(eta)}"
                )
                
                try:
                    await app.edit_message_text(
                        chat_id=message.chat.id,
                        message_id=message.id,
                        text=progress_text
                    )
                    last_update = current_time
                except MessageNotModified:
                    pass
                except RPCError as e:
                    logger.error(f"Progress update failed: {e}")
        
        # Upload based on file type
        if is_video_file(file_path):
            await app.send_video(
                chat_id=message.chat.id,
                video=file_path,
                thumb=thumbnail_path,
                supports_streaming=True,
                progress=progress,
                caption="🎥 Downloaded from TeraBox"
            )
        else:
            await app.send_document(
                chat_id=message.chat.id,
                document=file_path,
                thumb=thumbnail_path,
                progress=progress,
                caption="📄 Downloaded from TeraBox"
            )
    
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise
    finally:
        # Cleanup
        try:
            os.remove(file_path)
            if thumbnail_path and os.path.exists(thumbnail_path):
                os.remove(thumbnail_path)
        except OSError as e:
            logger.error(f"Cleanup failed: {e}")

@app.on_message(filters.command("tb"))
async def handle_terabox_command(client, message: Message):
    """Handle /tb command with TeraBox link"""
    # Extract URL from command
    if len(message.command) < 2:
        await message.reply_text("❌ Please provide a TeraBox URL after /tb command")
        return
    
    text = message.command[1].strip()
    
    if not is_valid_terabox_url(text):
        await message.reply_text("❌ Invalid TeraBox URL. Supported domains: terabox.com, teraboxapp.com, 1024terabox.com")
        return
    
    processing_msg = None
    try:
        processing_msg = await message.reply_text("🔍 Processing your link...")
        
        # Log to channel
        await app.send_message(
            LOG_CHANNEL,
            f"📥 New download\nUser: {message.from_user.mention}\nURL: {text}"
        )
        
        download_url = API_BASE_URL + text
        await processing_msg.edit_text("⬇️ Starting download...")
        
        file_path = download_file(download_url, processing_msg)
        await processing_msg.edit_text("⬆️ Starting upload...")
        
        await upload_file(file_path, processing_msg)
        await processing_msg.edit_text("✅ Download complete!")
        
        await app.send_message(
            LOG_CHANNEL,
            f"✅ Download completed\nUser: {message.from_user.mention}\nURL: {text}"
        )
    
    except Exception as e:
        error_msg = f"❌ Error: {str(e)}"
        try:
            if processing_msg:
                await processing_msg.edit_text(error_msg)
            else:
                await message.reply_text(error_msg)
        except:
            pass
        
        await app.send_message(
            LOG_CHANNEL,
            f"❌ Download failed\nUser: {message.from_user.mention}\nURL: {text}\nError: {str(e)}"
        )

if __name__ == "__main__":
    # Create necessary directories
    os.makedirs("downloads", exist_ok=True)
    os.makedirs(THUMBNAIL_DIR, exist_ok=True)
