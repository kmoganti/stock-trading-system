#!/usr/bin/env python3
"""Test Telegram approval flow for BUY and SELL signals"""

import asyncio
import httpx
import os
from datetime import datetime, timedelta
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, ContextTypes
from models.database import AsyncSessionLocal
from models.signals import Signal, SignalType, SignalStatus
from sqlalchemy import select

BOT_TOKEN = "8231093244:AAEC4uLXUhx1SJylPV-bYYp5PrM2Eo_ShfA"
CHAT_ID = "8062626973"
API_BASE = "http://localhost:8000"
API_KEY = "test-api-key"

async def create_test_signals():
    """Create test BUY and SELL signals"""
    print("=" * 80)
    print("Creating test signals...")
    print("=" * 80)
    
    async with AsyncSessionLocal() as session:
        # Create BUY signal
        buy_signal = Signal(
            symbol="TCS",
            signal_type=SignalType.BUY,
            price=3850.50,
            quantity=2,
            stop_loss=3820.0,
            take_profit=3900.0,
            margin_required=7701.0,
            status=SignalStatus.PENDING,
            expiry_time=datetime.now() + timedelta(hours=1),
            reason="Test BUY signal for day trading approval flow"
        )
        session.add(buy_signal)
        await session.flush()
        buy_id = buy_signal.id
        
        # Create SELL signal
        sell_signal = Signal(
            symbol="INFY",
            signal_type=SignalType.SELL,
            price=1650.25,
            quantity=5,
            stop_loss=1670.0,
            take_profit=1620.0,
            margin_required=8251.25,
            status=SignalStatus.PENDING,
            expiry_time=datetime.now() + timedelta(hours=1),
            reason="Test SELL signal for day trading approval flow"
        )
        session.add(sell_signal)
        await session.flush()
        sell_id = sell_signal.id
        
        await session.commit()
        
    print(f"✅ Created BUY signal #{buy_id}: TCS @ ₹3850.50")
    print(f"✅ Created SELL signal #{sell_id}: INFY @ ₹1650.25")
    return buy_id, sell_id

async def send_telegram_notifications(buy_id: int, sell_id: int):
    """Send Telegram notifications for both signals"""
    print("\n" + "=" * 80)
    print("Sending Telegram notifications...")
    print("=" * 80)
    
    bot = Bot(token=BOT_TOKEN)
    
    # Send BUY signal notification
    buy_message = (
        f"🔔 <b>New Trading Signal (BUY)</b>\n\n"
        f"Symbol: <b>TCS</b>\n"
        f"Action: <b>BUY</b>\n"
        f"Price: ₹3850.50\n"
        f"Quantity: 2\n"
        f"Stop Loss: ₹3820.00\n"
        f"Take Profit: ₹3900.00\n"
        f"Margin: ₹7701.00\n\n"
        f"Signal ID: #{buy_id}"
    )
    
    buy_keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"APPROVE:{buy_id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"REJECT:{buy_id}")
        ]
    ])
    
    await bot.send_message(
        chat_id=CHAT_ID,
        text=buy_message,
        parse_mode="HTML",
        reply_markup=buy_keyboard
    )
    print(f"✅ Sent BUY signal notification for #{buy_id}")
    
    # Send SELL signal notification
    sell_message = (
        f"🔔 <b>New Trading Signal (SELL)</b>\n\n"
        f"Symbol: <b>INFY</b>\n"
        f"Action: <b>SELL</b>\n"
        f"Price: ₹1650.25\n"
        f"Quantity: 5\n"
        f"Stop Loss: ₹1670.00\n"
        f"Take Profit: ₹1620.00\n"
        f"Margin: ₹8251.25\n\n"
        f"Signal ID: #{sell_id}"
    )
    
    sell_keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"APPROVE:{sell_id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"REJECT:{sell_id}")
        ]
    ])
    
    await bot.send_message(
        chat_id=CHAT_ID,
        text=sell_message,
        parse_mode="HTML",
        reply_markup=sell_keyboard
    )
    print(f"✅ Sent SELL signal notification for #{sell_id}")

async def handle_approval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle approval/rejection button clicks"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    action, signal_id = data.split(":")
    signal_id = int(signal_id)
    
    print(f"\n{'=' * 80}")
    print(f"✅ Button clicked: {action} for Signal #{signal_id}")
    print(f"{'=' * 80}")
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            if action == "APPROVE":
                url = f"{API_BASE}/api/signals/{signal_id}/approve"
                print(f"📡 Calling: POST {url}")
                response = await client.post(
                    url,
                    headers={"X-API-Key": API_KEY}
                )
                
                if response.status_code == 504:
                    # Timeout - check signal status directly
                    print("⏱️ API timed out - checking signal status...")
                    async with AsyncSessionLocal() as session:
                        result = await session.execute(
                            select(Signal).where(Signal.id == signal_id)
                        )
                        signal = result.scalar_one_or_none()
                        
                        if signal and signal.status == SignalStatus.APPROVED:
                            await query.edit_message_text(
                                text=f"{query.message.text}\n\n✅ <b>APPROVED</b> (Status confirmed)",
                                parse_mode="HTML"
                            )
                            print(f"✅ Signal #{signal_id} confirmed APPROVED in database")
                        else:
                            await query.edit_message_text(
                                text=f"{query.message.text}\n\n⏱️ <b>Processing...</b> (API timeout - check status later)",
                                parse_mode="HTML"
                            )
                            print(f"⏱️ Signal #{signal_id} still processing")
                    return
                
                response.raise_for_status()
                result = response.json()
                
                await query.edit_message_text(
                    text=f"{query.message.text}\n\n✅ <b>APPROVED</b>",
                    parse_mode="HTML"
                )
                print(f"✅ Signal #{signal_id} approved successfully")
                print(f"Response: {result}")
                
            elif action == "REJECT":
                url = f"{API_BASE}/api/signals/{signal_id}/reject"
                print(f"📡 Calling: POST {url}")
                response = await client.post(
                    url,
                    headers={"X-API-Key": API_KEY},
                    params={"reason": "Manual rejection via Telegram"}
                )
                
                if response.status_code == 504:
                    print("⏱️ API timed out - checking signal status...")
                    async with AsyncSessionLocal() as session:
                        result = await session.execute(
                            select(Signal).where(Signal.id == signal_id)
                        )
                        signal = result.scalar_one_or_none()
                        
                        if signal and signal.status == SignalStatus.REJECTED:
                            await query.edit_message_text(
                                text=f"{query.message.text}\n\n❌ <b>REJECTED</b> (Status confirmed)",
                                parse_mode="HTML"
                            )
                            print(f"✅ Signal #{signal_id} confirmed REJECTED in database")
                        else:
                            await query.edit_message_text(
                                text=f"{query.message.text}\n\n⏱️ <b>Processing...</b> (API timeout)",
                                parse_mode="HTML"
                            )
                            print(f"⏱️ Signal #{signal_id} still processing")
                    return
                
                response.raise_for_status()
                result = response.json()
                
                await query.edit_message_text(
                    text=f"{query.message.text}\n\n❌ <b>REJECTED</b>",
                    parse_mode="HTML"
                )
                print(f"✅ Signal #{signal_id} rejected successfully")
                print(f"Response: {result}")
                
    except httpx.TimeoutException as e:
        print(f"❌ Timeout error: {e}")
        await query.edit_message_text(
            text=f"{query.message.text}\n\n⏱️ <b>Timeout</b> - Please check signal status manually",
            parse_mode="HTML"
        )
    except Exception as e:
        print(f"❌ Error handling callback: {e}")
        import traceback
        traceback.print_exc()
        await query.edit_message_text(
            text=f"{query.message.text}\n\n❌ <b>Error:</b> {type(e).__name__}",
            parse_mode="HTML"
        )

async def start_bot():
    """Start Telegram bot to handle button clicks"""
    print("\n" + "=" * 80)
    print("🤖 Starting Telegram Bot Polling...")
    print("=" * 80)
    print("Bot will listen for approval/rejection button clicks")
    print("Press Ctrl+C to stop")
    print("=" * 80)
    print()
    
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CallbackQueryHandler(handle_approval))
    
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    
    print("✅ Bot is now polling for updates...")
    print("📱 Try clicking the Approve/Reject buttons in Telegram now!")
    print()
    
    # Keep running until interrupted
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\n\n🛑 Stopping bot...")
        await application.updater.stop()
        await application.stop()
        await application.shutdown()
        print("✅ Bot stopped")

async def main():
    """Main test flow"""
    # Step 1: Create test signals
    buy_id, sell_id = await create_test_signals()
    
    # Step 2: Send Telegram notifications
    await send_telegram_notifications(buy_id, sell_id)
    
    print("\n" + "=" * 80)
    print("📋 Test Setup Complete!")
    print("=" * 80)
    print(f"BUY Signal: #{buy_id} (TCS)")
    print(f"SELL Signal: #{sell_id} (INFY)")
    print("\nCheck your Telegram for the notifications!")
    print("=" * 80)
    
    # Step 3: Start bot
    await start_bot()

if __name__ == "__main__":
    asyncio.run(main())
