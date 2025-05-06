from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
import aiohttp
import os
import re
from typing import Optional
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration (should use environment variables in production)
API_ID = os.getenv("API_ID", "YOUR_API_ID")
API_HASH = os.getenv("API_HASH", "YOUR_API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN")

app = Client("Instagram_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)


MAX_VIDEO_SIZE_MB = 50  # Telegram's limit for bots is usually 50MB
CHUNK_SIZE = 1024 * 1024  # 1MB chunks for downloading
TIMEOUT = 300  # 5 minutes timeout for operations

# Cache for user preferences
user_prefs = {}

class DownloadError(Exception):
    """Custom exception for download-related errors"""
    pass

async def download_file(url: str, file_path: str) -> None:
    """Download a file from URL to local storage"""
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status != 200:
                raise DownloadError(f"Failed to download file. Status: {response.status}")
            
            with open(file_path, 'wb') as f:
                async for chunk in response.content.iter_chunked(CHUNK_SIZE):
                    f.write(chunk)

async def get_file_info(link: str) -> dict:
    """Get file information from Instagram API"""
    async with aiohttp.ClientSession() as session:
        api_url = f"https://api.yabes-desu.workers.dev/download/instagram/v2?url={link}"
        try:
            async with session.get(api_url, timeout=TIMEOUT) as resp:
                if resp.status != 200:
                    raise DownloadError("Failed to connect to the API")
                
                data = await resp.json()
                file_info = data.get("data", [{}])[0]
                
                if data.get("Status") != "true" or not file_info:
                    raise DownloadError("No downloadable file found")
                
                return file_info
        except aiohttp.ClientError as e:
            raise DownloadError(f"API request failed: {str(e)}")

@app.on_message(filters.command("start"))
async def start_handler(client: Client, message: Message):
    """Handle /start command"""
    await message.reply_photo(
        photo="https://graph.org/file/4e8a1172e8ba4b7a0bdfa.jpg",
        caption=(
            "👋 Welcome to instagram Downloader Bot!\n\n"
            "Send me a Instagram sharing link to download files.\n\n"
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
        f"Note: Large files (>50MB) will always be sent as links."
    )

@app.on_message(filters.command("help"))
async def help_handler(client: Client, message: Message):
    """Show help information"""
    await message.reply(
        "ℹ️ Instagram Downloader Bot Help\n\n"
        "1. Send a Instagram sharing link to download the file\n"
        "2. Use /mode to toggle between getting download links or direct file uploads\n"
        "3. Files larger than 50MB will always be sent as links\n\n"
        "Note: This bot uses a third-party API to fetch download links."
    )

@app.on_message(filters.text)
async def link_handler(client: Client, message: Message):
    """Handle Instagram links"""
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
        
        download_link = file_info.get("url")
        
        
        # Parse file size
        try:
            size_mb = float(size_text.replace("MB", "").strip())
        except (ValueError, AttributeError):
            size_mb = 0
        
        caption = f"Size: {size_text}"
        buttons = [[InlineKeyboardButton("🔗 Download Link", url=download_link)]]
        
        # Check if we should upload directly
        should_upload = upload_mode and size_mb > 0 and size_mb <= MAX_VIDEO_SIZE_MB
        
        if should_upload:
            # Download and upload the file directly
            await processing_msg.edit_text("⬇️ Downloading file...")
            
            try:
                # Create temp directory if it doesn't exist
                os.makedirs("temp", exist_ok=True)
                file_path = f"temp/{title}"
                
                # Download the file
                await download_file(download_link, file_path)
                
                # Check file size again (in case the API info was wrong)
                actual_size_mb = os.path.getsize(file_path) / (1024 * 1024)
                if actual_size_mb > MAX_VIDEO_SIZE_MB:
                    raise DownloadError(f"File too large ({actual_size_mb:.2f}MB > {MAX_VIDEO_SIZE_MB}MB)")
                
                # Upload the file
                await processing_msg.edit_text("⬆️ Uploading file...")
                
                if file_path.lower().endswith(('.mp4', '.mov', '.avi', '.mkv')):
                    # Upload as video
                    await message.reply_video(
                        video=file_path,
                        caption=caption,
                        supports_streaming=True,
                        progress=lambda current, total: logger.info(f"Uploaded {current}/{total} bytes")
                    )
                else:
                    # Upload as document
                    await message.reply_document(
                        document=file_path,
                        caption=caption,
                        progress=lambda current, total: logger.info(f"Uploaded {current}/{total} bytes")
                    )
                
                # Clean up
                os.remove(file_path)
                await processing_msg.delete()
                return
                
            except Exception as upload_error:
                logger.error(f"Upload failed: {str(upload_error)}")
                # Fall back to sending the link
                should_upload = False
        
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

if __name__ == "__main__":
    logger.info("Starting Instagram Downloader Bot...")
    app.run()
