from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
import aiohttp
import os
import re
import logging
from typing import Optional
import asyncio

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration (use environment variables in production)
API_ID = os.getenv("API_ID", "YOUR_API_ID")
API_HASH = os.getenv("API_HASH", "YOUR_API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN")

app = Client("terabox_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Constants
TERABOX_REGEX = re.compile(
    r'^https?:\/\/(?:www\.)?(?:[\w-]+\.)?(terabox\.com|1024terabox\.com|teraboxapp\.com|terafileshare\.com|teraboxlink\.com|terasharelink\.com)\/(s|sharing)\/[\w-]+',
    re.IGNORECASE
)
MAX_UPLOAD_SIZE_MB = 500  # Increased to 500MB
CHUNK_SIZE = 1024 * 1024 * 4  # 4MB chunks for better performance
TIMEOUT = 1800  # 30 minutes timeout for large files
TEMP_DIR = "temp_downloads"  # Temporary directory for downloads

# Cache for user preferences
user_prefs = {}

class DownloadError(Exception):
    """Custom exception for download-related errors"""
    pass

async def download_file_with_progress(url: str, file_path: str, message: Message) -> None:
    """Download a file from URL to local storage with progress updates"""
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status != 200:
                raise DownloadError(f"Failed to download file. Status: {response.status}")
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0
            last_update = 0
            
            with open(file_path, 'wb') as f:
                async for chunk in response.content.iter_chunked(CHUNK_SIZE):
                    f.write(chunk)
                    downloaded_size += len(chunk)
                    
                    # Update progress every 5% or 10MB, whichever comes first
                    progress = (downloaded_size / total_size) * 100
                    if progress - last_update >= 5 or downloaded_size - last_update >= 10 * 1024 * 1024:
                        await message.edit_text(
                            f"⬇️ Downloading... {downloaded_size/(1024*1024):.1f}MB / {total_size/(1024*1024):.1f}MB "
                            f"({progress:.1f}%)"
                        )
                        last_update = progress

async def get_file_info(link: str) -> dict:
    """Get file information from TeraBox API"""
    async with aiohttp.ClientSession() as session:
        api_url = f"https://wdzone-terabox-api.vercel.app/api?url={link}"
        try:
            async with session.get(api_url, timeout=60) as resp:
                if resp.status != 200:
                    raise DownloadError("Failed to connect to the API")
                
                data = await resp.json()
                file_info = data.get("📜 Extracted Info", [{}])[0]
                
                if data.get("✅ Status") != "Success" or not file_info:
                    raise DownloadError("No downloadable file found")
                
                return file_info
        except aiohttp.ClientError as e:
            raise DownloadError(f"API request failed: {str(e)}")

async def upload_file_with_progress(client: Client, message: Message, file_path: str, caption: str, is_video: bool) -> None:
    """Upload file to Telegram with progress updates"""
    upload_msg = await message.reply("⬆️ Starting upload...")
    
    def progress(current, total):
        progress_percent = (current / total) * 100
        asyncio.create_task(
            upload_msg.edit_text(
                f"⬆️ Uploading... {current/(1024*1024):.1f}MB / {total/(1024*1024):.1f}MB "
                f"({progress_percent:.1f}%)"
            )
        )
    
    try:
        if is_video:
            await client.send_video(
                chat_id=message.chat.id,
                video=file_path,
                caption=caption,
                supports_streaming=True,
                progress=progress
            )
        else:
            await client.send_document(
                chat_id=message.chat.id,
                document=file_path,
                caption=caption,
                progress=progress
            )
        
        await upload_msg.delete()
    except Exception as e:
        await upload_msg.edit_text(f"❌ Upload failed: {str(e)}")
        raise

@app.on_message(filters.command("start"))
async def start_handler(client: Client, message: Message):
    """Handle /start command"""
    await message.reply_photo(
        photo="https://graph.org/file/4e8a1172e8ba4b7a0bdfa.jpg",
        caption=(
            "👋 Welcome to TeraBox Downloader Bot!\n\n"
            "Send me a TeraBox sharing link to download files (up to 500MB).\n\n"
            "Commands available:\n"
            "/start - Show this message\n"
            "/mode - Toggle between direct download and upload modes\n"
            "/help - Show help information"
        ),
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("📌 Join Channel", url="https://t.me/Opleech_WD")]]
        )
    )

@app.on_message(filters.command("mode"))
async def mode_handler(client: Client, message: Message):
    """Toggle between download link and direct upload modes"""
    user_id = message.from_user.id
    current_mode = user_prefs.get(user_id, {}).get("upload_mode", False)
    new_mode = not current_mode
    
    user_prefs[user_id] = {"upload_mode": new_mode}
    
    mode_text = "direct upload" if new_mode else "download link"
    await message.reply(
        f"🔄 Mode changed: Now sending files as {mode_text}.\n"
        f"Note: Files larger than {MAX_UPLOAD_SIZE_MB}MB will always be sent as links."
    )

@app.on_message(filters.command("help"))
async def help_handler(client: Client, message: Message):
    """Show help information"""
    await message.reply(
        f"ℹ️ TeraBox Downloader Bot Help\n\n"
        f"1. Send a TeraBox sharing link to download the file\n"
        f"2. Use /mode to toggle between getting download links or direct file uploads\n"
        f"3. Files larger than {MAX_UPLOAD_SIZE_MB}MB will always be sent as links\n"
        f"4. The bot supports uploads up to {MAX_UPLOAD_SIZE_MB}MB\n\n"
        f"Note: Large files may take time to download and upload."
    )

@app.on_message(filters.text)
async def link_handler(client: Client, message: Message):
    """Handle TeraBox links"""
    link = message.text.strip()
    if not TERABOX_REGEX.match(link):
        return
    
    user_id = message.from_user.id
    upload_mode = user_prefs.get(user_id, {}).get("upload_mode", False)
    
    try:
        # Inform user we're processing
        processing_msg = await message.reply("⏳ Processing link...")
        
        # Get file info from API
        file_info = await get_file_info(link)
        title = file_info.get("📂 Title", "Unknown").replace("/", "_")  # Sanitize filename
        size_text = file_info.get("📏 Size", "Unknown")
        download_link = file_info.get("🔽 Direct Download Link")
        thumbnail_url = file_info.get("🖼️ Thumbnails", {}).get("360x270")
        
        # Parse file size
        try:
            size_mb = float(size_text.replace("MB", "").strip())
        except (ValueError, AttributeError):
            size_mb = 0
        
        caption = f"📂 Title: {title}\n📏 Size: {size_text}"
        buttons = [[InlineKeyboardButton("🔗 Download Link", url=download_link)]]
        
        # Check if we should attempt upload
        should_upload = upload_mode and size_mb > 0 and size_mb <= MAX_UPLOAD_SIZE_MB
        
        if should_upload:
            try:
                # Create temp directory if it doesn't exist
                os.makedirs(TEMP_DIR, exist_ok=True)
                file_path = os.path.join(TEMP_DIR, title)
                
                # Download the file with progress updates
                await processing_msg.edit_text("⬇️ Starting download...")
                await download_file_with_progress(download_link, file_path, processing_msg)
                
                # Verify the actual downloaded file size
                actual_size_mb = os.path.getsize(file_path) / (1024 * 1024)
                if actual_size_mb > MAX_UPLOAD_SIZE_MB:
                    raise DownloadError(f"File too large ({actual_size_mb:.1f}MB > {MAX_UPLOAD_SIZE_MB}MB)")
                
                # Determine if it's a video file
                is_video = any(file_path.lower().endswith(ext) for ext in ['.mp4', '.mov', '.avi', '.mkv', '.webm'])
                
                # Upload the file with progress updates
                await upload_file_with_progress(client, message, file_path, caption, is_video)
                
                # Clean up
                os.remove(file_path)
                await processing_msg.delete()
                return
                
            except Exception as upload_error:
                logger.error(f"Upload failed: {str(upload_error)}")
                # Fall back to sending the link
                should_upload = False
                await processing_msg.edit_text("⚠️ Upload failed, sending download link instead...")
                await asyncio.sleep(2)
        
        # If not uploading or upload failed, send the link
        if thumbnail_url:
            await message.reply_photo(
                photo=thumbnail_url,
                caption=caption,
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        else:
            await message.reply(
                caption,
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        
        await processing_msg.delete()
        
    except DownloadError as e:
        await message.reply(f"❌ Error: {str(e)}")
    except Exception as e:
        logger.exception("Unexpected error in link_handler")
        await message.reply(f"❌ An unexpected error occurred:\n{str(e)}")
    finally:
        # Clean up any remaining processing message
        try:
            await processing_msg.delete()
        except:
            pass

if __name__ == "__main__":
    logger.info("Starting TeraBox Downloader Bot...")
    # Create temp directory if it doesn't exist
    os.makedirs(TEMP_DIR, exist_ok=True)
    app.run()
