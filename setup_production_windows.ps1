# ============================================================================
# 🏭 PRODUCTION DEPLOYMENT SCRIPT FOR WINDOWS
# ============================================================================
# This script sets up the trading system for production deployment on Windows
# Run with administrator privileges for service installation
# ============================================================================

# Configuration Variables
$SERVICE_NAME = "AlgorithmicTradingSystem"
$SERVICE_DISPLAY_NAME = "Algorithmic Trading System"
$SERVICE_DESCRIPTION = "Production algorithmic trading system with automated signal generation and execution"
$PROJECT_DIR = Get-Location
$PYTHON_EXE = Join-Path $PROJECT_DIR "venv\Scripts\python.exe"
$MAIN_SCRIPT = Join-Path $PROJECT_DIR "run.py"
$LOG_DIR = Join-Path $PROJECT_DIR "logs"

Write-Host "🚀 Setting up Algorithmic Trading System for Production" -ForegroundColor Green
Write-Host "Project Directory: $PROJECT_DIR" -ForegroundColor Cyan
Write-Host "Python Executable: $PYTHON_EXE" -ForegroundColor Cyan

# ============================================================================
# 1. VALIDATE ENVIRONMENT
# ============================================================================

Write-Host "`n📋 Validating Environment..." -ForegroundColor Yellow

# Check if running as administrator
if (-NOT ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator"))
{
    Write-Host "❌ This script requires administrator privileges for service installation" -ForegroundColor Red
    Write-Host "   Please run PowerShell as Administrator and try again" -ForegroundColor Red
    exit 1
}

# Check if Python virtual environment exists
if (-not (Test-Path $PYTHON_EXE)) {
    Write-Host "❌ Python virtual environment not found at: $PYTHON_EXE" -ForegroundColor Red
    Write-Host "   Please create virtual environment first: python -m venv venv" -ForegroundColor Red
    exit 1
}

# Check if main script exists
if (-not (Test-Path $MAIN_SCRIPT)) {
    Write-Host "❌ Main script not found at: $MAIN_SCRIPT" -ForegroundColor Red
    exit 1
}

Write-Host "✅ Environment validation passed" -ForegroundColor Green

# ============================================================================
# 2. INSTALL DEPENDENCIES
# ============================================================================

Write-Host "`n📦 Installing Dependencies..." -ForegroundColor Yellow

try {
    # Install Python dependencies
    & $PYTHON_EXE -m pip install --upgrade pip
    & $PYTHON_EXE -m pip install -r requirements.txt
    
    # Install Windows service wrapper (if not already installed)
    & $PYTHON_EXE -m pip install pywin32
    
    Write-Host "✅ Dependencies installed successfully" -ForegroundColor Green
}
catch {
    Write-Host "❌ Failed to install dependencies: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# ============================================================================
# 3. CREATE WINDOWS SERVICE WRAPPER
# ============================================================================

Write-Host "`n🔧 Creating Windows Service Wrapper..." -ForegroundColor Yellow

$ServiceScript = @"
import sys
import os
import time
import logging
import servicemanager
import win32event
import win32service
import win32serviceutil

# Add project directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

class TradingSystemService(win32serviceutil.ServiceFramework):
    _svc_name_ = "$SERVICE_NAME"
    _svc_display_name_ = "$SERVICE_DISPLAY_NAME"
    _svc_description_ = "$SERVICE_DESCRIPTION"
    
    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        self.running = True
        
        # Set up logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('$LOG_DIR\\service.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger('TradingSystemService')
    
    def SvcStop(self):
        self.logger.info("🛑 Trading system service stop requested")
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.hWaitStop)
        self.running = False
    
    def SvcDoRun(self):
        self.logger.info("🚀 Starting trading system service")
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, '')
        )
        
        try:
            self.main()
        except Exception as e:
            self.logger.error(f"❌ Service error: {str(e)}")
            servicemanager.LogErrorMsg(f"Trading System Service Error: {str(e)}")
    
    def main(self):
        # Import and run the main application
        try:
            # Set environment variables
            os.environ['ENVIRONMENT'] = 'production'
            os.environ['LOG_CONSOLE_ENABLED'] = 'false'
            
            # Import the main application
            from run import main as app_main
            
            self.logger.info("✅ Trading system application starting...")
            
            # Run the application
            app_main()
            
        except Exception as e:
            self.logger.error(f"❌ Application error: {str(e)}")
            raise

if __name__ == '__main__':
    win32serviceutil.HandleCommandLine(TradingSystemService)
"@

# Write service script
$ServiceScriptPath = Join-Path $PROJECT_DIR "trading_service.py"
$ServiceScript | Out-File -FilePath $ServiceScriptPath -Encoding UTF8

Write-Host "✅ Windows service wrapper created" -ForegroundColor Green

# ============================================================================
# 4. INSTALL WINDOWS SERVICE
# ============================================================================

Write-Host "`n🔧 Installing Windows Service..." -ForegroundColor Yellow

try {
    # Install the service
    & $PYTHON_EXE $ServiceScriptPath install
    
    # Configure service to start automatically
    sc.exe config $SERVICE_NAME start= auto
    
    # Set service recovery options
    sc.exe failure $SERVICE_NAME reset= 86400 actions= restart/60000/restart/60000/restart/60000
    
    Write-Host "✅ Windows service installed successfully" -ForegroundColor Green
}
catch {
    Write-Host "❌ Failed to install service: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "   Try running: python trading_service.py install" -ForegroundColor Yellow
}

# ============================================================================
# 5. CREATE FIREWALL RULES
# ============================================================================

Write-Host "`n🔥 Configuring Windows Firewall..." -ForegroundColor Yellow

try {
    # Allow inbound connections on port 8000
    New-NetFirewallRule -DisplayName "Trading System API" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow -Force
    
    # Allow outbound connections for API calls
    New-NetFirewallRule -DisplayName "Trading System Outbound" -Direction Outbound -Protocol TCP -RemotePort 80,443 -Action Allow -Force
    
    Write-Host "✅ Firewall rules configured" -ForegroundColor Green
}
catch {
    Write-Host "⚠️ Firewall configuration skipped (requires admin privileges)" -ForegroundColor Yellow
}

# ============================================================================
# 6. CREATE SCHEDULED TASKS FOR MAINTENANCE
# ============================================================================

Write-Host "`n📅 Setting up Maintenance Tasks..." -ForegroundColor Yellow

try {
    # Create log cleanup task
    $LogCleanupAction = New-ScheduledTaskAction -Execute $PYTHON_EXE -Argument "-c `"import os; import glob; [os.remove(f) for f in glob.glob('logs/*.log') if os.path.getmtime(f) < time.time() - 30*24*3600]`""
    $LogCleanupTrigger = New-ScheduledTaskTrigger -Daily -At "02:00"
    $LogCleanupSettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
    
    Register-ScheduledTask -TaskName "TradingSystemLogCleanup" -Action $LogCleanupAction -Trigger $LogCleanupTrigger -Settings $LogCleanupSettings -Description "Clean old trading system logs" -Force
    
    # Create database backup task
    $BackupAction = New-ScheduledTaskAction -Execute $PYTHON_EXE -Argument "-c `"import shutil; import datetime; shutil.copy('trading_system.db', f'backups/trading_system_backup_{datetime.datetime.now().strftime(`"%Y%m%d`")}.db')`""
    $BackupTrigger = New-ScheduledTaskTrigger -Daily -At "01:00"
    
    Register-ScheduledTask -TaskName "TradingSystemBackup" -Action $BackupAction -Trigger $BackupTrigger -Settings $LogCleanupSettings -Description "Daily backup of trading system database" -Force
    
    Write-Host "✅ Maintenance tasks scheduled" -ForegroundColor Green
}
catch {
    Write-Host "⚠️ Could not create scheduled tasks: $($_.Exception.Message)" -ForegroundColor Yellow
}

# ============================================================================
# 7. VALIDATE PRODUCTION CONFIGURATION
# ============================================================================

Write-Host "`n🔍 Validating Production Configuration..." -ForegroundColor Yellow

try {
    # Test configuration loading
    $ConfigTest = & $PYTHON_EXE -c "from config.settings import get_settings; settings = get_settings(); print(f'Environment: {settings.environment}'); print(f'Debug: {getattr(settings, `'debug`', `'Not set`')}'); print(f'Database: {settings.database_url}')"
    
    Write-Host "Configuration Test Results:" -ForegroundColor Cyan
    Write-Host $ConfigTest -ForegroundColor White
    
    Write-Host "✅ Configuration validation passed" -ForegroundColor Green
}
catch {
    Write-Host "❌ Configuration validation failed: $($_.Exception.Message)" -ForegroundColor Red
}

# ============================================================================
# 8. START SERVICE
# ============================================================================

Write-Host "`n🚀 Starting Trading System Service..." -ForegroundColor Yellow

try {
    # Start the service
    Start-Service -Name $SERVICE_NAME
    
    # Wait a moment for service to start
    Start-Sleep -Seconds 5
    
    # Check service status
    $ServiceStatus = Get-Service -Name $SERVICE_NAME
    
    if ($ServiceStatus.Status -eq "Running") {
        Write-Host "✅ Trading system service is running" -ForegroundColor Green
    } else {
        Write-Host "⚠️ Service status: $($ServiceStatus.Status)" -ForegroundColor Yellow
    }
}
catch {
    Write-Host "⚠️ Could not start service automatically: $($_.Exception.Message)" -ForegroundColor Yellow
    Write-Host "   Try starting manually: Start-Service -Name $SERVICE_NAME" -ForegroundColor Cyan
}

# ============================================================================
# 9. DEPLOYMENT SUMMARY
# ============================================================================

Write-Host "`n📋 Production Deployment Summary" -ForegroundColor Green
Write-Host "=================================" -ForegroundColor Green

Write-Host "🏭 Environment: Production" -ForegroundColor Cyan
Write-Host "📁 Project Directory: $PROJECT_DIR" -ForegroundColor Cyan
Write-Host "🔧 Service Name: $SERVICE_NAME" -ForegroundColor Cyan
Write-Host "📊 Log Directory: $LOG_DIR" -ForegroundColor Cyan
Write-Host "💾 Backup Directory: $(Join-Path $PROJECT_DIR 'backups')" -ForegroundColor Cyan

Write-Host "`n📋 Next Steps:" -ForegroundColor Yellow
Write-Host "1. ✅ Verify service is running: Get-Service -Name $SERVICE_NAME" -ForegroundColor White
Write-Host "2. 🌐 Test API endpoint: Invoke-RestMethod -Uri http://localhost:8000/health" -ForegroundColor White
Write-Host "3. 📊 Monitor logs: Get-Content -Path '$LOG_DIR\trading_system.log' -Tail 20 -Wait" -ForegroundColor White
Write-Host "4. 🔒 Configure SSL certificate for HTTPS" -ForegroundColor White
Write-Host "5. ⚠️ Set DRY_RUN=false and AUTO_TRADE=true when ready for live trading" -ForegroundColor White

Write-Host "`n🎉 Production deployment completed successfully!" -ForegroundColor Green

# ============================================================================
# 10. SERVICE MANAGEMENT COMMANDS
# ============================================================================

Write-Host "`n🔧 Service Management Commands:" -ForegroundColor Yellow
Write-Host "Start Service:    Start-Service -Name $SERVICE_NAME" -ForegroundColor Cyan
Write-Host "Stop Service:     Stop-Service -Name $SERVICE_NAME" -ForegroundColor Cyan
Write-Host "Restart Service:  Restart-Service -Name $SERVICE_NAME" -ForegroundColor Cyan
Write-Host "Service Status:   Get-Service -Name $SERVICE_NAME" -ForegroundColor Cyan
Write-Host "Service Logs:     Get-Content '$LOG_DIR\service.log' -Tail 50" -ForegroundColor Cyan
Write-Host "Uninstall:        python trading_service.py remove" -ForegroundColor Cyan