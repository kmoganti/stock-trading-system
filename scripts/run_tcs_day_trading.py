import asyncio
import os
import json
from datetime import datetime, timedelta
from services.iifl_api import IIFLAPIService
from services.data_fetcher import DataFetcher
from services.strategy import StrategyService

async def run():
    # safety flags
    DRY_RUN = os.getenv('DRY_RUN', 'True').lower() in ('1','true','yes')
    VALIDATE = os.getenv('VALIDATE', 'True').lower() in ('1','true','yes')

    iifl = IIFLAPIService()
    ok = await iifl._ensure_authenticated()
    if not ok:
        print('Authentication failed, aborting')
        return 1

    df = DataFetcher(iifl)
    svc = StrategyService(df)

    symbol = 'TCS'
    category = 'day_trading'

    # Prepare dates for 2 days of 5m data as StrategyService expects
    to_date = datetime.now()
    from_date = to_date - timedelta(days=2)

    print(f"Running day_trading screening for {symbol} (DRY_RUN={DRY_RUN}, VALIDATE={VALIDATE})")

    # Fetch historical data
    data = await df.get_historical_data(symbol, interval='5m', from_date=from_date.strftime('%Y-%m-%d'), to_date=to_date.strftime('%Y-%m-%d'))

    # Stop if null/empty response
    if not data:
        print('Historical data fetch returned null/empty. Aborting.')
        return 2

    # Call strategy generation using pre-fetched data and validation
    try:
        signals = await svc.generate_signals_from_data(symbol, data, strategy_name=None, validate=VALIDATE)
    except Exception as e:
        print('Error while generating signals:', e)
        return 3

    # If the IIFL responses used by validation were NULL or Not OK the service would have returned no signals
    if signals is None:
        print('Service returned NULL for signals. Aborting.')
        return 4

    if not signals:
        print('No signals generated for TCS.')
    else:
        print(f'Generated {len(signals)} signal(s):')
        for s in signals:
            print('-', s.strategy, s.signal_type.value, s.entry_price, s.stop_loss, s.target_price, 'conf', s.confidence)

    # Save short report
    out = {
        'symbol': symbol,
        'generated_at': datetime.now().isoformat(),
        'signals': [
            {
                'strategy': s.strategy,
                'signal_type': s.signal_type.value,
                'entry_price': s.entry_price,
                'stop_loss': s.stop_loss,
                'target_price': s.target_price,
                'confidence': s.confidence,
            } for s in signals
        ]
    }

    with open('reports/tcs_day_trading_summary.json', 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=2)

    print('Done. Summary saved to reports/tcs_day_trading_summary.json')
    return 0

if __name__ == '__main__':
    code = asyncio.run(run())
    raise SystemExit(code)
