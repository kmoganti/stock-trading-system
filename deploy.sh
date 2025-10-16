#!/bin/bash
# Secure Production Deployment Script
# This script deploys the trading system with security hardening

set -euo pipefail  # Exit on error, undefined vars, pipe failures

echo "🚀 Starting secure deployment of Trading System"

# Configuration
PROJECT_DIR="/opt/trading-system"
USER="trading"
GROUP="trading"
DB_PATH="${PROJECT_DIR}/trading_system.db"
LOG_DIR="${PROJECT_DIR}/logs"
BACKUP_DIR="${PROJECT_DIR}/backups"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   log_error "This script should not be run as root for security reasons"
   exit 1
fi

# Create system user if not exists
create_system_user() {
    if ! id "$USER" &>/dev/null; then
        log_info "Creating system user: $USER"
        sudo useradd -r -s /bin/false -d "$PROJECT_DIR" "$USER"
        sudo groupadd "$GROUP" || true
        sudo usermod -a -G "$GROUP" "$USER"
    fi
}

# Set up directory structure with secure permissions
setup_directories() {
    log_info "Setting up directory structure..."
    
    sudo mkdir -p "$PROJECT_DIR"
    sudo mkdir -p "$LOG_DIR"
    sudo mkdir -p "$BACKUP_DIR"
    sudo mkdir -p "${PROJECT_DIR}/ssl"
    
    # Set ownership
    sudo chown -R "$USER:$GROUP" "$PROJECT_DIR"
    
    # Set secure permissions
    sudo chmod 750 "$PROJECT_DIR"           # Owner and group access
    sudo chmod 750 "$LOG_DIR"               # Log directory
    sudo chmod 700 "$BACKUP_DIR"            # Backup directory (owner only)
    sudo chmod 700 "${PROJECT_DIR}/ssl"     # SSL directory (owner only)
}

# Deploy application files
deploy_application() {
    log_info "Deploying application files..."
    
    # Copy application files
    sudo cp -r . "$PROJECT_DIR/"
    
    # Ensure proper ownership
    sudo chown -R "$USER:$GROUP" "$PROJECT_DIR"
    
    # Set secure file permissions
    sudo find "$PROJECT_DIR" -type f -name "*.py" -exec chmod 644 {} \;
    sudo find "$PROJECT_DIR" -type f -name "*.env*" -exec chmod 600 {} \;
    sudo find "$PROJECT_DIR" -type f -name "*.key" -exec chmod 600 {} \;
    sudo find "$PROJECT_DIR" -type f -name "*.pem" -exec chmod 600 {} \;
    sudo find "$PROJECT_DIR" -type d -exec chmod 755 {} \;
    
    # Make run script executable
    sudo chmod 755 "${PROJECT_DIR}/run.py"
}

# Install Python dependencies in virtual environment
setup_python_environment() {
    log_info "Setting up Python virtual environment..."
    
    cd "$PROJECT_DIR"
    
    # Create virtual environment as trading user
    sudo -u "$USER" python3 -m venv venv
    
    # Install dependencies
    sudo -u "$USER" ./venv/bin/pip install --upgrade pip
    sudo -u "$USER" ./venv/bin/pip install -r requirements.txt
    
    # Set secure permissions on venv
    sudo chmod -R 750 "${PROJECT_DIR}/venv"
}

# Create systemd service
create_systemd_service() {
    log_info "Creating systemd service..."
    
    sudo tee /etc/systemd/system/trading-system.service > /dev/null <<EOF
[Unit]
Description=Algorithmic Trading System
After=network.target
Wants=network-online.target

[Service]
Type=exec
User=$USER
Group=$GROUP
WorkingDirectory=$PROJECT_DIR
Environment=PATH=$PROJECT_DIR/venv/bin
Environment=PYTHONPATH=$PROJECT_DIR
EnvironmentFile=$PROJECT_DIR/.env.production
ExecStart=$PROJECT_DIR/venv/bin/python $PROJECT_DIR/run.py
Restart=always
RestartSec=10

# Security settings
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=$PROJECT_DIR/logs $PROJECT_DIR/data $PROJECT_DIR/backups
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictRealtime=true
SystemCallFilter=@system-service
SystemCallErrorNumber=EPERM

# Resource limits
LimitNOFILE=65536
LimitMEMLOCK=0

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    sudo systemctl enable trading-system.service
}

# Configure firewall
setup_firewall() {
    log_info "Configuring firewall..."
    
    # Install ufw if not present
    if ! command -v ufw &> /dev/null; then
        sudo apt-get update
        sudo apt-get install -y ufw
    fi
    
    # Reset firewall rules
    sudo ufw --force reset
    
    # Default policies
    sudo ufw default deny incoming
    sudo ufw default allow outgoing
    
    # Allow SSH (be careful!)
    sudo ufw allow ssh
    
    # Allow HTTP and HTTPS
    sudo ufw allow 80/tcp
    sudo ufw allow 443/tcp
    
    # Allow application port (only from localhost)
    sudo ufw allow from 127.0.0.1 to any port 8000
    
    # Enable firewall
    sudo ufw --force enable
    
    log_info "Firewall configured. SSH, HTTP, HTTPS allowed."
}

# Set up SSL certificates
setup_ssl() {
    log_info "Setting up SSL certificates..."
    
    SSL_DIR="${PROJECT_DIR}/ssl"
    
    # Check if certificates exist
    if [[ ! -f "${SSL_DIR}/cert.pem" ]] || [[ ! -f "${SSL_DIR}/private.key" ]]; then
        log_warn "SSL certificates not found. Generating self-signed certificate..."
        log_warn "For production, replace with proper SSL certificates!"
        
        sudo -u "$USER" openssl req -x509 -newkey rsa:4096 \
            -keyout "${SSL_DIR}/private.key" \
            -out "${SSL_DIR}/cert.pem" \
            -days 365 -nodes \
            -subj "/C=IN/ST=State/L=City/O=TradingSystem/CN=localhost"
        
        # Set secure permissions
        sudo chmod 600 "${SSL_DIR}/private.key"
        sudo chmod 644 "${SSL_DIR}/cert.pem"
    fi
}

# Install and configure nginx
setup_nginx() {
    log_info "Setting up nginx reverse proxy..."
    
    # Install nginx
    sudo apt-get update
    sudo apt-get install -y nginx
    
    # Create nginx configuration
    sudo tee /etc/nginx/sites-available/trading-system > /dev/null <<EOF
server {
    listen 80;
    server_name _;
    return 301 https://\$server_name\$request_uri;
}

server {
    listen 443 ssl http2;
    server_name _;
    
    ssl_certificate ${PROJECT_DIR}/ssl/cert.pem;
    ssl_private_key ${PROJECT_DIR}/ssl/private.key;
    
    # SSL Security
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    
    # Security headers
    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload";
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    
    # Rate limiting
    limit_req_zone \$binary_remote_addr zone=api:10m rate=100r/m;
    limit_req_zone \$binary_remote_addr zone=auth:10m rate=5r/m;
    
    location /api/auth/ {
        limit_req zone=auth burst=2 nodelay;
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
    
    location /api/ {
        limit_req zone=api burst=20 nodelay;
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF
    
    # Enable site
    sudo ln -sf /etc/nginx/sites-available/trading-system /etc/nginx/sites-enabled/
    sudo rm -f /etc/nginx/sites-enabled/default
    
    # Test configuration
    sudo nginx -t
    
    # Start nginx
    sudo systemctl enable nginx
    sudo systemctl restart nginx
}

# Validate deployment
validate_deployment() {
    log_info "Validating deployment..."
    
    # Check if service is running
    if sudo systemctl is-active --quiet trading-system; then
        log_info "✅ Trading system service is running"
    else
        log_error "❌ Trading system service is not running"
        sudo systemctl status trading-system
        return 1
    fi
    
    # Check if nginx is running
    if sudo systemctl is-active --quiet nginx; then
        log_info "✅ Nginx is running"
    else
        log_error "❌ Nginx is not running"
        sudo systemctl status nginx
        return 1
    fi
    
    # Test API endpoint
    if curl -k -f https://localhost/health &>/dev/null; then
        log_info "✅ API health check passed"
    else
        log_warn "⚠️ API health check failed - service may still be starting"
    fi
    
    # Check file permissions
    log_info "Checking file permissions..."
    ls -la "${PROJECT_DIR}/.env.production" | head -1
    ls -la "${PROJECT_DIR}/ssl/" | head -1
}

# Main deployment flow
main() {
    log_info "🔒 Starting secure deployment..."
    
    create_system_user
    setup_directories
    deploy_application
    setup_python_environment
    create_systemd_service
    setup_firewall
    setup_ssl
    setup_nginx
    
    # Start services
    log_info "Starting services..."
    sudo systemctl start trading-system
    sudo systemctl start nginx
    
    # Validate deployment
    validate_deployment
    
    log_info "🎉 Deployment completed successfully!"
    log_info ""
    log_info "📋 Post-deployment checklist:"
    log_info "  1. Update .env.production with your actual API keys"
    log_info "  2. Replace self-signed SSL certificate with proper certificate"
    log_info "  3. Configure your domain name and update nginx"
    log_info "  4. Set up monitoring and log rotation"
    log_info "  5. Configure backup schedule"
    log_info ""
    log_info "🔗 Access your system at: https://localhost/"
}

# Run main function
main "$@"
