import asyncio
import logging
from typing import Dict, Any
from .bot import TelegramBot

logger = logging.getLogger(__name__)

async def setup_handlers(telegram_bot: TelegramBot):
    """Setup additional handlers and background tasks"""
    try:
        # Initialize the bot
        await telegram_bot.initialize()
        
        # Start background tasks
        asyncio.create_task(signal_monitoring_task(telegram_bot))
        asyncio.create_task(risk_monitoring_task(telegram_bot))
        
        logger.info("Telegram bot handlers setup completed")
        
    except Exception as e:
        logger.error(f"Error setting up Telegram handlers: {str(e)}")
        raise

async def signal_monitoring_task(telegram_bot: TelegramBot):
    """Background task to monitor for new signals"""
    import httpx
    
    processed_signals = set()
    
    while True:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{telegram_bot.api_base_url}/signals?status=pending&limit=10")
                
                if response.status_code == 200:
                    signals = response.json()
                    
                    for signal in signals:
                        signal_id = signal['id']
                        
                        # Only send notification for new signals
                        if signal_id not in processed_signals:
                            await telegram_bot.send_signal_notification(signal)
                            processed_signals.add(signal_id)
                
                # Clean up processed signals periodically
                if len(processed_signals) > 1000:
                    processed_signals.clear()
                
        except Exception as e:
            logger.error(f"Error in signal monitoring task: {str(e)}")
        
        # Check every 30 seconds
        await asyncio.sleep(30)

async def risk_monitoring_task(telegram_bot: TelegramBot):
    """Background task to monitor risk events"""
    import httpx
    
    last_event_id = 0
    
    while True:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{telegram_bot.api_base_url}/risk/events?limit=5")
                
                if response.status_code == 200:
                    events = response.json()
                    
                    for event in events:
                        event_id = event['id']
                        
                        # Only send alerts for new events
                        if event_id > last_event_id:
                            await telegram_bot.send_risk_alert(
                                event['event_type'],
                                event['message'],
                                event['severity']
                            )
                            last_event_id = event_id
                
        except Exception as e:
            logger.error(f"Error in risk monitoring task: {str(e)}")
        
        # Check every 60 seconds
        await asyncio.sleep(60)
