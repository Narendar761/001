import os
import asyncio
from PIL import Image, ImageDraw, ImageFont
from pyrogram import Client, filters
from pyrogram.types import Message
from moviepy import VideoFileClip, TextClip, CompositeVideoClip
from tempfile import NamedTemporaryFile

# Configuration
API_ID = "22808125"  # Replace with your API ID
API_HASH = "406c09543fec722fe3c48ca2f06d78de"  # Replace with your API hash
BOT_TOKEN = "7833232359:AAGMa8Qrf81RiCyYdulIYoys89UlC6dz86Q"  # Replace with your bot token
WATERMARK_TEXT = "@YourWatermark"  # Your watermark text
FONT_PATH = "arial.ttf"  # Path to font file (or use default)
FONT_SIZE = 48
OPACITY = 128  # 0-255
POSITION = "bottom-right"  # Options: top-left, top-right, bottom-left, bottom-right, center

# Create Pyrofork client
app = Client(
    "watermark_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

def add_image_watermark(input_path, output_path):
    """Add watermark to an image"""
    try:
        # Open the original image
        original = Image.open(input_path).convert("RGBA")
        width, height = original.size
        
        # Create a transparent layer for the watermark
        watermark = Image.new("RGBA", original.size, (0, 0, 0, 0))
        
        # Load font (fallback to default if specified font not found)
        try:
            font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
        except:
            font = ImageFont.load_default()
        
        # Create drawing context
        draw = ImageDraw.Draw(watermark)
        
        # Calculate text size using textbbox (new method)
        left, top, right, bottom = draw.textbbox((0, 0), WATERMARK_TEXT, font=font)
        text_width = right - left
        text_height = bottom - top
        
        # Determine position based on configuration
        if POSITION == "top-left":
            position = (10, 10)
        elif POSITION == "top-right":
            position = (width - text_width - 10, 10)
        elif POSITION == "bottom-left":
            position = (10, height - text_height - 10)
        elif POSITION == "center":
            position = ((width - text_width) // 2, (height - text_height) // 2)
        else:  # bottom-right (default)
            position = (width - text_width - 10, height - text_height - 10)
        
        # Add text to watermark layer
        draw.text(position, WATERMARK_TEXT, font=font, fill=(255, 255, 255, OPACITY))
        
        # Combine original with watermark
        watermarked = Image.alpha_composite(original, watermark)
        
        # Save the result
        if output_path.lower().endswith(('.jpg', '.jpeg')):
            watermarked.convert("RGB").save(output_path, "JPEG", quality=95)
        else:
            watermarked.save(output_path, "PNG")
        return True
    except Exception as e:
        print(f"Error adding image watermark: {e}")
        return False

def add_video_watermark(input_path, output_path):
    """Add watermark to a video"""
    try:
        # Load the video clip
        clip = VideoFileClip(input_path)
        
        # Create a text clip for the watermark
        txt_clip = (TextClip(WATERMARK_TEXT, fontsize=FONT_SIZE, color='white',
                           font=FONT_PATH if os.path.exists(FONT_PATH) else None)
                   .set_opacity(OPACITY/255)
                   .set_duration(clip.duration))
        
        # Get text dimensions
        text_size = txt_clip.size
        
        # Determine position based on configuration
        if POSITION == "top-left":
            position = (10, 10)
        elif POSITION == "top-right":
            position = (clip.w - text_size[0] - 10, 10)
        elif POSITION == "bottom-left":
            position = (10, clip.h - text_size[1] - 10)
        elif POSITION == "center":
            position = ('center', 'center')
        else:  # bottom-right (default)
            position = (clip.w - text_size[0] - 10, clip.h - text_size[1] - 10)
        
        # Add watermark to video
        watermarked = CompositeVideoClip([clip, txt_clip.set_pos(position)])
        
        # Write the result to a file
        watermarked.write_videofile(
            output_path,
            codec='libx264',
            audio_codec='aac',
            threads=4,
            preset='fast',
            ffmpeg_params=['-crf', '23']
        )
        return True
    except Exception as e:
        print(f"Error adding video watermark: {e}")
        return False

@app.on_message(filters.command("start"))
async def start_command(client: Client, message: Message):
    """Handler for /start command"""
    await message.reply_text(
        "👋 Hello! I'm a watermark bot. Send me an image or video and I'll add a watermark to it.\n\n"
        "Supported commands:\n"
        "/watermark - Set custom watermark text\n"
        "/position - Change watermark position\n"
        "/opacity - Adjust watermark opacity"
    )

@app.on_message(filters.photo | filters.video | filters.document)
async def handle_media(client: Client, message: Message):
    """Handler for incoming photos and videos"""
    try:
        # Check if the document is an image or video
        if message.document and not (message.document.mime_type.startswith('image/') or 
                                   message.document.mime_type.startswith('video/')):
            return
        
        # Download status
        processing_msg = await message.reply_text("⏳ Downloading your file...")
        
        # Download the file
        media_path = await message.download()
        
        # Determine media type
        is_video = message.video or (message.document and message.document.mime_type.startswith('video/'))
        is_image = message.photo or (message.document and message.document.mime_type.startswith('image/'))
        
        if not (is_video or is_image):
            await processing_msg.edit_text("❌ Unsupported file type. Please send an image or video.")
            os.remove(media_path)
            return
        
        await processing_msg.edit_text("🖌 Adding watermark...")
        
        # Process the file
        with NamedTemporaryFile(delete=False, suffix='.png' if is_image else '.mp4') as temp_file:
            output_path = temp_file.name
        
        success = False
        if is_image:
            success = add_image_watermark(media_path, output_path)
            media_type = "photo"
        else:
            success = add_video_watermark(media_path, output_path)
            media_type = "video"
        
        if not success:
            await processing_msg.edit_text("❌ Failed to add watermark. Please try again.")
            os.remove(media_path)
            if os.path.exists(output_path):
                os.remove(output_path)
            return
        
        # Send the watermarked file back
        await processing_msg.edit_text("📤 Uploading watermarked file...")
        
        if is_image:
            await message.reply_photo(
                photo=output_path,
                caption=f"Here's your watermarked image with '{WATERMARK_TEXT}'"
            )
        else:
            await message.reply_video(
                video=output_path,
                caption=f"Here's your watermarked video with '{WATERMARK_TEXT}'"
            )
        
        # Clean up
        os.remove(media_path)
        os.remove(output_path)
        await processing_msg.delete()
        
    except Exception as e:
        print(f"Error processing media: {e}")
        await message.reply_text("❌ An error occurred while processing your file. Please try again.")
        # Clean up any remaining files
        if 'media_path' in locals() and os.path.exists(media_path):
            os.remove(media_path)
        if 'output_path' in locals() and os.path.exists(output_path):
            os.remove(output_path)

@app.on_message(filters.command("watermark"))
async def set_watermark(client: Client, message: Message):
    """Handler to set custom watermark text"""
    global WATERMARK_TEXT
    if len(message.command) > 1:
        new_text = ' '.join(message.command[1:])
        WATERMARK_TEXT = new_text
        await message.reply_text(f"✅ Watermark text updated to: '{WATERMARK_TEXT}'")
    else:
        await message.reply_text(f"Current watermark text: '{WATERMARK_TEXT}'\n\n"
                               "To change it, send /watermark followed by your new text")

@app.on_message(filters.command("position"))
async def set_position(client: Client, message: Message):
    """Handler to set watermark position"""
    global POSITION
    if len(message.command) > 1:
        new_pos = message.command[1].lower()
        if new_pos in ["top-left", "top-right", "bottom-left", "bottom-right", "center"]:
            POSITION = new_pos
            await message.reply_text(f"✅ Watermark position updated to: {POSITION}")
        else:
            await message.reply_text("❌ Invalid position. Choose from: top-left, top-right, bottom-left, bottom-right, center")
    else:
        await message.reply_text(f"Current watermark position: {POSITION}\n\n"
                               "To change it, send /position followed by one of these options:\n"
                               "top-left, top-right, bottom-left, bottom-right, center")

@app.on_message(filters.command("opacity"))
async def set_opacity(client: Client, message: Message):
    """Handler to set watermark opacity"""
    global OPACITY
    if len(message.command) > 1:
        try:
            new_opacity = int(message.command[1])
            if 0 <= new_opacity <= 255:
                OPACITY = new_opacity
                await message.reply_text(f"✅ Watermark opacity updated to: {OPACITY} (0-255 scale)")
            else:
                await message.reply_text("❌ Opacity must be between 0 and 255")
        except ValueError:
            await message.reply_text("❌ Please provide a number between 0 and 255")
    else:
        await message.reply_text(f"Current watermark opacity: {OPACITY} (0-255 scale)\n\n"
                               "To change it, send /opacity followed by a number (0-255)")

# Start the bot
print("Bot is running...")
app.run()
