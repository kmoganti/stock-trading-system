# Development Utilities

## Overview
Development server configurations and utilities for rapid development and testing.

## Contents

### Development Servers
- `fast_dev_server.py` - Fast development server with hot reload
- `simple_server.py` - Simple lightweight server for testing
- `instant_server.py` - Instant startup server for quick testing
- `minimal_server.py` - Minimal configuration server
- `emergency_server.py` - Emergency fallback server

### Database Utilities
- `fast_db_init.py` - Fast database initialization for development

## Usage

### Quick Development
```bash
# Fast development server with hot reload
python dev/fast_dev_server.py

# Simple server for basic testing
python dev/simple_server.py

# Instant server for quick tests
python dev/instant_server.py
```

### Database Setup
```bash
# Quick database initialization
python dev/fast_db_init.py
```

### Emergency Recovery
```bash
# Emergency fallback server
python dev/emergency_server.py
```

## Features

### Development Servers
- **Hot Reload**: Automatic restart on code changes
- **Debug Mode**: Enhanced error reporting and logging
- **Fast Startup**: Optimized for development speed
- **Minimal Dependencies**: Reduced overhead for testing

### Database Utilities
- **Fast Init**: Quick database setup for development
- **Test Data**: Optional test data population
- **Schema Validation**: Development schema checking

## Configuration

Development servers use:
- Relaxed security for faster development
- Enhanced logging and debugging
- Auto-reload capabilities
- Local-only configurations

## Best Practices

### During Development
1. Use `fast_dev_server.py` for regular development
2. Use `simple_server.py` for API testing
3. Use `instant_server.py` for quick validation
4. Use `emergency_server.py` only when other servers fail

### Database Development
1. Use `fast_db_init.py` to reset development database
2. Test migrations before applying to production
3. Validate schema changes with development tools

## Integration

Development utilities integrate with:
- Main application configuration
- Test suite execution
- Debug and analysis tools
- Production deployment pipeline