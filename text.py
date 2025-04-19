import os
import time
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip
from PIL import ImageFont

# Bot configuration
API_ID = 1234567  # Replace with your API ID
API_HASH = "your_api_hash_here"  # Replace with your API HASH
BOT_TOKEN = "your_bot_token_here"  # Replace with your bot token

# Initialize the Pyrofork client
app = Client(
    "video_watermark_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# Welcome message handler
@app.on_message(filters.command(["start", "help"]))
async def welcome(client: Client, message: Message):
    welcome_text = """
    🎥 **Video Watermark Bot** 🎥

    Send me a video and I'll add a text watermark to it!

    **Features:**
    - Custom text watermark
    - Position selection
    - Font size adjustment
    - Fast processing

    Just send me a video to get started!
    """
    await message.reply_text(
        welcome_text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Updates Channel", url="https://t.me/yourchannel")],
            [InlineKeyboardButton("💬 Support Group", url="https://t.me/yoursupportgroup")]
        ])
    )

# Progress callback function
async def progress(current, total, message: Message, start_time, operation):
    try:
        percent = current * 100 / total
        elapsed_time = time.time() - start_time
        speed = current / elapsed_time if elapsed_time > 0 else 0
        
        # Progress bar
        progress_bar = "[" + "■" * int(percent / 5) + " " * (20 - int(percent / 5)) + "]"
        
        speed_text = ""
        if speed > 1024 * 1024:
            speed_text = f"{speed / (1024 * 1024):.2f} MB/s"
        elif speed > 1024:
            speed_text = f"{speed / 1024:.2f} KB/s"
        else:
            speed_text = f"{speed:.2f} B/s"
        
        text = (
            f"**{operation}...**\n"
            f"{progress_bar} {percent:.2f}%\n"
            f"**Speed:** {speed_text}\n"
            f"**Processed:** {human_readable_size(current)} / {human_readable_size(total)}"
        )
        
        await message.edit_text(text)
    except FloodWait as e:
        time.sleep(e.value)
    except Exception:
        pass

def human_readable_size(size):
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.2f} KB"
    elif size < 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024):.2f} MB"
    else:
        return f"{size / (1024 * 1024 * 1024):.2f} GB"

# Video processing function
def add_watermark(video_path, output_path, watermark_text="Sample Watermark"):
    try:
        # Load video
        video = VideoFileClip(video_path)
        
        # Create watermark text
        txt_clip = (
            TextClip(
                watermark_text,
                fontsize=50,
                color="white",
                font="Arial-Bold",
                stroke_color="black",
                stroke_width=1
            )
            .set_position(("center", "bottom"))
            .set_duration(video.duration)
            .set_opacity(0.7)
        )
        
        # Composite the video with watermark
        final_clip = CompositeVideoClip([video, txt_clip])
        
        # Write the result to a file
        final_clip.write_videofile(
            output_path,
            codec="libx264",
            audio_codec="aac",
            threads=4,
            preset="ultrafast",
            logger=None
        )
        
        return True
    except Exception as e:
        print(f"Error in watermarking: {e}")
        return False
    finally:
        if 'video' in locals():
            video.close()
        if 'final_clip' in locals():
            final_clip.close()

# Video message handler
@app.on_message(filters.video | filters.document)
async def handle_video(client: Client, message: Message):
    # Check if the document is a video
    if message.document and not message.document.mime_type.startswith("video/"):
        return
    
    # Ask for watermark text
    watermark_text = await client.ask(
        chat_id=message.chat.id,
        text="Please send the text you want to use as watermark:",
        reply_to_message_id=message.id,
        filters=filters.text
    )
    
    processing_msg = await message.reply_text("📥 Downloading video...")
    start_time = time.time()
    
    # Download the video
    video_path = f"downloads/{message.from_user.id}_{message.id}.mp4"
    os.makedirs("downloads", exist_ok=True)
    
    await message.download(
        file_name=video_path,
        progress=lambda current, total: await progress(
            current, total, processing_msg, start_time, "Downloading"
        )
    )
    
    # Process the video
    await processing_msg.edit_text("🔄 Adding watermark...")
    output_path = f"downloads/{message.from_user.id}_{message.id}_watermarked.mp4"
    
    if not add_watermark(video_path, output_path, watermark_text.text):
        await processing_msg.edit_text("❌ Failed to add watermark. Please try again.")
        try:
            os.remove(video_path)
            os.remove(output_path)
        except:
            pass
        return
    
    # Upload the watermarked video
    await processing_msg.edit_text("📤 Uploading watermarked video...")
    upload_start_time = time.time()
    
    await message.reply_video(
        video=output_path,
        caption=f"Here's your watermarked video with text: {watermark_text.text}",
        progress=lambda current, total: await progress(
            current, total, processing_msg, upload_start_time, "Uploading"
        )
    )
    
    await processing_msg.delete()
    
    # Clean up
    try:
        os.remove(video_path)
        os.remove(output_path)
    except:
        pass

# Start the bot
print("Bot is running...")
app.run()
