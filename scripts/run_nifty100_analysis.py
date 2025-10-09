import asyncio
import json
from datetime import datetime
from services.data_fetcher import DataFetcher
from services.iifl_api import IIFLAPIService
from services.strategy import StrategyService


async def main():
    iifl = IIFLAPIService()
    # Ensure auth is attempted (will create mock token in dev/test if missing)
    await iifl._ensure_authenticated()

    df = DataFetcher(iifl)
    svc = StrategyService(df)

    # Load NIFTY100 symbols
    symbols = []
    with open('data/ind_nifty100list.csv', 'r', encoding='utf-8') as f:
        lines = f.read().splitlines()
        for i, line in enumerate(lines):
            if i == 0:
                continue
            parts = line.split(',')
            if len(parts) >= 3:
                sym = parts[2].strip()
                # Normalize common formatting
                sym = sym.replace('"', '').upper()
                symbols.append(sym)

    categories = ['long_term', 'short_term', 'day_trading', 'short_selling']

    # Store signals; for short_selling we will only keep SELL signals
    results = {c: {'signals': [], 'no_data': [], 'errors': []} for c in categories}

    # We'll avoid live validation to reduce external calls: use generate_signals_from_data when possible.

    async def process_symbol(sym):
        try:
            for cat in categories:
                # Determine days/interval used by StrategyService logic
                if cat == 'day_trading':
                    interval = '5m'
                    days = 2
                elif cat == 'long_term':
                    interval = '1D'
                    days = 250
                else:
                    interval = '1D'
                    days = 100

                to_date = datetime.now().strftime('%Y-%m-%d')
                from_date = (datetime.now() - __import__('datetime').timedelta(days=days)).strftime('%Y-%m-%d')

                # Use DataFetcher to get historical data (will attempt fallbacks and cache)
                data = await df.get_historical_data(sym, interval=interval, from_date=from_date, to_date=to_date)

                if not data:
                    results[cat]['no_data'].append(sym)
                    continue

                # Generate signals from data and run validation (live price/liquidity/margin checks)
                # For short_selling we'll still run the same strategies but keep only SELL signals
                signals = await svc.generate_signals_from_data(sym, data, validate=True)
                if signals:
                    added = False
                    for s in signals:
                        # If we're running short_selling, only keep SELL signals
                        if cat == 'short_selling' and s.signal_type.value.lower() != 'sell':
                            continue
                        results[cat]['signals'].append({
                            'symbol': s.symbol,
                            'signal_type': s.signal_type.value,
                            'entry_price': s.entry_price,
                            'stop_loss': s.stop_loss,
                            'target_price': s.target_price,
                            'strategy': s.strategy,
                            'confidence': s.confidence,
                        })
                        added = True
                    if not added:
                        results[cat]['no_data'].append(sym)
                else:
                    results[cat]['no_data'].append(sym)
        except Exception as e:
            for cat in categories:
                results[cat]['errors'].append({'symbol': sym, 'error': str(e)})

    # Run with limited concurrency
    sem = asyncio.Semaphore(8)
    async def sem_task(s):
        async with sem:
            await process_symbol(s)

    tasks = [sem_task(s) for s in symbols]
    await asyncio.gather(*tasks)

    out_path = 'reports/nifty100_strategy_summary.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump({'generated_at': datetime.now().isoformat(), 'results': results}, f, indent=2)

    print(f"Analysis complete. Summary written to {out_path}")

if __name__ == '__main__':
    asyncio.run(main())
