import os
import io
import requests
from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.types import Message

# Load secrets from .env
load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
LOG_CHANNEL = int(os.getenv("LOG_CHANNEL"))
BOT_USERNAME = os.getenv("BOT_USERNAME")  # without @

# Initialize bot
bot = Client("instagram_downloader_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# /start command for private chats only
@bot.on_message(filters.command("start") & filters.private)
async def start_command(client: Client, message: Message):
    await message.reply_text(
        "**👋 Welcome to Instagram Downloader Bot!**\n\n"
        "📥 Just send me an Instagram **reel or post link** and I’ll download the media for you.\n"
        f"🔗 Example: `https://www.instagram.com/reel/abc123/`\n\n"
        f"🤖 Powered by @{BOT_USERNAME}",
        quote=True
    )

# Function to process Instagram links
async def process_instagram_link(message: Message, url: str):
    processing_msg = await message.reply("🔍 Processing your Instagram link...")

    api_url = f"https://instagram-media-downloader-662h16y9n-narendar761s-projects.vercel.app/api/instagram?url={url}"
    try:
        response = requests.get(api_url)
        data = response.json()
    except Exception:
        await processing_msg.edit("⚠️ Failed to fetch data from the API.")
        return

    if data.get("error"):
        await processing_msg.edit("❌ Couldn't download media. Try a different link.")
        return

    medias = data.get("medias", [])
    if not medias:
        await processing_msg.edit("⚠️ No downloadable media found.")
        return

    await processing_msg.edit(f"📥 Found {len(medias)} media file(s). Downloading...")

    for i, media in enumerate(medias, start=1):
        media_url = media.get("url")
        media_type = media.get("type")
        extension = media.get("extension")

        if not media_url:
            continue

        try:
            download_note = await message.reply(f"📥 Downloading media {i}/{len(medias)}...")
            resp = requests.get(media_url, stream=True)
            resp.raise_for_status()

            file = io.BytesIO(resp.content)
            file.name = f"instagram_media_{i}.{extension}"

            caption = f"🎬 From Instagram\n🤖 Powered by @{BOT_USERNAME}"

            upload_note = await download_note.edit(f"📤 Uploading media {i}/{len(medias)}...")

            if media_type == "video":
                await message.reply_video(file, caption=caption)
            elif media_type == "image":
                await message.reply_photo(file, caption=caption)

            await upload_note.delete()
        except Exception as e:
            await message.reply(f"❌ Failed to upload media {i}: {e}")

    await processing_msg.edit("✅ All media sent!")

    # Log to channel
    chat_title = message.chat.title if message.chat.type != "private" else "Private"
    await bot.send_message(
        LOG_CHANNEL,
        f"📥 Used by: [{message.from_user.first_name}](tg://user?id={message.from_user.id})\n"
        f"🏷 Chat: {chat_title}\n"
        f"🔗 Link: {url}\n"
        f"📦 Files: {len(medias)}"
    )

# Handler: Watch for Instagram links in all messages (private & group)
@bot.on_message(filters.text & (filters.group | filters.private))
async def catch_instagram_links(client: Client, message: Message):
    text = message.text.strip()

    # Match basic Instagram link types
    if "instagram.com/" in text:
        # Optional: you could extract the exact URL using regex here
        await process_instagram_link(message, text)

bot.run()
      
