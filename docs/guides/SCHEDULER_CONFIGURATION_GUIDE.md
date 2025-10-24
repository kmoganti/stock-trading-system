# Trading Strategy Scheduler Configuration Guide
# ==============================================

## 🚀 Overview

The trading system now includes an advanced scheduler that automatically executes different trading strategies at optimal frequencies:

### Strategy Types & Frequencies

1. **Day Trading** (High Frequency)
   - Frequency: Every 5 minutes during market hours
   - Focus: Gap analysis, breakout patterns, scalping opportunities
   - Execution Window: 9:15 AM - 3:30 PM IST
   - Pre-market: Enabled for gap analysis

2. **Short Selling** (Frequent Monitoring)  
   - Frequency: Every 30 minutes during market hours
   - Focus: Overbought conditions, resistance rejections, bearish divergence
   - Execution Window: 9:15 AM - 4:00 PM IST (includes post-market)
   - Post-market: Enabled for end-of-day analysis

3. **Short Term** (Regular Intervals)
   - Frequency: Every 2 hours during extended hours
   - Focus: Swing trading signals, trend following
   - Execution Window: 9:15 AM, 11:15 AM, 1:15 PM, 3:15 PM, 5:15 PM IST
   - Pre/Post market: Both enabled

4. **Long Term** (Daily Analysis)
   - Frequency: Once daily after market close
   - Focus: Comprehensive trend analysis, position evaluation
   - Execution Time: 4:00 PM IST
   - Weekend: Enabled for research

## ⚙️ Configuration Parameters

### Basic Scheduler Control
ENABLE_SCHEDULER=true                    # Master switch for all scheduling
ENABLE_DAY_TRADING_SCHEDULER=true       # Enable day trading automation
ENABLE_SHORT_SELLING_SCHEDULER=true     # Enable short selling monitoring
ENABLE_SHORT_TERM_SCHEDULER=true        # Enable short-term signals
ENABLE_LONG_TERM_SCHEDULER=true         # Enable long-term analysis

### Strategy Frequencies (in minutes)
DAY_TRADING_FREQUENCY=5                 # Every 5 minutes (recommended: 5-15)
SHORT_SELLING_FREQUENCY=30              # Every 30 minutes (recommended: 15-60)
SHORT_TERM_FREQUENCY=120                # Every 2 hours (recommended: 60-240)
LONG_TERM_FREQUENCY=1440                # Once daily (recommended: 1440)

### Market Hours (IST timezone)
MARKET_START_HOUR=9                     # Market open hour
MARKET_START_MINUTE=15                  # Market open minute
MARKET_END_HOUR=15                      # Market close hour
MARKET_END_MINUTE=30                    # Market close minute

### Extended Hours Analysis
ENABLE_PRE_MARKET_ANALYSIS=true         # Pre-market gap analysis
ENABLE_POST_MARKET_ANALYSIS=true        # Post-market screening

### Resource Management
MAX_CONCURRENT_STRATEGIES=3             # Maximum parallel executions
STRATEGY_TIMEOUT_MINUTES=15             # Maximum execution time per strategy

## 📊 Frequency Optimization Guidelines

### High-Frequency Strategies (Day Trading & Short Selling)
- **Optimal Range**: 5-30 minutes
- **Considerations**: 
  - Market volatility (increase frequency during high volatility)
  - System resources (reduce if performance issues)
  - Signal quality (monitor hit rates)

### Medium-Frequency Strategies (Short Term)  
- **Optimal Range**: 1-4 hours
- **Considerations**:
  - Market trends (increase during trending markets)
  - Signal persistence (ensure signals remain valid)
  - Resource efficiency (balance with other strategies)

### Low-Frequency Strategies (Long Term)
- **Optimal Range**: Daily to weekly
- **Considerations**:
  - Market regime (daily during volatile periods)
  - Computational intensity (comprehensive analysis takes time)
  - Signal validity (long-term signals change slowly)

## 🔧 Performance Tuning Recommendations

### Based on Backtest Results

1. **Day Trading** (185 signals, 94.6% quality rate)
   - Recommended: 5-minute frequency during high volatility
   - Recommended: 10-minute frequency during low volatility
   - Peak hours: 9:15-11:00 AM, 2:00-3:30 PM

2. **Short Selling** (14 signals, 78.6% quality rate)
   - Recommended: 30-minute frequency (sufficient for quality signals)
   - Focus: End-of-day screening (3:00-4:00 PM)
   - Sector rotation: Increase frequency during sector peaks

3. **Short Term** (Historical average ~40 signals/day)
   - Recommended: 2-hour frequency for optimal coverage
   - Pre-market: 8:00 AM for gap preparation
   - Post-market: 5:00 PM for next-day preparation

4. **Long Term** (18 signals/month average)
   - Recommended: Daily execution sufficient
   - Weekend analysis: Enabled for research and planning

## 📈 Dynamic Frequency Adjustment

### Market Volatility-Based Scaling
```python
# Low Volatility (VIX < 20)
DAY_TRADING_FREQUENCY=10        # Reduce frequency
SHORT_SELLING_FREQUENCY=60      # Longer intervals

# High Volatility (VIX > 30)  
DAY_TRADING_FREQUENCY=5         # Maximum frequency
SHORT_SELLING_FREQUENCY=15      # Frequent monitoring
```

### Market Hours Optimization
```python
# Peak Trading Hours (9:15-11:00 AM, 2:00-3:30 PM)
DAY_TRADING_FREQUENCY=5         # Maximum frequency

# Lunch Hours (11:00 AM-2:00 PM)
DAY_TRADING_FREQUENCY=15        # Reduced frequency
```

## 🚨 Alert Configuration

### Performance Monitoring
- Success Rate Alerts: <80% success rate
- Execution Time Alerts: >5 minutes execution time
- Resource Alerts: >90% CPU/Memory usage

### Strategy-Specific Alerts
- Day Trading: >10 concurrent signals (potential overtrading)
- Short Selling: No signals for >2 hours during market hours
- Long Term: Analysis failure for >1 day

## 🛠️ API Endpoints

### Scheduler Control
- GET `/api/scheduler/status` - Current scheduler status
- POST `/api/scheduler/start` - Start scheduler
- POST `/api/scheduler/stop` - Stop scheduler
- GET `/api/scheduler/health` - Health check

### Manual Execution
- POST `/api/scheduler/execute/day_trading` - Manual day trading execution
- POST `/api/scheduler/execute/short_selling` - Manual short selling execution
- POST `/api/scheduler/execute/short_term` - Manual short-term execution
- POST `/api/scheduler/execute/long_term` - Manual long-term execution

### Monitoring
- GET `/api/scheduler/stats` - Execution statistics
- GET `/api/scheduler/performance` - Performance metrics
- GET `/api/scheduler/next-runs` - Next scheduled runs

## 🎯 Best Practices

### 1. Gradual Rollout
Start with conservative frequencies and gradually optimize:
```bash
# Week 1: Conservative
DAY_TRADING_FREQUENCY=15
SHORT_SELLING_FREQUENCY=60

# Week 2: Standard  
DAY_TRADING_FREQUENCY=10
SHORT_SELLING_FREQUENCY=30

# Week 3+: Optimized
DAY_TRADING_FREQUENCY=5
SHORT_SELLING_FREQUENCY=30
```

### 2. Resource Monitoring
- Monitor CPU/Memory usage
- Track execution times
- Monitor database performance
- Watch API rate limits

### 3. Quality Control
- Monitor signal hit rates
- Track false positive rates
- Review execution statistics daily
- Adjust parameters based on performance

### 4. Risk Management
- Set maximum concurrent strategies
- Use timeouts to prevent hanging
- Monitor for excessive signal generation
- Implement circuit breakers for system protection

## 📱 Mobile App Integration

The scheduler provides real-time updates that can be consumed by mobile applications:

### WebSocket Endpoints (Future Enhancement)
- `/ws/scheduler/status` - Real-time status updates
- `/ws/scheduler/signals` - Live signal notifications
- `/ws/scheduler/performance` - Performance metrics stream

### Push Notifications
Integration with Telegram bot for:
- Strategy execution notifications
- Performance alerts
- System status updates
- Signal quality reports

## 🔮 Advanced Features (Roadmap)

### 1. Machine Learning Integration
- Dynamic frequency adjustment based on market conditions
- Predictive scheduling based on historical performance
- Adaptive timeout management

### 2. Multi-Market Support  
- Different schedules for different exchanges
- Holiday calendar integration
- International market hours support

### 3. Portfolio-Aware Scheduling
- Adjust frequency based on current positions
- Risk-based execution prioritization
- Capital allocation-driven scheduling

### 4. Performance Analytics
- Strategy correlation analysis  
- Resource optimization recommendations
- Predictive performance modeling