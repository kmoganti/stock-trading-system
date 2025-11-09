# Signal Persistence & Telegram Notification Fix

## Problem Summary

**User Report**: "Generated signals are getting deleted immediately. They are not waiting for approval. Even telegram messages are not coming."

### Root Cause Analysis:

1. **Signals Not Being Saved**: The optimized scheduler was generating signals but **never saving them to the database**
   - Signals were only logged, not persisted
   - No database session or OrderManager initialized in optimized scheduler
   - Signals existed only in memory and disappeared after scan completed

2. **No Telegram Notifications**: Without saved signals, no notifications were sent
   - TelegramNotifier was initialized but never called after signal generation
   - No integration between scheduler and notification system

## Solution Implemented

### 1. Added Database Session & OrderManager to Optimized Scheduler

**File**: `services/optimized_scheduler.py`

#### Changes to `__init__` method:
```python
def __init__(self):
    # ... existing code ...
    self.order_manager: Optional['OrderManager'] = None  # NEW
```

#### Changes to `initialize_services` method:
```python
async def initialize_services(self):
    """Initialize trading services with timeout protection"""
    try:
        logger.info("Initializing optimized scheduler services...")
        
        async def init_iifl_services():
            from models.database import AsyncSessionLocal
            from services.order_manager import OrderManager
            from services.risk import RiskService
            
            self.iifl_api = IIFLAPIService()
            self.data_fetcher = DataFetcher(self.iifl_api)
            self.strategy_service = StrategyService(self.data_fetcher)
            
            # NEW: Initialize OrderManager with database session
            db_session = AsyncSessionLocal()
            risk_service = RiskService(self.iifl_api, db_session)
            self.order_manager = OrderManager(
                iifl_service=self.iifl_api,
                risk_service=risk_service,
                data_fetcher=self.data_fetcher,
                db_session=db_session
            )
```

**Benefits**:
- OrderManager can now save signals to database
- Database session properly initialized
- Risk validation integrated
- Proper lifecycle management

### 2. Added Signal Persistence After Scan Completion

**File**: `services/optimized_scheduler.py` - `execute_unified_scan` method

#### Before (Signals Lost):
```python
# Flatten results and group by category
category_results = defaultdict(list)
for symbol_results in all_results:
    if isinstance(symbol_results, list):
        for result in symbol_results:
            if isinstance(result, AnalysisResult):
                category_results[result.category].extend(result.signals)

# Log summary
execution_time = (datetime.now() - start_time).total_seconds()
logger.info(f"✅ Unified scan completed in {execution_time:.2f}s")

for category, signals in category_results.items():
    logger.info(f"   • {category.value}: {len(signals)} signals")
```

#### After (Signals Saved):
```python
# Flatten results and group by category
category_results = defaultdict(list)
for symbol_results in all_results:
    if isinstance(symbol_results, list):
        for result in symbol_results:
            if isinstance(result, AnalysisResult):
                category_results[result.category].extend(result.signals)

# NEW: Save signals to database
total_signals_saved = 0
signal_notifications = []

if self.order_manager:
    for category, signals in category_results.items():
        for signal in signals:
            try:
                # Convert TradingSignal to dict for OrderManager
                signal_dict = {
                    'symbol': signal.symbol,
                    'signal_type': signal.signal_type,
                    'entry_price': signal.entry_price,
                    'stop_loss': signal.stop_loss,
                    'take_profit': signal.target_price,
                    'reason': f"{signal.strategy} - {category.value}",
                    'confidence': signal.confidence,
                    'strategy': signal.strategy,
                    'category': category.value
                }
                
                saved_signal = await self.order_manager.create_signal(signal_dict)
                if saved_signal:
                    total_signals_saved += 1
                    logger.info(f"💾 Saved signal: {saved_signal.symbol} {saved_signal.signal_type.value}")
                    
                    # Prepare Telegram notification
                    signal_notifications.append({
                        'symbol': signal.symbol,
                        'type': signal.signal_type.value,
                        'entry': signal.entry_price,
                        'sl': signal.stop_loss,
                        'target': signal.target_price,
                        'confidence': signal.confidence,
                        'strategy': signal.strategy,
                        'category': category.value
                    })
            except Exception as e:
                logger.error(f"❌ Failed to save signal for {signal.symbol}: {e}")
else:
    logger.warning("⚠️ OrderManager not initialized, signals not saved to database")
```

**Benefits**:
- Every generated signal is saved to database
- Signals get proper status (PENDING by default)
- Risk validation applied before saving
- Margin requirements calculated
- Expiry time set based on settings
- Error handling per signal (one failure doesn't stop others)

### 3. Added Telegram Notifications

**File**: `services/optimized_scheduler.py` - `execute_unified_scan` method

```python
# NEW: Send Telegram notifications for all saved signals
if signal_notifications and self.strategy_service and self.strategy_service._notifier:
    try:
        # Group by category for cleaner notifications
        category_groups = defaultdict(list)
        for notif in signal_notifications:
            category_groups[notif['category']].append(notif)
        
        for cat, notifs in category_groups.items():
            message = f"🔔 <b>{cat.replace('_', ' ').title()} Signals ({len(notifs)})</b>\n\n"
            for n in notifs:
                signal_emoji = "🟢" if n['type'].lower() == "buy" else "🔴"
                message += f"{signal_emoji} <b>{n['symbol']}</b> - {n['type'].upper()}\n"
                message += f"   Entry: ₹{n['entry']:.2f} | SL: ₹{n['sl']:.2f} | Target: ₹{n['target']:.2f}\n"
                message += f"   Strategy: {n['strategy']} | Confidence: {n['confidence']:.0%}\n\n"
            
            await self.strategy_service._notifier.send(message)
            logger.info(f"📱 Sent Telegram notification for {len(notifs)} {cat} signals")
    except Exception as e:
        logger.error(f"❌ Failed to send Telegram notifications: {e}")
```

**Notification Format**:
```
🔔 Day Trading Signals (3)

🟢 RELIANCE - BUY
   Entry: ₹2450.50 | SL: ₹2420.00 | Target: ₹2500.00
   Strategy: ema_crossover | Confidence: 75%

🟢 TCS - BUY
   Entry: ₹3580.25 | SL: ₹3550.00 | Target: ₹3650.00
   Strategy: momentum | Confidence: 82%

🔴 HDFCBANK - SELL
   Entry: ₹1650.75 | SL: ₹1670.00 | Target: ₹1620.00
   Strategy: bollinger_bands | Confidence: 68%
```

**Benefits**:
- Grouped by strategy category (Day Trading, Short Term, etc.)
- Clear signal type indicators (🟢 BUY / 🔴 SELL)
- All critical information at a glance
- Formatted for easy reading on mobile
- HTML formatting for better readability

## Signal Workflow After Fix

### 1. **Signal Generation** (Existing)
- Scheduler runs at configured intervals
- Fetches historical data for symbols
- Calculates technical indicators
- Generates signals based on strategies

### 2. **Signal Persistence** (NEW)
- Convert TradingSignal to dict
- Call `OrderManager.create_signal()`
- Risk validation performed
- Margin requirements calculated
- Signal saved to database with:
  - Status: PENDING (awaiting approval)
  - Expiry time: Current time + signal_timeout
  - Quantity: Calculated by risk management
  - All metadata (confidence, strategy, etc.)

### 3. **Telegram Notification** (NEW)
- Group signals by category
- Format message with all signal details
- Send to configured Telegram chat
- User receives immediate notification

### 4. **User Approval** (Existing, Now Works!)
- User views signals in dashboard `/signals`
- Reviews signal details
- Approves or rejects via UI
- If AUTO_TRADE=true, signals auto-execute
- If AUTO_TRADE=false, requires manual approval

### 5. **Signal Execution** (Existing)
- Approved signals sent to IIFL API
- Order placed on exchange
- Order ID tracked
- Position monitoring begins

## Testing

### 1. Verify Signal Persistence:
```bash
# Check database for signals
docker exec trading_postgres psql -U trading_user -d trading_system -c "SELECT id, symbol, signal_type, status, created_at FROM signals ORDER BY created_at DESC LIMIT 10;"
```

Expected: New signals appear in database after scanner runs

### 2. Verify Telegram Notifications:
- Ensure `TELEGRAM_BOT_TOKEN` is set in .env
- Ensure `TELEGRAM_CHAT_ID` is set in .env
- Wait for next scheduler run (check logs for "Starting unified scan")
- Check Telegram for notifications

### 3. Verify Dashboard Display:
```bash
# Open browser
http://localhost:8000/signals

# Or test API
curl http://localhost:8000/api/signals?status=pending
```

Expected: Signals show in UI with PENDING status

### 4. Check Scheduler Logs:
```bash
# Watch for signal saving
tail -f logs/strategy.log | grep -E "💾|📱|Saved signal|Telegram"
```

Expected output:
```
💾 Saved signal: RELIANCE BUY
💾 Saved signal: TCS BUY
📱 Sent Telegram notification for 2 day_trading signals
```

## Configuration

### Environment Variables:
```bash
# Enable auto-trading (signals execute automatically)
AUTO_TRADE=false  # Set to false for manual approval

# Signal timeout (seconds before signal expires)
SIGNAL_TIMEOUT=3600  # 1 hour

# Telegram (required for notifications)
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
TELEGRAM_NOTIFICATIONS_ENABLED=true

# Scheduler (required for signal generation)
ENABLE_SCHEDULER=true
```

### Scheduler Timing:
- **Frequent Scan**: Every 5 min (9:15 AM - 3:30 PM IST) - Day Trading & Short Selling
- **Regular Scan**: Every 2 hours (9:15 AM - 3:30 PM IST) - Short Term
- **Comprehensive Scan**: 10:00 AM, 2:00 PM IST - All Strategies
- **Daily Scan**: 4:00 PM IST - Long Term

## Troubleshooting

### Signals Not Appearing?

1. **Check OrderManager initialization**:
   ```bash
   grep "OrderManager not initialized" logs/strategy.log
   ```
   If found: Database connection issue

2. **Check signal generation**:
   ```bash
   grep "signals generated" logs/strategy.log
   ```
   If 0 signals: No trading opportunities found (normal)

3. **Check database connection**:
   ```bash
   docker exec trading_postgres psql -U trading_user -d trading_system -c "SELECT 1;"
   ```

### Telegram Not Working?

1. **Check bot token**:
   ```bash
   echo $TELEGRAM_BOT_TOKEN
   ```

2. **Check notifier initialization**:
   ```bash
   grep "Telegram" logs/server_simple.log
   ```

3. **Test notification manually**:
   ```python
   from services.telegram_notifier import TelegramNotifier
   notifier = TelegramNotifier()
   await notifier.send("Test message")
   ```

### Signals Disappearing?

- Check signal expiry time: `SIGNAL_TIMEOUT` setting
- Check if AUTO_TRADE=true (signals execute immediately)
- Check logs for "Signal expired" messages

## Summary

✅ **Fixed**:
1. Signals now saved to database (PENDING status)
2. Telegram notifications sent for all new signals
3. Signals await user approval (if AUTO_TRADE=false)
4. Proper error handling and logging

✅ **Benefits**:
- Users can review signals before execution
- Signal history preserved in database
- Telegram alerts for timely action
- Risk validation before persistence
- Margin requirements calculated

✅ **Next Steps**:
1. Test with real market conditions
2. Monitor first few scheduler runs
3. Verify Telegram notifications received
4. Check signal approval workflow

---

**Status**: ✅ **COMPLETED**  
**Server**: http://localhost:8000  
**Signals Dashboard**: http://localhost:8000/signals  
**Monitor Scheduler**: `./monitor_scheduler.sh`
