from pyrofork import Client, filters
from pyrofork.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
import aiohttp
import os
import re
import logging
from typing import Optional
import asyncio
import math

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
CHUNK_SIZE = 1024 * 1024 * 4  # 4MB chunks for better performance
TIMEOUT = 3600  # 60 minutes timeout for very large files
TEMP_DIR = "temp_downloads"  # Temporary directory for downloads
MAX_RETRIES = 3  # Maximum retry attempts for downloads/uploads

# Cache for user preferences
user_prefs = {}

class DownloadError(Exception):
    """Custom exception for download-related errors"""
    pass

async def download_file_with_progress(url: str, file_path: str, message: Message) -> None:
    """Download a file from URL to local storage with progress updates"""
    for attempt in range(MAX_RETRIES):
        try:
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
                            progress = (downloaded_size / total_size) * 100 if total_size > 0 else 0
                            if (progress - last_update >= 5 or 
                                downloaded_size - last_update >= 10 * 1024 * 1024 or
                                total_size == 0):
                                await message.edit_text(
                                    f"⬇️ Downloading... {format_size(downloaded_size)} / "
                                    f"{format_size(total_size)} ({progress:.1f}%)"
                                )
                                last_update = progress
                    return  # Success
        except Exception as e:
            if attempt == MAX_RETRIES - 1:
                raise DownloadError(f"Download failed after {MAX_RETRIES} attempts: {str(e)}")
            await asyncio.sleep(5)  # Wait before retrying
            continue

    raise DownloadError(f"Download failed after {MAX_RETRIES} attempts")

def format_size(size_bytes: int) -> str:
    """Convert bytes to human-readable format"""
    if size_bytes == 0:
        return "0B"
    size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {size_name[i]}"

async def get_file_info(link: str) -> dict:
    """Get file information from TeraBox API"""
    for attempt in range(MAX_RETRIES):
        try:
            async with aiohttp.ClientSession() as session:
                api_url = f"https://wdzone-terabox-api.vercel.app/api?url={link}"
                async with session.get(api_url, timeout=60) as resp:
                    if resp.status != 200:
                        raise DownloadError("Failed to connect to the API")
                    
                    data = await resp.json()
                    file_info = data.get("📜 Extracted Info", [{}])[0]
                    
                    if data.get("✅ Status") != "Success" or not file_info:
                        raise DownloadError("No downloadable file found")
                    
                    return file_info
        except Exception as e:
            if attempt == MAX_RETRIES - 1:
                raise DownloadError(f"API request failed after {MAX_RETRIES} attempts: {str(e)}")
            await asyncio.sleep(2)
            continue

async def upload_file_with_progress(client: Client, message: Message, file_path: str, caption: str, is_video: bool) -> None:
    """Upload file to Telegram with progress updates"""
    upload_msg = await message.reply("⬆️ Preparing upload...")
    
    def progress(current, total):
        progress_percent = (current / total) * 100
        asyncio.create_task(
            upload_msg.edit_text(
                f"⬆️ Uploading... {format_size(current)} / {format_size(total)} "
                f"({progress_percent:.1f}%)"
            )
        )
    
    for attempt in range(MAX_RETRIES):
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
            return  # Success
        except Exception as e:
            if attempt == MAX_RETRIES - 1:
                await upload_msg.edit_text(f"❌ Upload failed after {MAX_RETRIES} attempts: {str(e)}")
                raise DownloadError(f"Upload failed: {str(e)}")
            await asyncio.sleep(5)
            continue

@app.on_message(filters.command("start"))
async def start_handler(client: Client, message: Message):
    """Handle /start command"""
    await message.reply_photo(
        photo="https://graph.org/file/4e8a1172e8ba4b7a0bdfa.jpg",
        caption=(
            "👋 Welcome to TeraBox Downloader Bot!\n\n"
            "Send me a TeraBox sharing link to download files of any size.\n\n"
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
        "Note: Very large files may take longer to process."
    )

@app.on_message(filters.command("help"))
async def help_handler(client: Client, message: Message):
    """Show help information"""
    await message.reply(
        "ℹ️ TeraBox Downloader Bot Help\n\n"
        "1. Send a TeraBox sharing link to download the file\n"
        "2. Use /mode to toggle between getting download links or direct file uploads\n"
        "3. The bot supports files of any size\n"
        "4. Large files will be automatically handled with progress tracking\n\n"
        "Note: Very large files may take significant time to download and upload."
    )

@app.on_message(filters.text & ~filters.edited)
async def link_handler(client: Client, message: Message):
    """Handle TeraBox links"""
    link = message.text.strip()
    if not TERABOX_REGEX.match(link):
        return
    
    user_id = message.from_user.id
    upload_mode = user_prefs.get(user_id, {}).get("upload_mode", False)
    
    processing_msg = None
    try:
        # Inform user we're processing
        processing_msg = await message.reply("⏳ Processing link...")
        
        # Get file info from API
        file_info = await get_file_info(link)
        title = file_info.get("📂 Title", "Unknown").replace("/", "_")  # Sanitize filename
        size_text = file_info.get("📏 Size", "Unknown")
        download_link = file_info.get("🔽 Direct Download Link")
        thumbnail_url = file_info.get("🖼️ Thumbnails", {}).get("360x270")
        
        caption = f"📂 Title: {title}\n📏 Size: {size_text}"
        buttons = [[InlineKeyboardButton("🔗 Download Link", url=download_link)]]
        
        if upload_mode:
            try:
                # Create temp directory if it doesn't exist
                os.makedirs(TEMP_DIR, exist_ok=True)
                file_path = os.path.join(TEMP_DIR, title)
                
                # Download the file with progress updates
                await processing_msg.edit_text("⬇️ Starting download...")
                await download_file_with_progress(download_link, file_path, processing_msg)
                
                # Determine if it's a video file
                is_video = any(file_path.lower().endswith(ext) for ext in ['.mp4', '.mov', '.avi', '.mkv', '.webm']
                
                # Upload the file with progress updates
                await upload_file_with_progress(client, message, file_path, caption, is_video)
                
                # Clean up
                try:
                    os.remove(file_path)
                except:
                    pass
                
                try:
                    await processing_msg.delete()
                except:
                    pass
                return
                
            except Exception as upload_error:
                logger.error(f"Upload failed: {str(upload_error)}")
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
        
        if processing_msg:
            await processing_msg.delete()
        
    except DownloadError as e:
        await message.reply(f"❌ Error: {str(e)}")
    except Exception as e:
        logger.exception("Unexpected error in link_handler")
        await message.reply(f"❌ An unexpected error occurred:\n{str(e)}")
    finally:
        # Clean up any remaining processing message
        if processing_msg:
            try:
                await processing_msg.delete()
            except:
                pass

if __name__ == "__main__":
    logger.info("Starting TeraBox Downloader Bot...")
    # Create temp directory if it doesn't exist
    os.makedirs(TEMP_DIR, exist_ok=True)
    app.run()
