# Debug Utilities

## Overview
Debug scripts for troubleshooting and system analysis.

## Contents

### Authentication Debugging
- `debug_auth.py` - IIFL authentication troubleshooting
- Helps diagnose auth token issues and API connection problems

### Startup Debugging  
- `debug_startup.py` - System startup troubleshooting
- Identifies initialization issues and dependency problems

### Historical Data Debugging
- `debug_historical_data.py` - Historical data retrieval troubleshooting
- Validates data fetching and processing workflows

## Usage

```bash
# Debug authentication issues
python debug/debug_auth.py

# Debug startup problems
python debug/debug_startup.py

# Debug historical data issues
python debug/debug_historical_data.py
```

## When to Use

- **Authentication Failures**: Use `debug_auth.py` when IIFL API authentication fails
- **Startup Issues**: Use `debug_startup.py` when the system won't start properly
- **Data Problems**: Use `debug_historical_data.py` when historical data retrieval fails

## Integration

These debug scripts can be integrated into the main test suite for automated troubleshooting during development and deployment.