#!/bin/bash
# Service Manager for External Trading System Services
# Manages Telegram Bot and Market Stream as separate processes

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Service configuration
TELEGRAM_BOT_SCRIPT="services/external_telegram_bot.py"
MARKET_STREAM_SCRIPT="services/external_market_stream.py"
MAIN_SERVER_SCRIPT="main.py"

# PID files
TELEGRAM_BOT_PID="logs/telegram_bot.pid"
MARKET_STREAM_PID="logs/market_stream.pid"
MAIN_SERVER_PID="logs/main_server.pid"

# Log files
TELEGRAM_BOT_LOG="logs/telegram_bot.log"
MARKET_STREAM_LOG="logs/market_stream.log"
MAIN_SERVER_LOG="logs/main_server.log"

# Ensure logs directory exists
mkdir -p logs

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if a service is running
is_running() {
    local pid_file=$1
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if ps -p "$pid" > /dev/null 2>&1; then
            return 0
        else
            rm -f "$pid_file"
            return 1
        fi
    fi
    return 1
}

# Start a service
start_service() {
    local service_name=$1
    local script_path=$2
    local pid_file=$3
    local log_file=$4
    
    if is_running "$pid_file"; then
        print_warning "$service_name is already running"
        return 0
    fi
    
    print_status "Starting $service_name..."
    nohup python3 "$script_path" > "$log_file" 2>&1 &
    local pid=$!
    echo $pid > "$pid_file"
    
    sleep 2
    if is_running "$pid_file"; then
        print_success "$service_name started successfully (PID: $pid)"
        return 0
    else
        print_error "Failed to start $service_name"
        return 1
    fi
}

# Stop a service
stop_service() {
    local service_name=$1
    local pid_file=$2
    
    if ! is_running "$pid_file"; then
        print_warning "$service_name is not running"
        return 0
    fi
    
    local pid=$(cat "$pid_file")
    print_status "Stopping $service_name (PID: $pid)..."
    
    kill "$pid"
    sleep 2
    
    if is_running "$pid_file"; then
        print_warning "Forcefully killing $service_name..."
        kill -9 "$pid"
        sleep 1
    fi
    
    rm -f "$pid_file"
    print_success "$service_name stopped"
}

# Show service status
show_status() {
    echo "=== Trading System Services Status ==="
    echo
    
    # Main Server
    if is_running "$MAIN_SERVER_PID"; then
        local pid=$(cat "$MAIN_SERVER_PID")
        print_success "Main Server: RUNNING (PID: $pid)"
    else
        print_error "Main Server: STOPPED"
    fi
    
    # Telegram Bot
    if is_running "$TELEGRAM_BOT_PID"; then
        local pid=$(cat "$TELEGRAM_BOT_PID")
        print_success "Telegram Bot: RUNNING (PID: $pid)"
    else
        print_error "Telegram Bot: STOPPED"
    fi
    
    # Market Stream
    if is_running "$MARKET_STREAM_PID"; then
        local pid=$(cat "$MARKET_STREAM_PID")
        print_success "Market Stream: RUNNING (PID: $pid)"
    else
        print_error "Market Stream: STOPPED"
    fi
    echo
}

# Start all services
start_all() {
    echo "=== Starting All Trading System Services ==="
    echo
    
    # Start main server first
    start_service "Main Server" "$MAIN_SERVER_SCRIPT" "$MAIN_SERVER_PID" "$MAIN_SERVER_LOG"
    
    # Start external services
    start_service "Telegram Bot" "$TELEGRAM_BOT_SCRIPT" "$TELEGRAM_BOT_PID" "$TELEGRAM_BOT_LOG"
    start_service "Market Stream" "$MARKET_STREAM_SCRIPT" "$MARKET_STREAM_PID" "$MARKET_STREAM_LOG"
    
    echo
    show_status
}

# Stop all services
stop_all() {
    echo "=== Stopping All Trading System Services ==="
    echo
    
    stop_service "Market Stream" "$MARKET_STREAM_PID"
    stop_service "Telegram Bot" "$TELEGRAM_BOT_PID"
    stop_service "Main Server" "$MAIN_SERVER_PID"
    
    echo
    show_status
}

# Restart all services
restart_all() {
    echo "=== Restarting All Trading System Services ==="
    echo
    
    stop_all
    sleep 2
    start_all
}

# Show logs
show_logs() {
    local service=$1
    case $service in
        "main"|"server")
            echo "=== Main Server Logs ==="
            tail -f "$MAIN_SERVER_LOG"
            ;;
        "telegram"|"bot")
            echo "=== Telegram Bot Logs ==="
            tail -f "$TELEGRAM_BOT_LOG"
            ;;
        "market"|"stream")
            echo "=== Market Stream Logs ==="
            tail -f "$MARKET_STREAM_LOG"
            ;;
        "all"|*)
            echo "=== All Service Logs ==="
            echo "Main Server | Telegram Bot | Market Stream"
            echo "============|==============|==============="
            tail -f "$MAIN_SERVER_LOG" "$TELEGRAM_BOT_LOG" "$MARKET_STREAM_LOG"
            ;;
    esac
}

# Main script logic
case "${1:-}" in
    "start")
        case "${2:-all}" in
            "main"|"server")
                start_service "Main Server" "$MAIN_SERVER_SCRIPT" "$MAIN_SERVER_PID" "$MAIN_SERVER_LOG"
                ;;
            "telegram"|"bot")
                start_service "Telegram Bot" "$TELEGRAM_BOT_SCRIPT" "$TELEGRAM_BOT_PID" "$TELEGRAM_BOT_LOG"
                ;;
            "market"|"stream")
                start_service "Market Stream" "$MARKET_STREAM_SCRIPT" "$MARKET_STREAM_PID" "$MARKET_STREAM_LOG"
                ;;
            "all"|*)
                start_all
                ;;
        esac
        ;;
    "stop")
        case "${2:-all}" in
            "main"|"server")
                stop_service "Main Server" "$MAIN_SERVER_PID"
                ;;
            "telegram"|"bot")
                stop_service "Telegram Bot" "$TELEGRAM_BOT_PID"
                ;;
            "market"|"stream")
                stop_service "Market Stream" "$MARKET_STREAM_PID"
                ;;
            "all"|*)
                stop_all
                ;;
        esac
        ;;
    "restart")
        case "${2:-all}" in
            "main"|"server")
                stop_service "Main Server" "$MAIN_SERVER_PID"
                start_service "Main Server" "$MAIN_SERVER_SCRIPT" "$MAIN_SERVER_PID" "$MAIN_SERVER_LOG"
                ;;
            "telegram"|"bot")
                stop_service "Telegram Bot" "$TELEGRAM_BOT_PID"
                start_service "Telegram Bot" "$TELEGRAM_BOT_SCRIPT" "$TELEGRAM_BOT_PID" "$TELEGRAM_BOT_LOG"
                ;;
            "market"|"stream")
                stop_service "Market Stream" "$MARKET_STREAM_PID"
                start_service "Market Stream" "$MARKET_STREAM_SCRIPT" "$MARKET_STREAM_PID" "$MARKET_STREAM_LOG"
                ;;
            "all"|*)
                restart_all
                ;;
        esac
        ;;
    "status")
        show_status
        ;;
    "logs")
        show_logs "${2:-all}"
        ;;
    *)
        echo "Trading System Service Manager"
        echo
        echo "Usage: $0 {start|stop|restart|status|logs} [service]"
        echo
        echo "Commands:"
        echo "  start [service]   - Start services"
        echo "  stop [service]    - Stop services"
        echo "  restart [service] - Restart services"
        echo "  status           - Show service status"
        echo "  logs [service]   - Show service logs"
        echo
        echo "Services:"
        echo "  all              - All services (default)"
        echo "  main|server      - Main trading server"
        echo "  telegram|bot     - Telegram bot service"
        echo "  market|stream    - Market stream service"
        echo
        echo "Examples:"
        echo "  $0 start all          # Start all services"
        echo "  $0 stop telegram      # Stop telegram bot"
        echo "  $0 restart market     # Restart market stream"
        echo "  $0 logs main          # Show main server logs"
        echo "  $0 status             # Show all service status"
        ;;
esac