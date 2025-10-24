#!/usr/bin/env python3
"""
External Telegram Bot Service
Run as: python services/external_telegram_bot.py
"""

import asyncio
import logging
import os
import sys
import signal
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.settings import get_settings
from telegram_bot.bot import TelegramBot
from telegram_bot.handlers import setup_handlers

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/telegram_bot.log', mode='a')
    ]
)
logger = logging.getLogger(__name__)

class ExternalTelegramBotService:
    """External Telegram Bot Service Runner"""
    
    def __init__(self):
        self.bot: TelegramBot = None
        self.running = False
        self.settings = get_settings()
        
    async def start(self):
        """Start the Telegram bot service"""
        try:
            # Check if bot is enabled and configured
            telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
            telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")
            
            if not telegram_token or not telegram_chat_id:
                logger.error("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID")
                return False
                
            if not getattr(self.settings, "telegram_bot_enabled", False):
                logger.warning("Telegram bot is disabled in settings")
                return False
            
            logger.info("Starting External Telegram Bot Service...")
            
            # Create and setup bot
            self.bot = TelegramBot()
            await setup_handlers(self.bot)
            await self.bot.start()
            
            self.running = True
            logger.info("🤖 Telegram Bot Service started successfully!")
            
            # Send startup notification
            try:
                await self.bot.bot.send_message(
                    chat_id=telegram_chat_id,
                    text="🚀 <b>Telegram Bot Service Started</b>\n\nBot is now online and ready to receive trading notifications.",
                    parse_mode='HTML'
                )
            except Exception as e:
                logger.warning(f"Could not send startup notification: {e}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to start Telegram bot service: {e}")
            return False
    
    async def stop(self):
        """Stop the Telegram bot service"""
        try:
            if self.bot and self.running:
                logger.info("Stopping Telegram Bot Service...")
                await self.bot.stop()
                self.running = False
                logger.info("Telegram Bot Service stopped")
        except Exception as e:
            logger.error(f"Error stopping Telegram bot service: {e}")
    
    async def run_forever(self):
        """Run the service until interrupted"""
        if not await self.start():
            return
        
        try:
            # Keep running until interrupted
            while self.running:
                await asyncio.sleep(1)
                
        except (KeyboardInterrupt, SystemExit):
            logger.info("Received shutdown signal")
        finally:
            await self.stop()

def setup_signal_handlers(service):
    """Setup signal handlers for graceful shutdown"""
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}")
        service.running = False
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

async def main():
    """Main entry point"""
    # Ensure logs directory exists
    os.makedirs('logs', exist_ok=True)
    
    logger.info("Initializing External Telegram Bot Service...")
    
    service = ExternalTelegramBotService()
    setup_signal_handlers(service)
    
    try:
        await service.run_forever()
    except Exception as e:
        logger.error(f"Service error: {e}")
        await service.stop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Service interrupted by user")
    except Exception as e:
        logger.error(f"Service failed: {e}")
        sys.exit(1)