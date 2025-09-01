import asyncio
import logging
from typing import Dict, Any, Optional
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import httpx
from config.settings import get_settings

logger = logging.getLogger(__name__)

class TelegramBot:
    """Telegram bot for trading system notifications and approvals"""
    
    def __init__(self):
        self.settings = get_settings()
        self.bot_token = self.settings.telegram_bot_token
        self.chat_id = self.settings.telegram_chat_id
        self.application: Optional[Application] = None
        self.bot: Optional[Bot] = None
        self.api_base_url = f"http://localhost:{self.settings.port}/api"
    
    async def initialize(self):
        """Initialize the Telegram bot"""
        try:
            self.application = Application.builder().token(self.bot_token).build()
            self.bot = self.application.bot
            
            # Setup handlers
            await self._setup_handlers()
            
            logger.info("Telegram bot initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing Telegram bot: {str(e)}")
            raise
    
    async def _setup_handlers(self):
        """Setup command and callback handlers"""
        # Command handlers
        self.application.add_handler(CommandHandler("start", self._start_command))
        self.application.add_handler(CommandHandler("status", self._status_command))
        self.application.add_handler(CommandHandler("positions", self._positions_command))
        self.application.add_handler(CommandHandler("pnl", self._pnl_command))
        self.application.add_handler(CommandHandler("halt", self._halt_command))
        self.application.add_handler(CommandHandler("resume", self._resume_command))
        
        # Callback query handler for inline buttons
        self.application.add_handler(CallbackQueryHandler(self._handle_callback))
    
    async def start(self):
        """Start the Telegram bot"""
        try:
            await self.application.initialize()
            await self.application.start()
            await self.application.updater.start_polling()
            
            logger.info("Telegram bot started and polling for updates")
            
        except Exception as e:
            logger.error(f"Error starting Telegram bot: {str(e)}")
            raise
    
    async def stop(self):
        """Stop the Telegram bot"""
        try:
            if self.application:
                await self.application.updater.stop()
                await self.application.stop()
                await self.application.shutdown()
            
            logger.info("Telegram bot stopped")
            
        except Exception as e:
            logger.error(f"Error stopping Telegram bot: {str(e)}")
    
    async def send_signal_notification(self, signal: Dict[str, Any]):
        """Send signal approval notification with inline buttons"""
        try:
            signal_id = signal['id']
            symbol = signal['symbol']
            signal_type = signal['signal_type']
            reason = signal.get('reason', 'No reason provided')
            stop_loss = signal.get('stop_loss', 'N/A')
            take_profit = signal.get('take_profit', 'N/A')
            margin_required = signal.get('margin_required', 0)
            expiry_time = signal.get('expiry_time', 'N/A')
            
            message = f"""
🔔 **New Trading Signal**

📈 **Symbol:** {symbol}
📊 **Type:** {signal_type.upper()}
💡 **Reason:** {reason}
🛑 **Stop Loss:** {stop_loss}
🎯 **Take Profit:** {take_profit}
💰 **Margin Required:** ₹{margin_required:,.2f}
⏰ **Expires:** {expiry_time}

Please approve or reject this signal:
            """
            
            # Create inline keyboard
            keyboard = [
                [
                    InlineKeyboardButton("✅ Approve", callback_data=f"approve:{signal_id}"),
                    InlineKeyboardButton("❌ Reject", callback_data=f"reject:{signal_id}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
            logger.info(f"Signal notification sent for signal {signal_id}")
            
        except Exception as e:
            logger.error(f"Error sending signal notification: {str(e)}")
    
    async def send_execution_confirmation(self, signal: Dict[str, Any], order_id: str):
        """Send order execution confirmation"""
        try:
            symbol = signal['symbol']
            signal_type = signal['signal_type']
            quantity = signal.get('quantity', 'N/A')
            price = signal.get('price', 'N/A')
            
            message = f"""
✅ *Order Executed*

📈 *Symbol:* {symbol}
📊 *Type:* {signal_type.upper()}
📦 *Quantity:* {quantity}
💵 *Price:* ₹{price}
🆔 *Order ID:* {order_id}

Order has been successfully placed with the broker.
            """
            
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode='Markdown'
            )
            
            logger.info(f"Execution confirmation sent for order {order_id}")
            
        except Exception as e:
            logger.error(f"Error sending execution confirmation: {str(e)}")
    
    async def send_risk_alert(self, alert_type: str, message: str, severity: str = "medium"):
        """Send risk management alerts"""
        try:
            emoji_map = {
                "low": "ℹ️",
                "medium": "⚠️", 
                "high": "🚨",
                "critical": "🔴"
            }
            
            emoji = emoji_map.get(severity, "⚠️")
            
            alert_message = f"""
{emoji} **Risk Alert**

**Type:** {alert_type}
**Severity:** {severity.upper()}
**Message:** {message}

Please review your positions and risk parameters.
            """
            
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=alert_message,
                parse_mode='Markdown'
            )
            
            logger.info(f"Risk alert sent: {alert_type}")
            
        except Exception as e:
            logger.error(f"Error sending risk alert: {str(e)}")
    
    async def send_signal_expiry_notification(self, signal: Dict[str, Any]):
        """Send notification when signal expires"""
        try:
            symbol = signal['symbol']
            signal_type = signal['signal_type']
            signal_id = signal['id']
            
            message = f"""
⏰ **Signal Expired**

📈 **Symbol:** {symbol}
📊 **Type:** {signal_type.upper()}
🆔 **Signal ID:** {signal_id}

Signal has expired without approval.
            """
            
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Error sending expiry notification: {str(e)}")
    
    async def _start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        welcome_message = """
🤖 **Stock Trading System Bot**

Welcome! This bot will send you trading signals and system notifications.

**Available Commands:**
/status - System status
/positions - Current positions
/pnl - Profit & Loss summary
/halt - Emergency halt trading
/resume - Resume trading

The bot will automatically send you signals for approval.
        """
        
        await update.message.reply_text(welcome_message, parse_mode='Markdown')
    
    async def _status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.api_base_url}/system/status")
                
                if response.status_code == 200:
                    data = response.json()
                    
                    message = f"""
📊 **System Status**

🔄 **Auto Trade:** {'✅ Enabled' if data.get('auto_trade') else '❌ Disabled'}
🔗 **IIFL API:** {'✅ Connected' if data.get('iifl_api_connected') else '❌ Disconnected'}
💾 **Database:** {'✅ Connected' if data.get('database_connected') else '❌ Disconnected'}
📈 **Max Positions:** {data.get('max_positions', 'N/A')}
⚠️ **Risk Per Trade:** {data.get('risk_per_trade', 0):.1%}
🛑 **Max Daily Loss:** {data.get('max_daily_loss', 0):.1%}
                    """
                else:
                    message = "❌ Unable to fetch system status"
            
            await update.message.reply_text(message, parse_mode='Markdown')
            
        except Exception as e:
            await update.message.reply_text(f"Error fetching status: {str(e)}")
    
    async def _positions_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /positions command"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.api_base_url}/portfolio/positions")
                
                if response.status_code == 200:
                    data = response.json()
                    positions = data.get('positions', [])
                    total_pnl = data.get('total_pnl', 0)
                    
                    if positions:
                        message = f"📈 **Current Positions** (Total PnL: ₹{total_pnl:,.2f})\n\n"
                        
                        for pos in positions[:10]:  # Limit to 10 positions
                            symbol = pos.get('symbol', 'N/A')
                            qty = pos.get('quantity', 0)
                            pnl = pos.get('pnl', 0)
                            message += f"• **{symbol}:** {qty} shares, PnL: ₹{pnl:,.2f}\n"
                    else:
                        message = "📈 **No open positions**"
                else:
                    message = "❌ Unable to fetch positions"
            
            await update.message.reply_text(message, parse_mode='Markdown')
            
        except Exception as e:
            await update.message.reply_text(f"Error fetching positions: {str(e)}")
    
    async def _pnl_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /pnl command"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.api_base_url}/reports/pnl/daily")
                
                if response.status_code == 200:
                    data = response.json()
                    
                    daily_pnl = data.get('daily_pnl', 0)
                    cumulative_pnl = data.get('cumulative_pnl', 0)
                    total_trades = data.get('total_trades', 0)
                    win_rate = data.get('win_rate', 0)
                    
                    message = f"""
💰 **P&L Summary**

📅 **Today's PnL:** ₹{daily_pnl:,.2f}
📈 **Cumulative PnL:** ₹{cumulative_pnl:,.2f}
🔢 **Total Trades:** {total_trades}
🎯 **Win Rate:** {win_rate:.1%}
                    """
                else:
                    message = "❌ Unable to fetch P&L data"
            
            await update.message.reply_text(message, parse_mode='Markdown')
            
        except Exception as e:
            await update.message.reply_text(f"Error fetching P&L: {str(e)}")
    
    async def _halt_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /halt command"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(f"{self.api_base_url}/system/halt")
                
                if response.status_code == 200:
                    message = "🛑 **Trading Halted**\n\nAll trading activities have been stopped."
                else:
                    message = "❌ Unable to halt trading"
            
            await update.message.reply_text(message, parse_mode='Markdown')
            
        except Exception as e:
            await update.message.reply_text(f"Error halting trading: {str(e)}")
    
    async def _resume_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /resume command"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(f"{self.api_base_url}/system/resume")
                
                if response.status_code == 200:
                    message = "✅ **Trading Resumed**\n\nTrading activities have been resumed."
                else:
                    message = "❌ Unable to resume trading"
            
            await update.message.reply_text(message, parse_mode='Markdown')
            
        except Exception as e:
            await update.message.reply_text(f"Error resuming trading: {str(e)}")
    
    async def _handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline button callbacks"""
        try:
            query = update.callback_query
            await query.answer()
            
            callback_data = query.data
            action, signal_id = callback_data.split(':')
            
            async with httpx.AsyncClient() as client:
                if action == "approve":
                    response = await client.post(f"{self.api_base_url}/signals/{signal_id}/approve")
                elif action == "reject":
                    response = await client.post(f"{self.api_base_url}/signals/{signal_id}/reject")
                else:
                    await query.edit_message_text("❌ Invalid action")
                    return
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get("success"):
                        await query.edit_message_text(
                            f"✅ Signal {signal_id} {action}ed successfully",
                            parse_mode='Markdown'
                        )
                    else:
                        await query.edit_message_text(
                            f"❌ Failed to {action} signal: {result.get('message', 'Unknown error')}",
                            parse_mode='Markdown'
                        )
                else:
                    await query.edit_message_text(f"❌ API error: {response.status_code}")
            
        except Exception as e:
            logger.error(f"Error handling callback: {str(e)}")
            await query.edit_message_text(f"❌ Error: {str(e)}")
