# Scheduler Hang Issues - Fixed

## Problem
The server was hanging when scheduled jobs were running due to:
1. **Blocking IIFL API calls** during service initialization
2. **No timeout protection** on scheduled job execution
3. **Cascading failures** when one API call hangs, blocking all subsequent jobs
4. **Service initialization in synchronous context** causing event loop blocks

## Root Causes

### 1. Service Initialization Blocking
```python
# BEFORE (BLOCKING):
self.iifl_api = IIFLAPIService()  # Could hang indefinitely
self.data_fetcher = DataFetcher(self.iifl_api)
self.strategy_service = StrategyService(self.data_fetcher)
```

### 2. No Timeout on Job Execution
```python
# BEFORE (NO TIMEOUT):
for symbol in symbols:
    signals = await self.strategy_service.generate_signals(...)  # Could hang forever
```

### 3. No Timeout on Scheduled Tasks
```python
# BEFORE (NO TIMEOUT):
data = await fetcher.get_historical_data(...)  # Could hang indefinitely
```

## Solutions Implemented

### 1. Timeout-Protected Service Initialization
**File:** `services/scheduler.py`

```python
# AFTER (WITH TIMEOUT):
async def initialize_services(self):
    try:
        # Initialize IIFL API with 10-second timeout
        self.iifl_api = await asyncio.wait_for(
            asyncio.to_thread(IIFLAPIService),
            timeout=10.0
        )
        self.data_fetcher = DataFetcher(self.iifl_api)
        self.strategy_service = StrategyService(self.data_fetcher)
        logger.info("✅ Trading services initialized successfully")
    except asyncio.TimeoutError:
        logger.warning("⏱️ IIFL API initialization timed out")
        # Set to None - services will reinitialize on first job run
        self.iifl_api = None
        self.data_fetcher = None
        self.strategy_service = None
```

### 2. Lazy Service Initialization
Added `_ensure_services_initialized()` method that checks and initializes services before each job run:

```python
async def _ensure_services_initialized(self):
    """Ensure services are initialized before running jobs"""
    if self.strategy_service is None:
        logger.info("Services not initialized, initializing now...")
        try:
            self.iifl_api = IIFLAPIService()
            self.data_fetcher = DataFetcher(self.iifl_api)
            self.strategy_service = StrategyService(self.data_fetcher)
            logger.info("✅ Services initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize services: {e}")
            raise RuntimeError("Cannot execute job: services not available")
    return True
```

### 3. Timeout Protection on All Job Executions

#### Day Trading Strategy
```python
# Service initialization timeout (10s)
await asyncio.wait_for(
    self._ensure_services_initialized(),
    timeout=10.0
)

# Per-symbol timeout (30s)
signals = await asyncio.wait_for(
    self.strategy_service.generate_signals(...),
    timeout=30.0
)

# Overall strategy timeout (10 minutes - from config)
await asyncio.wait_for(
    generate_all_signals(),
    timeout=config.timeout_minutes * 60
)
```

#### Short Selling Strategy
- Service initialization: 10s timeout
- Per-symbol analysis: 60s timeout
- Overall strategy: 15 minutes timeout

#### Short Term Strategy
- Service initialization: 10s timeout
- Per-symbol generation: 45s timeout
- Overall strategy: 20 minutes timeout

#### Long Term Strategy
- Service initialization: 10s timeout
- Per-symbol generation: 60s timeout
- Overall strategy: 30 minutes timeout

### 4. Timeout Protection on Scheduled Tasks
**File:** `services/scheduler_tasks.py`

#### Watchlist Prefetch
```python
# Overall prefetch timeout: 15 minutes
await asyncio.wait_for(
    _execute_prefetch(),
    timeout=15 * 60
)

# Per-symbol fetch timeout: 60 seconds
await asyncio.wait_for(
    _fetch_symbol_data(fetcher, sym),
    timeout=60.0
)
```

#### Intraday Watchlist Builder
```python
# Watchlist building timeout: 10 minutes
await asyncio.wait_for(
    _execute_watchlist_build(),
    timeout=10 * 60
)
```

## Benefits

### ✅ No More Server Hangs
- All operations have maximum execution time limits
- Failed operations don't block subsequent jobs
- Server remains responsive even if IIFL API is slow

### ✅ Graceful Degradation
- If service initialization fails, job is skipped with logged warning
- Individual symbol failures don't stop the entire strategy execution
- Services can reinitialize on next job run

### ✅ Better Monitoring
- Clear timeout warnings in logs
- Execution stats track timeouts separately
- Easy to identify problematic symbols or operations

### ✅ Resource Protection
- Prevents event loop starvation
- Limits concurrent API calls (semaphores)
- Prevents cascading failures

## Configuration

### Strategy Timeouts
Configured in `services/scheduler.py` via `ScheduleConfig`:

| Strategy | Timeout | Frequency |
|----------|---------|-----------|
| Day Trading | 10 min | Every 5 min |
| Short Selling | 15 min | Every 30 min |
| Short Term | 20 min | Every 2 hours |
| Long Term | 30 min | Daily |

### Task Timeouts
- **Watchlist Prefetch**: 15 minutes overall, 60s per symbol
- **Intraday Watchlist Build**: 10 minutes
- **Service Initialization**: 10 seconds

## Testing

### Manual Test
```bash
# 1. Start server with scheduler enabled
ENABLE_SCHEDULER=true python -m uvicorn main:app --host 0.0.0.0 --port 8000

# 2. Monitor logs for scheduled job execution
tail -f logs/trading_*.log | grep -E "(Executing|completed|timeout|failed)"

# 3. Verify no hangs occur during:
#    - Service initialization
#    - Strategy execution
#    - Scheduled tasks
```

### Automated Test
```python
# Test timeout protection
import asyncio

async def test_timeout():
    from services.scheduler import get_trading_scheduler
    
    scheduler = get_trading_scheduler()
    await scheduler.initialize_services()
    
    # Trigger a strategy execution
    await scheduler.execute_day_trading_strategy()
    
    # Check execution stats
    stats = scheduler.get_execution_stats()
    print(stats)

asyncio.run(test_timeout())
```

## Monitoring

### Log Patterns to Watch
- `⏱️` - Timeout occurred
- `❌` - Operation failed
- `✅` - Operation succeeded
- `⚠️` - Warning (initialization failed, will retry)

### Success Indicators
```
✅ Trading services initialized successfully
✅ Day trading strategy completed: 15 signals in 45.23s
✅ Short term strategy completed: 8 signals in 120.45s
```

### Failure Indicators
```
⏱️ IIFL API initialization timed out
⏱️ Timeout generating day trading signals for RELIANCE
❌ Day trading strategy failed: Cannot execute job: services not available
```

## Future Improvements

1. **Dynamic Timeout Adjustment**
   - Adjust timeouts based on historical execution times
   - Increase timeout during market volatility

2. **Circuit Breaker Pattern**
   - Temporarily disable jobs after repeated failures
   - Auto-recovery after cooldown period

3. **Health Checks**
   - Periodic IIFL API health checks
   - Skip job execution if API is known to be down

4. **Retry Logic**
   - Retry failed symbol processing with exponential backoff
   - Separate retry queue for timed-out operations

5. **Performance Metrics**
   - Track timeout frequency per symbol
   - Alert when timeout rate exceeds threshold
   - Dashboard for real-time job status

## Related Files Modified

1. `services/scheduler.py` - Main scheduler with timeout protection
2. `services/scheduler_tasks.py` - Scheduled tasks with timeout protection
3. `api/signals.py` - Approval/rejection endpoints with TEST_MODE
4. `main.py` - Scheduler initialization (no changes needed)

## Notes

- **TEST_MODE**: Set `TEST_MODE=true` environment variable to bypass IIFL calls for testing
- **Scheduler Disable**: Set `ENABLE_SCHEDULER=false` to disable all scheduled jobs
- **Log Level**: Adjust `LOG_LEVEL_SCHEDULER=DEBUG` for detailed execution logs
