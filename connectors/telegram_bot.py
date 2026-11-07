"""
connectors/telegram_bot.py - Telegram Polling Bot & Voice Notes Handler
"""
import os
import re
import asyncio
import threading
from pathlib import Path
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from config.settings import get_telegram_token, get_authorized_user_ids, TEMP_DIR
from core.agent_loop import process_user_input, llm_router
from tools.screen_vision import run_async_safe
from core.logger import logger

_telegram_thread = None
_telegram_app = None
_is_running = False
_last_chat_id = None


def is_authorized(user_id: int) -> bool:
    user_ids = get_authorized_user_ids()
    if not user_ids:
        return True
    return user_id in user_ids


def send_photo_to_telegram(image_path: str, caption: str = "") -> bool:
    """Sends a photo to Telegram asynchronously from any thread (e.g. Terminal)."""
    global _telegram_app, _last_chat_id
    if not _telegram_app or not _last_chat_id:
        return False

    async def _send():
        try:
            p = Path(image_path)
            if not p.exists():
                return False
            with open(p, "rb") as photo:
                await _telegram_app.bot.send_photo(chat_id=_last_chat_id, photo=photo, caption=caption or "📸 Here is your screenshot!")
            return True
        except Exception as e:
            logger.error(f"Failed to send photo to Telegram: {e}")
            return False

    return run_async_safe(_send())


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global _last_chat_id
    _last_chat_id = update.effective_chat.id
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("⛔ Unauthorized user ID.")
        return
    await update.message.reply_text("hey, i'm Friday — online and standing by 👋")


async def send_response_with_media(update: Update, response: str):
    """Parses response for media tags (e.g. [SCREENSHOT:path]) and sends photo via Telegram, then deletes temp file."""
    screenshot_match = re.search(r"\[SCREENSHOT:(.*?)\]", response)
    if screenshot_match:
        file_path_str = screenshot_match.group(1).strip()
        clean_text = re.sub(r"\[SCREENSHOT:.*?\]", "", response).strip()
        file_path = Path(file_path_str)

        if file_path.exists():
            try:
                with open(file_path, "rb") as photo_file:
                    await update.message.reply_photo(photo=photo_file, caption=clean_text or "📸 Here is your screenshot!")
            except Exception as e:
                logger.error(f"Error sending screenshot to Telegram: {e}")
                await update.message.reply_text(clean_text or "📸 Screenshot captured.")
            finally:
                try:
                    if file_path.exists():
                        file_path.unlink()
                except Exception as err:
                    logger.error(f"Failed to delete temp screenshot file: {err}")
            return
        else:
            await update.message.reply_text(clean_text or "📸 Screenshot captured.")
            return

    await update.message.reply_text(response)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global _last_chat_id
    _last_chat_id = update.effective_chat.id

    user_id = update.effective_user.id
    if not is_authorized(user_id):
        await update.message.reply_text("⛔ Unauthorized user ID.")
        return

    text = update.message.text
    if not text:
        return

    response = process_user_input(text, session_id="default")
    await send_response_with_media(update, response)


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        await update.message.reply_text("⛔ Unauthorized user ID.")
        return

    file = await context.bot.get_file(update.message.voice.file_id)
    voice_path = TEMP_DIR / f"voice_{update.message.message_id}.ogg"
    await file.download_to_drive(custom_path=voice_path)

    # Transcribe voice with Whisper via Groq
    transcript = llm_router.transcribe_audio(str(voice_path))
    if voice_path.exists():
        voice_path.unlink()

    if not transcript:
        await update.message.reply_text("Sorry, I couldn't transcribe your voice note.")
        return

    await update.message.reply_text(f"🎙️ *You said:* {transcript}")
    response = process_user_input(transcript, session_id="default")
    await send_response_with_media(update, response)


def is_telegram_running() -> bool:
    global _telegram_thread, _is_running
    return _is_running and _telegram_thread is not None and _telegram_thread.is_alive()


def run_telegram_bot(is_background: bool = False):
    global _is_running
    token = get_telegram_token()
    if not token:
        logger.warning("⚠️ TELEGRAM_BOT_TOKEN missing in .env file. Skipping Telegram daemon.")
        _is_running = False
        return

    _is_running = True
    try:
        app = ApplicationBuilder().token(token).build()
        app.add_handler(CommandHandler("start", start_command))
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
        app.add_handler(MessageHandler(filters.VOICE, handle_voice))

        if is_background:
            logger.debug("🤖 Starting Friday Telegram Bot polling daemon in background...")
            app.run_polling(stop_signals=None)
        else:
            logger.info("🤖 Starting Friday Telegram Bot polling daemon (Foreground)...")
            app.run_polling()
    except Exception as e:
        logger.error(f"Telegram Bot error: {e}")
    finally:
        _is_running = False


def start_telegram_in_background() -> bool:
    """Starts Telegram Bot daemon in a background thread if configured and not already running."""
    global _telegram_thread, _is_running
    if is_telegram_running():
        logger.debug("Telegram Bot is already running in background.")
        return True

    token = get_telegram_token()
    if not token:
        logger.warning("⚠️ TELEGRAM_BOT_TOKEN missing in .env. Telegram daemon auto-start skipped.")
        return False

    def _worker():
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            run_telegram_bot(is_background=True)
        except Exception as err:
            logger.error(f"Telegram background thread error: {err}")

    _telegram_thread = threading.Thread(target=_worker, daemon=True, name="FridayTelegramBot")
    _telegram_thread.start()
    _is_running = True
    logger.debug("🤖 Telegram Bot daemon started in background thread.")
    return True
