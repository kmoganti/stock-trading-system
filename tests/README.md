# Test Organization and Structure

## Overview
The test suite has been reorganized into a structured hierarchy for better maintainability and clarity.

## Directory Structure

```
tests/
├── __init__.py                 # Main tests package
├── conftest.py                # Shared pytest configuration and fixtures
│
├── unit/                      # Unit tests - isolated component testing
│   ├── __init__.py
│   ├── test_diagnostics.py           # Core system health checks
│   ├── test_database_models.py       # Database model tests
│   ├── test_api_endpoints.py         # FastAPI endpoint tests
│   ├── test_api.py                   # Additional API tests
│   ├── test_models.py                # Model validation tests
│   ├── test_services.py              # Service layer tests
│   ├── test_data_fetcher_service.py  # Data fetching service tests
│   ├── test_order_manager_service.py # Order management tests
│   ├── test_iifl_api_service.py      # IIFL API service tests
│   └── test_iifl_api_service_fixed.py # Fixed IIFL API tests
│
├── integration/               # Integration tests - component interaction
│   ├── __init__.py
│   ├── test_integration.py           # General integration tests
│   ├── test_iifl_holdings.py         # IIFL holdings integration
│   └── iifl_auth_test.py              # IIFL authentication integration
│
├── functional/                # Functional tests - end-to-end workflows
│   ├── __init__.py
│   ├── test_basic_functionality.py   # Basic system functionality
│   └── test_real_signals.py          # Real signal generation tests
│
├── performance/               # Performance and load testing
│   ├── __init__.py
│   └── test_logging_performance.py   # Logging system performance
│
└── backtest/                  # Backtesting and strategy validation
    ├── __init__.py
    ├── comprehensive_backtest.py     # Comprehensive backtesting
    ├── comprehensive_monthly_backtest.py # Monthly backtest analysis
    └── short_selling_daytrading_backtest.py # Day trading strategies
```

## Test Categories

### 1. Unit Tests (`tests/unit/`)
**Purpose**: Test individual components in isolation
- **test_diagnostics.py**: Core system health and import validation
- **test_database_models.py**: Database model creation, validation, and operations
- **test_api_endpoints.py**: FastAPI route testing with mocks
- **test_*_service.py**: Individual service layer components

**Run Command**: `python -m pytest tests/unit/ -v`

### 2. Integration Tests (`tests/integration/`)
**Purpose**: Test interaction between components
- **test_iifl_holdings.py**: IIFL API integration with real/mock data
- **iifl_auth_test.py**: Authentication flow with IIFL services
- **test_integration.py**: General component integration

**Run Command**: `python -m pytest tests/integration/ -v`

### 3. Functional Tests (`tests/functional/`)
**Purpose**: Test complete user workflows and business logic
- **test_basic_functionality.py**: Core trading system workflows
- **test_real_signals.py**: Signal generation and processing

**Run Command**: `python -m pytest tests/functional/ -v`

### 4. Performance Tests (`tests/performance/`)
**Purpose**: Test system performance and resource usage
- **test_logging_performance.py**: Logging system optimization

**Run Command**: `python -m pytest tests/performance/ -v`

### 5. Backtest Tests (`tests/backtest/`)
**Purpose**: Strategy validation and historical testing
- **comprehensive_backtest.py**: Full strategy backtesting
- **comprehensive_monthly_backtest.py**: Monthly analysis
- **short_selling_daytrading_backtest.py**: Day trading strategies

**Run Command**: `python -m pytest tests/backtest/ -v`

## Running Tests

### Quick Health Check
```bash
# Run diagnostic tests to verify core functionality
python -m pytest tests/unit/test_diagnostics.py -v
```

### Full Test Suite
```bash
# Run all tests with the organized test runner
python run_all_tests.py
```

### Category-Specific Testing
```bash
# Unit tests only
python -m pytest tests/unit/ -v

# Integration tests only
python -m pytest tests/integration/ -v

# Functional tests only
python -m pytest tests/functional/ -v
```

### Specific Test Execution
```bash
# Test specific functionality
python -m pytest tests/unit/test_database_models.py::TestSignalModel::test_signal_creation -v

# Test with timeout and detailed output
python -m pytest tests/unit/test_diagnostics.py -v --tb=short
```

## Test Runner Features

The `run_all_tests.py` script has been updated to support the new structure:

```bash
# Run specific test categories
python run_all_tests.py pytest    # Run organized pytest suite
python run_all_tests.py quick     # Quick health check
python run_all_tests.py iifl      # IIFL-specific tests
python run_all_tests.py api       # API endpoint tests
```

## Benefits of New Organization

### 1. **Clear Separation of Concerns**
- Unit tests focus on individual components
- Integration tests verify component interactions
- Functional tests validate complete workflows

### 2. **Faster Test Execution**
- Run only relevant test categories during development
- Quick diagnostic tests for health checks
- Isolated performance testing

### 3. **Better Maintenance**
- Logical grouping makes tests easier to find and update
- Clear naming conventions
- Reduced test interdependencies

### 4. **Improved Debugging**
- Easier to identify which layer has issues
- More targeted test failure analysis
- Better error isolation

### 5. **CI/CD Pipeline Ready**
- Different test categories can run in parallel
- Staging-specific test execution
- Performance regression detection

## Migration Notes

### Files Moved:
- `test_iifl_holdings.py` → `tests/integration/`
- `iifl_auth_test.py` → `tests/integration/`
- `test_real_signals.py` → `tests/functional/`
- `test_logging_performance.py` → `tests/performance/`
- Backtest files → `tests/backtest/`
- All service unit tests → `tests/unit/`

### Updated References:
- `run_all_tests.py` updated to use new structure
- Test runner supports organized execution
- Documentation reflects new paths

This organization provides a solid foundation for maintaining and expanding the test suite as the trading system grows.