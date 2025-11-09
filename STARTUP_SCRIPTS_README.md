# Startup Scripts for Stock Trading System

This directory contains scripts to manage the trading system with Telegram bot and market stream.

## Available Scripts

### `./start.sh`
Starts the trading system with all configured services:
- Loads environment variables from `.env`
- Validates required configuration (IIFL credentials, etc.)
- Starts the production server with logging
- Enables Telegram bot (if configured)
- Enables market stream (if configured)
- Performs health checks
- Saves PID for process management

**Safety features:**
- Backs up `.env` before starting
- Prompts for confirmation if AUTO_TRADE=true and DRY_RUN=false
- Prevents starting if already running
- Validates required environment variables

### `./stop.sh`
Gracefully stops the trading system:
- Sends SIGTERM for graceful shutdown
- Waits up to 30 seconds for clean exit
- Falls back to SIGKILL if needed
- Cleans up PID file

### `./restart.sh`
Restarts the system (stop + start):
- Stops the current instance
- Waits briefly
- Starts a new instance

### `./status.sh`
Displays comprehensive system status:
- Process information (PID, CPU, memory, uptime)
- Health check results
- Service status (auto-trade, IIFL API, database)
- Log file information
- Recent errors from logs
- Quick access URLs

## Quick Start

1. **First time setup:**
   ```bash
   # Ensure .env is configured with your credentials
   cp .env.example .env
   # Edit .env with your actual values
   nano .env
   ```

2. **Start the system:**
   ```bash
   ./start.sh
   ```

3. **Check status:**
   ```bash
   ./status.sh
   ```

4. **View logs:**
   ```bash
   tail -f logs/trading_system.log
   ```

5. **Stop the system:**
   ```bash
   ./stop.sh
   ```

## Configuration

The scripts read configuration from `.env` file. Key variables:

### Required
- `IIFL_CLIENT_ID` - Your IIFL client ID
- `IIFL_AUTH_CODE` - IIFL authentication code
- `IIFL_APP_SECRET` - IIFL application secret

### Optional but Recommended
- `TELEGRAM_BOT_TOKEN` - Telegram bot token (from BotFather)
- `TELEGRAM_CHAT_ID` - Your Telegram chat ID
- `ENABLE_MARKET_STREAM` - Enable real-time market data (default: false)
- `TELEGRAM_BOT_ENABLED` - Enable Telegram notifications (default: false)

### Safety Settings
- `AUTO_TRADE` - Enable automatic order placement (default: false)
- `DRY_RUN` - Test mode without real orders (default: true)

## Environment Variables

The scripts handle environment variables automatically:
- Loads all variables from `.env`
- Validates required variables before starting
- Warns about missing optional variables
- Exports variables for the Python process

## Process Management

- PID file: `.trading_system.pid`
- Logs directory: `logs/`
- Startup log: `logs/startup.log`
- Main log: `logs/trading_system.log`

## Health Checks

The start script performs automatic health checks:
- Waits for server to start (up to 20 seconds)
- Checks `/health` endpoint
- Reports success/failure

The status script provides detailed health information:
- Process status and resource usage
- API connectivity (IIFL, database)
- Service status (auto-trade, market stream, telegram)
- Recent errors from logs

## Troubleshooting

### Server won't start
```bash
# Check startup logs
tail -50 logs/startup.log

# Check for missing environment variables
./start.sh
# (Will list any missing required variables)
```

### Process stuck or zombie
```bash
# Force kill and cleanup
kill -9 $(cat .trading_system.pid)
rm .trading_system.pid
./start.sh
```

### Health check fails
```bash
# Wait a bit longer - server may still be initializing
sleep 10
curl http://localhost:8000/health

# Check if process is running
./status.sh

# Check logs for errors
tail -50 logs/trading_system.log | grep ERROR
```

### Port already in use
```bash
# Find and kill process using port 8000
lsof -i :8000
kill <PID>

# Or change port in .env
echo "PORT=8001" >> .env
./start.sh
```

## Safety Features

1. **Backup Protection**: Creates timestamped `.env` backup before each start
2. **Live Trading Confirmation**: Requires typing "YES" to start with AUTO_TRADE=true
3. **Running Check**: Prevents starting duplicate instances
4. **Graceful Shutdown**: Gives services time to clean up before force-killing
5. **Environment Validation**: Checks for required variables before starting

## Logs

All logs are stored in `logs/` directory:
- `startup.log` - Server startup messages
- `trading_system.log` - Main application log
- Various component logs (if configured)

## systemd Integration (Optional)

For production deployment, you can create a systemd service:

```bash
sudo nano /etc/systemd/system/trading-system.service
```

```ini
[Unit]
Description=Stock Trading System
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/stock-trading-system
ExecStart=/path/to/stock-trading-system/start.sh
ExecStop=/path/to/stock-trading-system/stop.sh
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable trading-system
sudo systemctl start trading-system
sudo systemctl status trading-system
```

## Examples

### Start in test mode (safe)
```bash
# Ensure these are set in .env:
# AUTO_TRADE=false
# DRY_RUN=true
./start.sh
```

### Start with Telegram and market stream
```bash
# Ensure these are set in .env:
# TELEGRAM_BOT_TOKEN=your_token
# TELEGRAM_CHAT_ID=your_chat_id
# ENABLE_MARKET_STREAM=true
# TELEGRAM_BOT_ENABLED=true
./start.sh
```

### Monitor in real-time
```bash
# Terminal 1: Start system
./start.sh

# Terminal 2: Watch logs
tail -f logs/trading_system.log

# Terminal 3: Monitor status
watch -n 5 './status.sh'
```

## Support

For issues or questions:
1. Check logs: `tail -50 logs/trading_system.log`
2. Verify status: `./status.sh`
3. Check environment: `grep -v '^#' .env | grep -v '^$'`
4. Review documentation in the main README.md
