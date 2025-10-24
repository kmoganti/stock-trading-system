#!/usr/bin/env python3
import json

# Load contract data
with open('data/contracts_nseeq.json', 'r') as f:
    contracts = json.load(f)

# Read NIFTY100 symbols
with open('data/ind_nifty100list.csv', 'r') as f:
    lines = f.readlines()[1:]  # Skip header
    nifty100_symbols = [line.split(',')[2] for line in lines]

# Check which symbols don't have contract mapping
missing_contracts = []
found_contracts = []

for symbol in nifty100_symbols:
    # Try various forms
    candidates = [
        symbol.upper(),
        f'{symbol.upper()}-EQ',
        f'{symbol.upper()}-BE', 
        f'{symbol.upper()}-SM'
    ]
    
    # Also try alnum-only version
    alnum_only = ''.join(c for c in symbol.upper() if c.isalnum())
    candidates.append(alnum_only)
    
    found = False
    matched_key = None
    instrument_id = None
    
    for candidate in candidates:
        if candidate in contracts:
            found_contracts.append((symbol, candidate, contracts[candidate]))
            found = True
            matched_key = candidate
            instrument_id = contracts[candidate]
            break
    
    if not found:
        missing_contracts.append(symbol)

print(f'NIFTY100 Contract Resolution Analysis:')
print(f'Total NIFTY100 symbols: {len(nifty100_symbols)}')
print(f'Found instrument IDs: {len(found_contracts)}')
print(f'Missing instrument IDs: {len(missing_contracts)}')
print()
print('Missing contracts:')
for symbol in missing_contracts:
    print(f'  {symbol}')
print()
print('Sample found contracts:')
for i, (symbol, key, inst_id) in enumerate(found_contracts[:15]):
    print(f'  {symbol} -> {key} = {inst_id}')

if missing_contracts:
    print()
    print('Searching for partial matches in contract map for missing symbols:')
    for missing in missing_contracts[:10]:  # Check first 10
        print(f'\nSearching for "{missing}":')
        matches = [k for k in contracts.keys() if missing.upper() in k.upper()]
        if matches:
            for match in matches[:5]:  # Show up to 5 matches
                print(f'  Found similar: {match} = {contracts[match]}')
        else:
            print(f'  No partial matches found')