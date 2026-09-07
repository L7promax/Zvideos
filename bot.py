import os
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

from telegram import Update, InputPaidMediaVideo
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ---- Config (set these as environment variables on Render) ----
BOT_TOKEN = os.environ["BOT_TOKEN"]
PREMIUM_CHANNEL_ID = int(os.environ["PREMIUM_CHANNEL_ID"])  # e.g. -1001234567890


# ---- Tiny HTTP server so Render's free "Web Service" sees an open port ----
def run_health_server():
    port = int(os.environ.get("PORT", 8080))

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Bot is running")

        def log_message(self, *args):
            pass  # keep logs clean

    HTTPServer(("0.0.0.0", port), Handler).serve_forever()


# ---- Handlers ----
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Mujhe koi video bhejo (forward ya direct upload), "
        "main use tumhare premium channel par Stars-lock karke daal dunga."
    )


async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    video = message.video
    if video is None and message.document and (message.document.mime_type or "").startswith("video"):
        video = message.document

    if video is None:
        await message.reply_text("Ye video nahi lag raha, dobara try karo.")
        return

    context.user_data["pending_file_id"] = video.file_id
    context.user_data["pending_caption"] = message.caption or ""
    await message.reply_text("Is video ke liye kitne Stars price rakhna hai? (sirf number bhejo, jaise 50)")


async def handle_price_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "pending_file_id" not in context.user_data:
        return  # no video waiting, ignore random text

    text = update.message.text.strip()
    if not text.isdigit() or int(text) < 1:
        await update.message.reply_text("Sirf ek valid number bhejo (minimum 1), jaise 50")
        return

    star_count = int(text)
    file_id = context.user_data.pop("pending_file_id")
    caption = context.user_data.pop("pending_caption", "")

    try:
        await context.bot.send_paid_media(
            chat_id=PREMIUM_CHANNEL_ID,
            star_count=star_count,
            media=[InputPaidMediaVideo(media=file_id)],
            caption=caption,
        )
        await update.message.reply_text(
            f"Done! Video {star_count} Stars ke lock ke saath channel par daal di gayi."
        )
    except Exception as e:
        logger.exception("Failed to post paid media")
        await update.message.reply_text(f"Error aaya: {e}")


def main():
    threading.Thread(target=run_health_server, daemon=True).start()

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, handle_video))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_price_reply))

    logger.info("Bot starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
