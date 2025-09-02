#!/usr/bin/env python3
"""
Test portfolio data processing with real IIFL holdings
"""

import asyncio
import sys
import os
import json

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.iifl_api import IIFLAPIService
from services.data_fetcher import DataFetcher

async def test_portfolio_processing():
    """Test portfolio data processing with real IIFL data"""
    print("=== Portfolio Data Processing Test ===\n")
    
    # Initialize services
    iifl_service = IIFLAPIService()
    data_fetcher = DataFetcher(iifl_service)
    
    # Test authentication
    auth_result = await iifl_service.authenticate()
    print(f"Authentication: {'SUCCESS' if auth_result else 'FAILED'}")
    
    if not iifl_service.session_token.startswith('mock_'):
        print("Using real IIFL data\n")
        
        # Test portfolio data processing
        print("Testing portfolio data processing...")
        portfolio_data = await data_fetcher.get_portfolio_data()
        
        print(f"Holdings count: {len(portfolio_data.get('holdings', []))}")
        print(f"Positions count: {len(portfolio_data.get('positions', []))}")
        print(f"Total value: Rs.{portfolio_data.get('total_value', 0):,.2f}")
        print(f"Total invested: Rs.{portfolio_data.get('total_invested', 0):,.2f}")
        print(f"Total P&L: Rs.{portfolio_data.get('total_pnl', 0):,.2f}")
        print(f"Total P&L %: {portfolio_data.get('total_pnl_percent', 0):.2f}%")
        
        if portfolio_data.get('holdings'):
            print("\nSample holdings:")
            for i, holding in enumerate(portfolio_data['holdings'][:3]):
                print(f"  {i+1}. {holding.get('symbol')} - {holding.get('quantity')} shares")
                print(f"     Avg: Rs.{holding.get('avg_price', 0):.2f}, LTP: Rs.{holding.get('ltp', 0):.2f}")
                print(f"     P&L: Rs.{holding.get('pnl', 0):,.2f} ({holding.get('pnl_percent', 0):.2f}%)")
        
        if portfolio_data.get('positions'):
            print("\nSample positions:")
            for i, position in enumerate(portfolio_data['positions'][:3]):
                print(f"  {i+1}. {position.get('symbol')} - {position.get('quantity')} shares")
                print(f"     P&L: Rs.{position.get('pnl', 0):,.2f}")
    else:
        print("Using mock data - update auth code in .env for live testing")

if __name__ == "__main__":
    asyncio.run(test_portfolio_processing())
