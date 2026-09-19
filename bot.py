"""
SMARTREPORT AUTO — Sprint 1: Telegram Bot

Usage:
    1. Copy .env.example → .env dan isi TELEGRAM_TOKEN
    2. python bot.py
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
)

load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TOKEN:
    print("[ERROR] TELEGRAM_TOKEN tidak ditemukan di .env")
    sys.exit(1)

sys.path.insert(0, str(Path(__file__).parent))

from src.bot.handlers import start, photo, text_message, done, batal, cmd_lokasi, cmd_tanggal, cmd_log, cmd_myid, cmd_update
from src.bot.conversation import build as build_conv


def main() -> None:
    app = Application.builder().token(TOKEN).build()

    app.add_handler(build_conv())           # guided flow — harus duluan
    app.add_handler(CommandHandler("start",   start))
    app.add_handler(CommandHandler("done",    done))
    app.add_handler(CommandHandler("batal",   batal))
    app.add_handler(CommandHandler("lokasi",  cmd_lokasi))
    app.add_handler(CommandHandler("tanggal", cmd_tanggal))
    app.add_handler(CommandHandler("log",     cmd_log))
    app.add_handler(CommandHandler("myid",   cmd_myid))
    app.add_handler(CommandHandler("update", cmd_update))
    app.add_handler(MessageHandler(filters.PHOTO,                   photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message))

    async def _on_startup(app):
        if ADMIN_CHAT_ID := os.getenv("ADMIN_CHAT_ID", ""):
            try:
                await app.bot.send_message(
                    chat_id=ADMIN_CHAT_ID,
                    text="✅ *SmartReport Bot* aktif dan siap digunakan.",
                    parse_mode="Markdown",
                )
            except Exception:
                pass

    print("Bot berjalan... (Ctrl+C untuk stop)")
    app.run_polling(drop_pending_updates=True, post_init=_on_startup)


if __name__ == "__main__":
    main()
