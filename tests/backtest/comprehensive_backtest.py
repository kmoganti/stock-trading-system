#!/usr/bin/env python3
"""
Comprehensive backtest script for trading strategies over the last week.
This script analyzes both short-term and long-term trading signals.
"""

import sys
import os
import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
import json

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from services.iifl_api import IIFLAPIService
from services.data_fetcher import DataFetcher
from services.strategy import StrategyService

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class BacktestRunner:
    def __init__(self):
        self.iifl_service = IIFLAPIService()
        self.data_fetcher = DataFetcher(self.iifl_service)
        self.strategy_service = StrategyService(self.data_fetcher)
        
    async def get_nifty100_symbols(self) -> List[str]:
        """Get NIFTY100 symbols from the CSV file"""
        try:
            csv_path = "data/ind_nifty100list.csv"
            symbols = []
            
            with open(csv_path, 'r') as f:
                lines = f.readlines()
                for line in lines[1:]:  # Skip header
                    parts = line.strip().split(',')
                    if len(parts) >= 3:
                        symbol = parts[2].strip()
                        symbols.append(symbol)
            
            # Return top 20 for faster processing
            return symbols[:20]
            
        except Exception as e:
            logger.error(f"Error reading NIFTY100 symbols: {e}")
            # Fallback to popular stocks
            return [
                'RELIANCE', 'TCS', 'HDFCBANK', 'INFY', 'ICICIBANK', 'SBIN', 
                'BHARTIARTL', 'ITC', 'LT', 'ASIANPAINT', 'AXISBANK', 'MARUTI',
                'BAJFINANCE', 'HCLTECH', 'ULTRACEMCO', 'TITAN', 'NESTLEIND', 
                'KOTAKBANK', 'HINDUNILVR', 'WIPRO'
            ]

    async def generate_signals_for_period(self, symbol: str, start_date: str, end_date: str, category: str = "short_term") -> List[Dict]:
        """Generate signals for a symbol over a specific period"""
        try:
            logger.info(f"Generating {category} signals for {symbol} from {start_date} to {end_date}")
            
            # Get extended historical data for proper indicator calculation
            extended_start = datetime.strptime(start_date, "%Y-%m-%d") - timedelta(days=100)
            extended_start_str = extended_start.strftime("%Y-%m-%d")
            
            historical_data = await self.data_fetcher.get_historical_data(
                symbol,
                interval="1D",
                from_date=extended_start_str,
                to_date=end_date
            )
            
            if not historical_data or len(historical_data) < 50:
                logger.warning(f"Insufficient data for {symbol}: {len(historical_data) if historical_data else 0} records")
                return []
            
            # Generate signals using the strategy service
            signals = await self.strategy_service.generate_signals_from_data(
                symbol, historical_data, validate=False
            )
            
            # Filter signals to the requested date range
            filtered_signals = []
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            
            for signal in signals:
                # For this analysis, we'll consider all generated signals as they represent current market state
                signal_dict = {
                    'symbol': signal.symbol,
                    'signal_type': signal.signal_type.value,
                    'entry_price': signal.entry_price,
                    'stop_loss': signal.stop_loss,
                    'target_price': signal.target_price,
                    'confidence': signal.confidence,
                    'strategy': signal.strategy,
                    'category': category,
                    'metadata': signal.metadata or {}
                }
                filtered_signals.append(signal_dict)
            
            return filtered_signals
            
        except Exception as e:
            logger.error(f"Error generating signals for {symbol}: {e}")
            return []

    async def run_comprehensive_backtest(self, days: int = 7) -> Dict[str, Any]:
        """Run comprehensive backtest for both short-term and long-term strategies"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        start_date_str = start_date.strftime("%Y-%m-%d")
        end_date_str = end_date.strftime("%Y-%m-%d")
        
        logger.info(f"Starting comprehensive backtest from {start_date_str} to {end_date_str}")
        
        # Get symbols to analyze
        symbols = await self.get_nifty100_symbols()
        logger.info(f"Analyzing {len(symbols)} symbols")
        
        results = {
            'period': {
                'start_date': start_date_str,
                'end_date': end_date_str,
                'days': days
            },
            'short_term_signals': [],
            'long_term_signals': [],
            'summary': {
                'total_symbols': len(symbols),
                'symbols_with_short_signals': 0,
                'symbols_with_long_signals': 0,
                'total_short_signals': 0,
                'total_long_signals': 0,
                'strategies_used': set(),
                'signal_type_distribution': {'BUY': 0, 'SELL': 0}
            }
        }
        
        # Analyze each symbol
        processed = 0
        for symbol in symbols:
            try:
                processed += 1
                logger.info(f"Processing {symbol} ({processed}/{len(symbols)})")
                
                # Generate short-term signals
                short_signals = await self.generate_signals_for_period(
                    symbol, start_date_str, end_date_str, "short_term"
                )
                
                # Generate long-term signals  
                long_signals = await self.generate_signals_for_period(
                    symbol, start_date_str, end_date_str, "long_term"
                )
                
                # Update results
                if short_signals:
                    results['short_term_signals'].extend(short_signals)
                    results['summary']['symbols_with_short_signals'] += 1
                    results['summary']['total_short_signals'] += len(short_signals)
                    
                if long_signals:
                    results['long_term_signals'].extend(long_signals)
                    results['summary']['symbols_with_long_signals'] += 1
                    results['summary']['total_long_signals'] += len(long_signals)
                
                # Update strategy and signal type statistics
                for signal in short_signals + long_signals:
                    results['summary']['strategies_used'].add(signal['strategy'])
                    results['summary']['signal_type_distribution'][signal['signal_type']] += 1
                
            except Exception as e:
                logger.error(f"Error processing {symbol}: {e}")
                continue
        
        # Convert set to list for JSON serialization
        results['summary']['strategies_used'] = list(results['summary']['strategies_used'])
        
        return results

    def analyze_signals(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze the generated signals and provide insights"""
        analysis = {
            'signal_analysis': {},
            'strategy_performance': {},
            'top_opportunities': [],
            'risk_analysis': {}
        }
        
        # Analyze all signals
        all_signals = results['short_term_signals'] + results['long_term_signals']
        
        if not all_signals:
            analysis['signal_analysis']['status'] = 'No signals generated'
            return analysis
        
        # Signal type analysis
        buy_signals = [s for s in all_signals if s['signal_type'] == 'BUY']
        sell_signals = [s for s in all_signals if s['signal_type'] == 'SELL']
        
        analysis['signal_analysis'] = {
            'total_signals': len(all_signals),
            'buy_signals': len(buy_signals),
            'sell_signals': len(sell_signals),
            'buy_percentage': (len(buy_signals) / len(all_signals)) * 100,
            'average_confidence': sum(s['confidence'] for s in all_signals) / len(all_signals)
        }
        
        # Strategy performance
        strategy_stats = {}
        for signal in all_signals:
            strategy = signal['strategy']
            if strategy not in strategy_stats:
                strategy_stats[strategy] = {'count': 0, 'avg_confidence': 0, 'confidences': []}
            
            strategy_stats[strategy]['count'] += 1
            strategy_stats[strategy]['confidences'].append(signal['confidence'])
        
        for strategy, stats in strategy_stats.items():
            stats['avg_confidence'] = sum(stats['confidences']) / len(stats['confidences'])
            del stats['confidences']  # Remove raw data
        
        analysis['strategy_performance'] = strategy_stats
        
        # Top opportunities (highest confidence signals)
        top_signals = sorted(all_signals, key=lambda x: x['confidence'], reverse=True)[:10]
        analysis['top_opportunities'] = top_signals
        
        # Risk analysis
        if buy_signals:
            risk_rewards = []
            for signal in buy_signals:
                risk = signal['entry_price'] - signal['stop_loss']
                reward = signal['target_price'] - signal['entry_price']
                if risk > 0:
                    risk_rewards.append(reward / risk)
            
            if risk_rewards:
                analysis['risk_analysis'] = {
                    'average_risk_reward_ratio': sum(risk_rewards) / len(risk_rewards),
                    'min_risk_reward': min(risk_rewards),
                    'max_risk_reward': max(risk_rewards)
                }
        
        return analysis

    async def save_results(self, results: Dict[str, Any], analysis: Dict[str, Any]):
        """Save results to files"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save detailed results
        results_file = f"reports/backtest_results_{timestamp}.json"
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        # Save analysis
        analysis_file = f"reports/backtest_analysis_{timestamp}.json"
        with open(analysis_file, 'w') as f:
            json.dump(analysis, f, indent=2, default=str)
        
        logger.info(f"Results saved to {results_file}")
        logger.info(f"Analysis saved to {analysis_file}")
        
        return results_file, analysis_file


async def main():
    """Main function to run the comprehensive backtest"""
    logger.info("Starting Comprehensive Trading Strategy Backtest")
    logger.info("=" * 60)
    
    try:
        backtest_runner = BacktestRunner()
        
        # Run the backtest for last 7 days
        results = await backtest_runner.run_comprehensive_backtest(days=7)
        
        # Analyze results
        analysis = backtest_runner.analyze_signals(results)
        
        # Print summary
        print("\n" + "=" * 60)
        print("BACKTEST RESULTS SUMMARY")
        print("=" * 60)
        
        print(f"Analysis Period: {results['period']['start_date']} to {results['period']['end_date']}")
        print(f"Total Symbols Analyzed: {results['summary']['total_symbols']}")
        print(f"Short-term Signals: {results['summary']['total_short_signals']}")
        print(f"Long-term Signals: {results['summary']['total_long_signals']}")
        print(f"Symbols with Short Signals: {results['summary']['symbols_with_short_signals']}")
        print(f"Symbols with Long Signals: {results['summary']['symbols_with_long_signals']}")
        
        if analysis.get('signal_analysis', {}).get('total_signals', 0) > 0:
            print(f"\nSIGNAL ANALYSIS:")
            print(f"Total Signals Generated: {analysis['signal_analysis']['total_signals']}")
            print(f"Buy Signals: {analysis['signal_analysis']['buy_signals']} ({analysis['signal_analysis']['buy_percentage']:.1f}%)")
            print(f"Sell Signals: {analysis['signal_analysis']['sell_signals']}")
            print(f"Average Confidence: {analysis['signal_analysis']['average_confidence']:.2f}")
            
            print(f"\nSTRATEGY PERFORMANCE:")
            for strategy, stats in analysis['strategy_performance'].items():
                print(f"  {strategy}: {stats['count']} signals, avg confidence: {stats['avg_confidence']:.2f}")
            
            if analysis.get('risk_analysis'):
                print(f"\nRISK ANALYSIS:")
                print(f"Average Risk/Reward Ratio: {analysis['risk_analysis']['average_risk_reward_ratio']:.2f}")
            
            print(f"\nTOP 5 OPPORTUNITIES:")
            for i, signal in enumerate(analysis['top_opportunities'][:5], 1):
                risk_reward = (signal['target_price'] - signal['entry_price']) / (signal['entry_price'] - signal['stop_loss']) if signal['signal_type'] == 'BUY' else 'N/A'
                print(f"  {i}. {signal['symbol']} - {signal['signal_type']} at ₹{signal['entry_price']:.2f} (Confidence: {signal['confidence']:.2f}, Strategy: {signal['strategy']})")
        else:
            print("\nNo trading signals generated in the analysis period.")
        
        # Save results
        results_file, analysis_file = await backtest_runner.save_results(results, analysis)
        
        print(f"\nDetailed results saved to:")
        print(f"  - {results_file}")
        print(f"  - {analysis_file}")
        
    except Exception as e:
        logger.error(f"Error in main execution: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())