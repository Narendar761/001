import os
import asyncio
from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait
import ffmpeg
import subprocess

# Load environment variables
load_dotenv()

# Configuration from .env
API_ID = int(os.getenv("API_ID", 123456))
API_HASH = os.getenv("API_HASH", "your_api_hash")
BOT_TOKEN = os.getenv("BOT_TOKEN", "your_bot_token")
WATERMARK_TEXT = os.getenv("WATERMARK_TEXT", "Your Text")
FONT_SIZE = int(os.getenv("FONT_SIZE", 24))
FONT_COLOR = os.getenv("FONT_COLOR", "white")
FONT_FILE = os.getenv("FONT_FILE", "arial.ttf")
POSITION = os.getenv("POSITION", "bottom_right")
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", 100)) * 1024 * 1024  # 100MB

app = Client("watermark_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

def get_position_args(position):
    positions = {
        "top_left": {"x": "10", "y": "10"},
        "top_right": {"x": "(w-text_w)-10", "y": "10"},
        "bottom_left": {"x": "10", "y": "(h-text_h)-10"},
        "bottom_right": {"x": "(w-text_w)-10", "y": "(h-text_h)-10"},
        "center": {"x": "(w-text_w)/2", "y": "(h-text_h)/2"}
    }
    return positions.get(position, positions["bottom_right"])

async def generate_thumbnail(input_path, output_path="thumbnail.jpg", time="00:00:01"):
    """Generate thumbnail from video"""
    try:
        (
            ffmpeg
            .input(input_path, ss=time)
            .output(output_path, vframes=1)
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )
        return output_path if os.path.exists(output_path) else None
    except ffmpeg.Error as e:
        print(f"Thumbnail error: {e.stderr.decode()}")
        return None

async def add_watermark_to_video(input_path, output_path):
    """Add watermark to video"""
    pos = get_position_args(POSITION)
    try:
        cmd = [
            'ffmpeg',
            '-i', input_path,
            '-vf', f"drawtext=text='{WATERMARK_TEXT}':fontfile={FONT_FILE}:"
                   f"fontcolor={FONT_COLOR}:fontsize={FONT_SIZE}:"
                   f"x={pos['x']}:y={pos['y']}",
            '-c:v', 'libx264',
            '-preset', 'fast',
            '-crf', '18',
            '-c:a', 'copy',
            '-y',
            output_path
        ]
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await process.communicate()
        return os.path.exists(output_path)
    except Exception as e:
        print(f"Video watermark error: {str(e)}")
        return False

async def add_watermark_to_image(input_path, output_path):
    """Add watermark to image"""
    pos = get_position_args(POSITION)
    try:
        cmd = [
            'ffmpeg',
            '-i', input_path,
            '-vf', f"drawtext=text='{WATERMARK_TEXT}':fontfile={FONT_FILE}:"
                   f"fontcolor={FONT_COLOR}:fontsize={FONT_SIZE}:"
                   f"x={pos['x']}:y={pos['y']}",
            '-y',
            output_path
        ]
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await process.communicate()
        return os.path.exists(output_path)
    except Exception as e:
        print(f"Image watermark error: {str(e)}")
        return False

@app.on_message(filters.command(["start", "help"]) & filters.private)
async def start_handler(client: Client, message: Message):
    await message.reply_text(
        "Welcome to the Watermark Bot!\n"
        "Send me a video or image and I'll add a text watermark.\n\n"
        f"Current settings:\n"
        f"Text: {WATERMARK_TEXT}\n"
        f"Position: {POSITION}\n"
        f"Font size: {FONT_SIZE}\n"
        f"Color: {FONT_COLOR}"
    )

@app.on_message(filters.private & (filters.video | filters.photo))
async def media_handler(client: Client, message: Message):
    try:
        # Check file size
        file_size = message.video.file_size if message.video else message.photo.file_size
        if file_size > MAX_FILE_SIZE:
            await message.reply_text(f"File is too large (max {MAX_FILE_SIZE//(1024*1024)}MB allowed).")
            return

        is_video = bool(message.video)
        file_type = "video" if is_video else "image"
        
        sent_msg = await message.reply_text(f"Downloading {file_type}...")

        # Create unique file names
        unique_id = message.video.file_unique_id if is_video else message.photo.file_unique_id
        input_path = f"downloads/input_{unique_id}.{'mp4' if is_video else 'jpg'}"
        output_path = f"downloads/output_{unique_id}.{'mp4' if is_video else 'jpg'}"
        thumbnail_path = f"downloads/thumb_{unique_id}.jpg"

        # Ensure downloads directory exists
        os.makedirs("downloads", exist_ok=True)

        # Download file
        try:
            await message.download(
                file_name=input_path,
                progress=progress_callback,
                progress_args=(sent_msg, "Downloading")
            )
        except Exception as e:
            await sent_msg.edit_text(f"Download failed: {str(e)}")
            return

        # Generate thumbnail for videos
        if is_video:
            await sent_msg.edit_text("Generating thumbnail...")
            await generate_thumbnail(input_path, thumbnail_path)

        # Add watermark
        await sent_msg.edit_text(f"Adding watermark to {file_type}...")
        
        success = False
        if is_video:
            success = await add_watermark_to_video(input_path, output_path)
        else:
            success = await add_watermark_to_image(input_path, output_path)

        if not success:
            await sent_msg.edit_text(f"Failed to add watermark to {file_type}.")
            return

        # Upload result
        await sent_msg.edit_text(f"Uploading watermarked {file_type}...")
        try:
            if is_video:
                await message.reply_video(
                    video=output_path,
                    thumb=thumbnail_path if os.path.exists(thumbnail_path) else None,
                    caption="Here's your watermarked video!",
                    progress=progress_callback,
                    progress_args=(sent_msg, "Uploading")
                )
            else:
                await message.reply_photo(
                    photo=output_path,
                    caption="Here's your watermarked image!"
                )
        except Exception as e:
            await sent_msg.edit_text(f"Upload failed: {str(e)}")
            return

        # Clean up
        await sent_msg.delete()
        for file_path in [input_path, output_path, thumbnail_path]:
            try:
                if file_path and os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                print(f"Error deleting {file_path}: {str(e)}")

    except FloodWait as e:
        await asyncio.sleep(e.value)
    except Exception as e:
        await message.reply_text(f"An error occurred: {str(e)}")

async def progress_callback(current, total, message: Message, stage):
    try:
        percent = min(int(current * 100 / total), 100)
        await message.edit_text(f"{stage}... {percent}%")
    except:
        pass

if __name__ == "__main__":
    os.makedirs("downloads", exist_ok=True)
    print("Bot is running...")
    app.run()
