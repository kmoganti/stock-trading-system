#!/usr/bin/env python3
"""
Run the Telegram bot with background monitoring tasks.

Requirements:
- TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID in environment
- API server running (so the bot can poll /api endpoints)
"""

import asyncio
import logging
from pathlib import Path
import sys

# Ensure project root on path
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from telegram_bot.bot import TelegramBot  # noqa: E402
from telegram_bot.handlers import setup_handlers  # noqa: E402


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    bot = TelegramBot()
    # Setup handlers and background monitoring tasks
    await setup_handlers(bot)
    # Start polling
    await bot.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
