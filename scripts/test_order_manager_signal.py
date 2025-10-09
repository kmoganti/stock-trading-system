import asyncio
import logging
from services.order_manager import OrderManager
from services.risk import RiskService

# Dummy services
class DummyIIFL:
    pass

class DummyDF:
    async def calculate_required_margin(self, *a, **k):
        return {"current_order_margin": 500.0}
    async def get_margin_info(self):
        return {"availableMargin": 10000.0, "totalEquity": 10000.0}

class DummyRisk(RiskService):
    def __init__(self):
        # avoid calling parent init which needs data_fetcher/db
        pass
    async def calculate_position_size(self, signal, available_capital):
        return 1
    async def validate_signal_risk(self, signal, position_size):
        return {"approved": True, "reasons": [], "risk_score": 0.0, "required_margin": 500.0}

async def main():
    logging.basicConfig(level=logging.INFO)
    dummy_iifl = DummyIIFL()
    dummy_df = DummyDF()
    dummy_risk = DummyRisk()
    om = OrderManager(iifl_service=dummy_iifl, risk_service=dummy_risk, data_fetcher=dummy_df, db_session=None)

    # signal_data uses 'price' not 'entry_price'
    signal_data = {
        'symbol': 'RELIANCE',
        'signal_type': 'sell',
        'price': 2600.0,
        'stop_loss': 2550.0
    }

    sig = await om.create_signal(signal_data)
    print('Created signal:', sig)

if __name__ == '__main__':
    asyncio.run(main())
