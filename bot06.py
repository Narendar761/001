from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import aiohttp
import os
import re
import logging
import asyncio
import math
from datetime import datetime
import hashlib

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
LOG_CHANNEL = os.getenv("LOG_CHANNEL", "YOUR_LOG_CHANNEL_ID")

app = Client("terabox_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Constants
TERABOX_REGEX = re.compile(
    r'^https?:\/\/(?:www\.)?(?:[\w-]+\.)?(terabox\.com|1024terabox\.com|teraboxapp\.com|terafileshare\.com|teraboxlink\.com|terasharelink\.com)\/(s|sharing)\/[\w-]+',
    re.IGNORECASE
)
CHUNK_SIZE = 1024 * 1024 * 4  # 4MB chunks
TIMEOUT = 3600  # 60 minutes timeout
TEMP_DIR = "temp_downloads"
MAX_RETRIES = 3
PROGRESS_UPDATE_THRESHOLD = 5  # Minimum percentage change to update progress

# Cache for download links
download_cache = {}

class DownloadError(Exception):
    """Custom exception for download-related errors"""
    pass

def generate_file_hash(content: str) -> str:
    """Generate a short hash for callback data"""
    return hashlib.md5(content.encode()).hexdigest()[:10]

async def log_to_channel(text: str):
    """Send log message to the log channel"""
    try:
        await app.send_message(LOG_CHANNEL, text)
    except Exception as e:
        logger.error(f"Failed to send log to channel: {str(e)}")

def format_size(size_bytes: int) -> str:
    """Convert bytes to human-readable format"""
    if size_bytes == 0:
        return "0B"
    size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {size_name[i]}"

def progress_bar(percentage: float) -> str:
    """Generate a progress bar string"""
    filled = '█' * int(percentage / 5)
    empty = '░' * (20 - len(filled))
    return f"[{filled}{empty}]"

async def safe_edit_message(message: Message, text: str):
    """Safely edit a message with error handling"""
    try:
        await message.edit_text(text)
    except Exception as e:
        if "MESSAGE_NOT_MODIFIED" not in str(e):
            logger.warning(f"Failed to edit message: {str(e)}")

async def download_file_with_progress(url: str, file_path: str, message: Message) -> None:
    """Download a file with progress updates"""
    last_progress = -PROGRESS_UPDATE_THRESHOLD  # Ensure first update happens
    
    for attempt in range(MAX_RETRIES):
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        raise DownloadError(f"Failed to download file. Status: {response.status}")
                    
                    total_size = int(response.headers.get('content-length', 0))
                    downloaded_size = 0
                    
                    with open(file_path, 'wb') as f:
                        async for chunk in response.content.iter_chunked(CHUNK_SIZE):
                            if chunk:  # Ensure chunk is not empty
                                f.write(chunk)
                                downloaded_size += len(chunk)
                                
                                progress = (downloaded_size / total_size) * 100 if total_size > 0 else 0
                                
                                # Only update if progress changed significantly
                                if abs(progress - last_progress) >= PROGRESS_UPDATE_THRESHOLD:
                                    bar = progress_bar(progress)
                                    await safe_edit_message(
                                        message,
                                        f"⬇️ Downloading...\n"
                                        f"{bar} {progress:.1f}%\n"
                                        f"{format_size(downloaded_size)} / {format_size(total_size)}"
                                    )
                                    last_progress = progress
                    return
        except Exception as e:
            if attempt == MAX_RETRIES - 1:
                raise DownloadError(f"Download failed after {MAX_RETRIES} attempts: {str(e)}")
            await asyncio.sleep(5)
            continue

async def upload_file_with_progress(client: Client, message: Message, file_path: str, caption: str, is_video: bool) -> Message:
    """Upload file with progress updates"""
    upload_msg = await message.reply("⬆️ Preparing upload...")
    last_progress = -PROGRESS_UPDATE_THRESHOLD  # Ensure first update happens
    
    async def progress(current, total):
        nonlocal last_progress
        progress_percent = (current / total) * 100
        
        # Only update if progress changed significantly
        if abs(progress_percent - last_progress) >= PROGRESS_UPDATE_THRESHOLD:
            bar = progress_bar(progress_percent)
            await safe_edit_message(
                upload_msg,
                f"⬆️ Uploading...\n"
                f"{bar} {progress_percent:.1f}%\n"
                f"{format_size(current)} / {format_size(total)}"
            )
            last_progress = progress_percent
    
    for attempt in range(MAX_RETRIES):
        try:
            if not os.path.exists(file_path):
                raise DownloadError("File not found for upload")
            
            if is_video:
                sent_message = await client.send_video(
                    chat_id=message.chat.id,
                    video=file_path,
                    caption=caption,
                    supports_streaming=True,
                    progress=progress
                )
            else:
                sent_message = await client.send_document(
                    chat_id=message.chat.id,
                    document=file_path,
                    caption=caption,
                    progress=progress
                )
            
            try:
                await upload_msg.delete()
            except:
                pass
            return sent_message
            
        except Exception as e:
            if attempt == MAX_RETRIES - 1:
                await safe_edit_message(upload_msg, f"❌ Upload failed after {MAX_RETRIES} attempts: {str(e)}")
                raise DownloadError(f"Upload failed: {str(e)}")
            await asyncio.sleep(5)
            continue

# [Rest of your code remains the same...]

if __name__ == "__main__":
    logger.info("Starting TeraBox Downloader Bot...")
    os.makedirs(TEMP_DIR, exist_ok=True)
    app.run()
