import asyncio
import logging
from services.risk import RiskService

# Minimal stub DataFetcher to avoid network calls
class DummyDF:
    async def calculate_required_margin(self, symbol, position_size, transaction_type, price):
        # return a small margin dict or numeric
        return {"current_order_margin": 1000.0}

    async def get_portfolio_data(self):
        return {"total_pnl": 0, "positions": [], "holdings": []}

    async def get_margin_info(self):
        return {"availableMargin": 100000.0, "totalEquity": 100000.0}

async def main():
    logging.basicConfig(level=logging.INFO)
    dummy = DummyDF()
    # db_session is not used in validate_signal_risk for success path
    rs = RiskService(dummy, None)

    # Signal dict missing 'entry_price' but has 'price'
    signal = {
        'symbol': 'RELIANCE',
        'price': 2500.0,
        'stop_loss': 2450.0,
        'signal_type': 'sell'
    }

    result = await rs.validate_signal_risk(signal, position_size=1)
    print('Validation result:', result)

if __name__ == '__main__':
    asyncio.run(main())
