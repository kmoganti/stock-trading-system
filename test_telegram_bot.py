#!/usr/bin/env python3
"""
Test script for Telegram bot functionality
"""
import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from telegram_bot.bot import TelegramBot
from datetime import datetime, timedelta
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_telegram_bot():
    """Test telegram bot with a fake signal"""
    try:
        # Initialize bot
        bot = TelegramBot()
        await bot.initialize()
        
        # Create a test signal
        test_signal = {
            'id': 'TEST_001',
            'symbol': 'RELIANCE',
            'signal_type': 'buy',
            'reason': 'Strong bullish momentum with RSI oversold condition',
            'price': 2450.75,
            'quantity': 10,
            'stop_loss': 2400.00,
            'take_profit': 2550.00,
            'margin_required': 24507.50,
            'expiry_time': (datetime.now() + timedelta(minutes=15)).isoformat(),
            'created_at': datetime.now().isoformat()
        }
        
        logger.info("Sending test signal notification...")
        await bot.send_signal_notification(test_signal)
        
        # Send a test risk alert
        logger.info("Sending test risk alert...")
        await bot.send_risk_alert(
            alert_type="Daily Loss Limit",
            message="Daily loss has reached 3.5% of capital. Approaching 5% limit.",
            severity="medium"
        )
        
        # Send test execution confirmation
        logger.info("Sending test execution confirmation...")
        await bot.send_execution_confirmation(test_signal, "ORD_12345")
        
        logger.info("All test messages sent successfully!")
        logger.info("Bot is ready to receive commands. Try:")
        logger.info("- /start")
        logger.info("- /status")
        logger.info("- /positions")
        logger.info("- /pnl")
        
        # Keep bot running for testing
        logger.info("Bot is now running. Press Ctrl+C to stop.")
        await bot.start()
        
    except KeyboardInterrupt:
        logger.info("Stopping bot...")
        await bot.stop()
    except Exception as e:
        logger.error(f"Error testing telegram bot: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(test_telegram_bot())
