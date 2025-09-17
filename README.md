# Stock Trading System with IIFL API Integration

A comprehensive automated stock trading system with IIFL Markets API integration, Telegram bot notifications, and web dashboard.

## Features

- **Event-driven Architecture**: Modular, asynchronous service communication
- **IIFL API Integration**: Complete order management, market data, and portfolio tracking
- **Risk Management**: Position sizing, daily loss limits, drawdown monitoring
- **Telegram Bot**: Real-time notifications and manual approval workflow
- **Web Dashboard**: Modern UI for monitoring and control
- **Backtesting**: Strategy validation before live trading
- **Automated Reporting**: Daily PnL reports with PDF generation

## Quick Start

1. **Clone and Setup**
   ```bash
   cd stock-trading-system
   pip install -r requirements.txt
   ```

2. **Configure Environment**
   ```bash
   cp .env.example .env
   # Edit .env with your IIFL API credentials and Telegram bot token
   ```

3. **Initialize Database**
   ```bash
   python -m alembic upgrade head
   ```

4. **Run the System**
   ```bash
   python main.py
   ```

5. **Access Web Dashboard**
   - Open http://localhost:8000 in your browser
   - API documentation: http://localhost:8000/docs

## Architecture

### Core Services
- **ConfigService**: Environment configuration management
- **DBService**: Async database operations
- **DataFetcher**: IIFL API market data integration
- **StrategyService**: Trading signal generation
- **RiskService**: Position sizing and risk controls
- **OrderManager**: Order execution and lifecycle management
- **TelegramBot**: Notifications and manual approvals
- **ReportService**: PnL tracking and PDF generation

### Database Schema
- `signals`: Trade signals with approval workflow
- `pnl_reports`: Daily and cumulative PnL tracking
- `risk_events`: System risk events and halts
- `settings`: Runtime configuration parameters

## API Endpoints

### System Control
- `GET /api/system/status` - System health and status
- `POST /api/system/halt` - Emergency trading halt
- `POST /api/system/resume` - Resume trading

### Signal Management
- `GET /api/signals` - List pending signals
- `POST /api/signals/{id}/approve` - Approve signal
- `POST /api/signals/{id}/reject` - Reject signal

### Portfolio & Risk
- `GET /api/positions` - Current positions
- `GET /api/pnl/daily` - Daily PnL report
- `GET /api/risk/events` - Risk events log

### Backtesting
- `POST /api/backtest/run` - Run strategy backtest
- `GET /api/backtest/result/{id}` - Get backtest results

## Configuration

Key environment variables:

- `AUTO_TRADE`: Enable/disable automatic order execution
- `SIGNAL_TIMEOUT`: Signal expiry time in seconds
- `RISK_PER_TRADE`: Maximum risk per trade (0.02 = 2%)
- `MAX_DAILY_LOSS`: Maximum daily loss threshold
- `MIN_PRICE`: Minimum stock price filter
- `MIN_LIQUIDITY`: Minimum liquidity filter

## Security

- Bearer token authentication for API access
- Telegram chat ID verification
- Environment-based credential management
- CORS protection for web interface

## Monitoring

- Structured logging with rotation
- Real-time WebSocket updates
- Telegram notifications for all critical events
- Daily PDF reports with charts and metrics

## Development

```bash
# Run tests
pytest

# Format code
black .

# Lint code
flake8 .
```

## Historical Candles Fetcher (Holdings)

Use the standalone script to fetch historical OHLC candles for each holding using IIFL's historical data endpoint.

1. Prepare inputs in the `files/` directory:
   - Copy `files/holding.example.json` to `files/holding.json` and edit with your holdings. Requires `nseInstrumentId` and `nseTradingSymbol`.
   - Copy `files/auth_token.example.txt` to `files/auth_token.txt` and paste your Bearer token (or raw token; the script prefixes it automatically).

2. Run the fetcher:
   ```bash
   python scripts/fetch_holdings_candles.py
   ```

3. Output JSON candle files are saved under `files/` as `<SYMBOL>_candles.json`.

## License

Private use only. Not for redistribution.
