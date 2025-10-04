import os
import sys
from pathlib import Path

# Ensure project root is importable when running this script directly
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

os.environ['PAPER_TRADING'] = '1'
from services.iifl_api import IIFLAPIService
from services.order_manager import OrderManager

print('IIFLAPIService trading_enabled=', IIFLAPIService().trading_enabled, 'paper_trading=', IIFLAPIService().paper_trading)
om = OrderManager(iifl_service=IIFLAPIService())
print('OrderManager created; settings auto_trade present:', hasattr(om.settings, 'auto_trade'))
