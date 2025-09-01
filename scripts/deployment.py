#!/usr/bin/env python3
"""
Deployment script for the Automated Stock Trading System
"""

import os
import sys
import subprocess
import json
from pathlib import Path
from datetime import datetime

def run_command(command, description, capture_output=True):
    """Run a command and handle errors"""
    print(f"🔄 {description}...")
    try:
        result = subprocess.run(
            command, 
            shell=True, 
            check=True, 
            capture_output=capture_output, 
            text=True
        )
        print(f"✅ {description} completed")
        return result.stdout if capture_output else True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed: {e.stderr if capture_output else str(e)}")
        return False

def check_prerequisites():
    """Check deployment prerequisites"""
    print("🔍 Checking prerequisites...")
    
    prerequisites = [
        ("docker", "Docker is required for containerized deployment"),
        ("docker-compose", "Docker Compose is required for multi-container setup")
    ]
    
    missing = []
    for cmd, description in prerequisites:
        try:
            subprocess.run([cmd, "--version"], capture_output=True, check=True)
            print(f"✅ {cmd} found")
        except (subprocess.CalledProcessError, FileNotFoundError):
            print(f"❌ {description}")
            missing.append(cmd)
    
    return len(missing) == 0

def build_docker_image():
    """Build Docker image"""
    return run_command(
        "docker build -t trading-system:latest .",
        "Building Docker image"
    )

def run_tests_in_container():
    """Run tests in Docker container"""
    return run_command(
        "docker run --rm trading-system:latest python -m pytest tests/ -v",
        "Running tests in container"
    )

def deploy_with_docker_compose():
    """Deploy using Docker Compose"""
    return run_command(
        "docker-compose up -d",
        "Starting services with Docker Compose"
    )

def check_service_health():
    """Check if services are healthy"""
    print("🔄 Checking service health...")
    
    # Wait a moment for services to start
    import time
    time.sleep(10)
    
    try:
        import requests
        response = requests.get("http://localhost:8000/api/system/health", timeout=30)
        if response.status_code == 200:
            print("✅ Trading system is healthy")
            return True
        else:
            print(f"❌ Health check failed with status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Health check failed: {str(e)}")
        return False

def create_systemd_service():
    """Create systemd service for production deployment"""
    service_content = f"""[Unit]
Description=Automated Stock Trading System
After=network.target

[Service]
Type=simple
User=trading
WorkingDirectory={Path.cwd()}
Environment=PATH={Path.cwd()}/venv/bin
ExecStart={Path.cwd()}/venv/bin/python run.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
"""
    
    service_file = Path("/etc/systemd/system/trading-system.service")
    
    try:
        service_file.write_text(service_content)
        print("✅ Systemd service created")
        
        # Enable and start service
        run_command("sudo systemctl daemon-reload", "Reloading systemd")
        run_command("sudo systemctl enable trading-system", "Enabling service")
        run_command("sudo systemctl start trading-system", "Starting service")
        
        return True
    except PermissionError:
        print("❌ Permission denied. Run with sudo for systemd service creation")
        return False
    except Exception as e:
        print(f"❌ Failed to create systemd service: {str(e)}")
        return False

def backup_configuration():
    """Backup current configuration"""
    backup_dir = Path("backups")
    backup_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = backup_dir / f"config_backup_{timestamp}.tar.gz"
    
    files_to_backup = [".env", "trading.db", "logs/", "reports/"]
    existing_files = [f for f in files_to_backup if Path(f).exists()]
    
    if existing_files:
        backup_cmd = f"tar -czf {backup_file} {' '.join(existing_files)}"
        if run_command(backup_cmd, f"Creating backup {backup_file}"):
            print(f"📦 Backup created: {backup_file}")
            return True
    
    return False

def deployment_menu():
    """Interactive deployment menu"""
    print("\n🚀 Automated Stock Trading System - Deployment")
    print("=" * 50)
    print("1. Development deployment (local)")
    print("2. Docker deployment (containerized)")
    print("3. Production deployment (systemd)")
    print("4. Run tests only")
    print("5. Backup configuration")
    print("0. Exit")
    
    choice = input("\nSelect deployment option: ").strip()
    return choice

def main():
    """Main deployment function"""
    print("🚀 Stock Trading System Deployment Tool")
    print("=" * 50)
    
    while True:
        choice = deployment_menu()
        
        if choice == "0":
            print("👋 Goodbye!")
            break
            
        elif choice == "1":
            print("\n📍 Development Deployment")
            print("-" * 30)
            
            # Check if virtual environment exists
            if not Path("venv").exists():
                print("Creating virtual environment...")
                run_command("python -m venv venv", "Creating virtual environment")
            
            # Install dependencies
            if os.name == 'nt':  # Windows
                pip_cmd = "venv\\Scripts\\pip install -r requirements.txt"
                python_cmd = "venv\\Scripts\\python run.py"
            else:  # Unix/Linux
                pip_cmd = "venv/bin/pip install -r requirements.txt"
                python_cmd = "venv/bin/python run.py"
            
            if run_command(pip_cmd, "Installing dependencies"):
                print("✅ Ready for development!")
                print(f"Run: {python_cmd}")
            
        elif choice == "2":
            print("\n🐳 Docker Deployment")
            print("-" * 30)
            
            if not check_prerequisites():
                continue
            
            steps = [
                (build_docker_image, "Building Docker image"),
                (run_tests_in_container, "Running tests"),
                (deploy_with_docker_compose, "Deploying with Docker Compose"),
                (check_service_health, "Checking service health")
            ]
            
            success = True
            for step_func, step_name in steps:
                if not step_func():
                    success = False
                    break
            
            if success:
                print("🎉 Docker deployment successful!")
                print("Access dashboard at: http://localhost:8000")
            
        elif choice == "3":
            print("\n🏭 Production Deployment")
            print("-" * 30)
            
            backup_configuration()
            
            if create_systemd_service():
                print("🎉 Production deployment successful!")
                print("Service status: sudo systemctl status trading-system")
                print("View logs: sudo journalctl -u trading-system -f")
            
        elif choice == "4":
            print("\n🧪 Running Tests")
            print("-" * 30)
            
            run_command("python -m pytest tests/ -v --tb=short", "Running test suite", False)
            
        elif choice == "5":
            print("\n💾 Configuration Backup")
            print("-" * 30)
            
            backup_configuration()
            
        else:
            print("❌ Invalid choice. Please try again.")
        
        input("\nPress Enter to continue...")

if __name__ == "__main__":
    main()
