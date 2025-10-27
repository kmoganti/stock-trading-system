#!/usr/bin/env python3
"""
Comprehensive 1-month backtest analysis for long-term and short-term screening strategies.
This script will analyze signal patterns, performance metrics, and provide detailed insights.
"""

import sys
import os
import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple
import json
from collections import defaultdict, Counter

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from services.iifl_api import IIFLAPIService
from services.data_fetcher import DataFetcher

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ComprehensiveBacktestAnalyzer:
    """Advanced backtest analyzer for multi-timeframe strategy analysis"""
    
    def __init__(self):
        self.iifl_service = IIFLAPIService()
        self.data_fetcher = DataFetcher(self.iifl_service)
        
    async def get_nifty_stocks(self) -> List[str]:
        """Get comprehensive list of NIFTY stocks for analysis"""
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
            
            # Return top 40 for comprehensive analysis
            return symbols[:40]
            
        except Exception as e:
            print(f"Error reading NIFTY symbols: {e}")
            # Extended fallback list
            return [
                'RELIANCE', 'TCS', 'HDFCBANK', 'INFY', 'ICICIBANK', 'SBIN', 
                'BHARTIARTL', 'ITC', 'LT', 'ASIANPAINT', 'AXISBANK', 'MARUTI',
                'KOTAKBANK', 'HINDUNILVR', 'BAJFINANCE', 'HCLTECH', 'WIPRO',
                'ULTRACEMCO', 'TITAN', 'NESTLEIND', 'POWERGRID', 'NTPC',
                'ONGC', 'JSWSTEEL', 'TATAMOTORS', 'BAJAJFINSV', 'M&M',
                'ADANIPORTS', 'COALINDIA', 'DIVISLAB', 'DRREDDY', 'EICHERMOT',
                'GRASIM', 'HEROMOTOCO', 'HINDALCO', 'INDUSINDBK', 'IOC',
                'BRITANNIA', 'CIPLA', 'SUNPHARMA', 'TECHM'
            ]

    def calculate_technical_indicators(self, data: List[Dict]) -> Dict[str, float]:
        """Calculate comprehensive technical indicators"""
        if not data or len(data) < 50:
            return {}
        
        try:
            # Extract price and volume data
            closes = [float(d['close']) for d in data]
            highs = [float(d['high']) for d in data]
            lows = [float(d['low']) for d in data]
            volumes = [float(d['volume']) for d in data]
            
            # Moving averages
            sma_10 = sum(closes[-10:]) / 10 if len(closes) >= 10 else closes[-1]
            sma_20 = sum(closes[-20:]) / 20 if len(closes) >= 20 else closes[-1]
            sma_50 = sum(closes[-50:]) / 50 if len(closes) >= 50 else closes[-1]
            
            # EMA calculations (simplified)
            def calculate_ema(prices, period):
                multiplier = 2 / (period + 1)
                ema = prices[0]
                for price in prices[1:]:
                    ema = (price * multiplier) + (ema * (1 - multiplier))
                return ema
            
            ema_9 = calculate_ema(closes[-30:], 9) if len(closes) >= 30 else closes[-1]
            ema_21 = calculate_ema(closes[-30:], 21) if len(closes) >= 30 else closes[-1]
            
            # RSI calculation (simplified)
            def calculate_rsi(prices, period=14):
                if len(prices) < period + 1:
                    return 50.0
                
                deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
                gains = [d if d > 0 else 0 for d in deltas[-period:]]
                losses = [-d if d < 0 else 0 for d in deltas[-period:]]
                
                avg_gain = sum(gains) / period
                avg_loss = sum(losses) / period
                
                if avg_loss == 0:
                    return 100.0
                
                rs = avg_gain / avg_loss
                return 100 - (100 / (1 + rs))
            
            rsi = calculate_rsi(closes)
            
            # Bollinger Bands
            bb_middle = sma_20
            std_dev = (sum([(price - bb_middle) ** 2 for price in closes[-20:]]) / 20) ** 0.5
            bb_upper = bb_middle + (2 * std_dev)
            bb_lower = bb_middle - (2 * std_dev)
            
            # Volume analysis
            avg_volume = sum(volumes[-20:]) / 20 if len(volumes) >= 20 else volumes[-1]
            volume_ratio = volumes[-1] / avg_volume if avg_volume > 0 else 1.0
            
            # Price momentum
            current_price = closes[-1]
            week_ago_price = closes[-7] if len(closes) >= 7 else closes[0]
            month_ago_price = closes[-30] if len(closes) >= 30 else closes[0]
            
            weekly_momentum = (current_price - week_ago_price) / week_ago_price * 100
            monthly_momentum = (current_price - month_ago_price) / month_ago_price * 100
            
            # Volatility (ATR approximation)
            true_ranges = []
            for i in range(1, min(15, len(data))):
                tr = max(
                    highs[i] - lows[i],
                    abs(highs[i] - closes[i-1]),
                    abs(lows[i] - closes[i-1])
                )
                true_ranges.append(tr)
            
            atr = sum(true_ranges) / len(true_ranges) if true_ranges else current_price * 0.02
            
            return {
                'current_price': current_price,
                'sma_10': sma_10,
                'sma_20': sma_20,
                'sma_50': sma_50,
                'ema_9': ema_9,
                'ema_21': ema_21,
                'rsi': rsi,
                'bb_upper': bb_upper,
                'bb_middle': bb_middle,
                'bb_lower': bb_lower,
                'volume_ratio': volume_ratio,
                'weekly_momentum': weekly_momentum,
                'monthly_momentum': monthly_momentum,
                'atr': atr,
                'volatility_pct': (atr / current_price) * 100
            }
            
        except Exception as e:
            print(f"Error calculating indicators: {e}")
            return {}

    def analyze_short_term_signals(self, indicators: Dict[str, float], symbol: str) -> List[Dict]:
        """Analyze short-term trading signals (1-7 days holding period)"""
        signals = []
        
        if not indicators:
            return signals
        
        current_price = indicators.get('current_price', 0)
        if current_price == 0:
            return signals
        
        # Short-term momentum strategy
        if (indicators.get('ema_9', 0) > indicators.get('ema_21', 0) and  # Bullish EMA crossover
            current_price > indicators.get('sma_10', 0) and  # Above short-term MA
            indicators.get('rsi', 50) > 45 and indicators.get('rsi', 50) < 70 and  # RSI in range
            indicators.get('volume_ratio', 0) > 0.8 and  # Volume confirmation
            indicators.get('weekly_momentum', 0) > 1.0):  # Positive momentum
            
            confidence = min(0.85, 0.6 + (indicators.get('weekly_momentum', 0) / 30))
            
            signals.append({
                'symbol': symbol,
                'signal_type': 'BUY',
                'strategy': 'short_term_momentum',
                'timeframe': 'short_term',
                'entry_price': current_price,
                'stop_loss': current_price * 0.96,  # 4% stop loss
                'target_price': current_price * 1.06,  # 6% target
                'confidence': confidence,
                'holding_period_days': 3,
                'reasoning': f"Short-term momentum: {indicators.get('weekly_momentum', 0):.1f}% weekly gain, EMA bullish",
                'indicators': {
                    'ema_9': indicators.get('ema_9'),
                    'ema_21': indicators.get('ema_21'),
                    'rsi': indicators.get('rsi'),
                    'volume_ratio': indicators.get('volume_ratio'),
                    'weekly_momentum': indicators.get('weekly_momentum')
                }
            })
        
        # Short-term mean reversion strategy
        elif (current_price < indicators.get('bb_lower', 0) and  # Oversold on BB
              indicators.get('rsi', 50) < 35 and  # RSI oversold
              indicators.get('volume_ratio', 0) > 1.2 and  # High volume
              indicators.get('weekly_momentum', 0) < -3.0):  # Significant decline
            
            signals.append({
                'symbol': symbol,
                'signal_type': 'BUY',
                'strategy': 'short_term_mean_reversion',
                'timeframe': 'short_term',
                'entry_price': current_price,
                'stop_loss': current_price * 0.94,  # 6% stop loss (wider for mean reversion)
                'target_price': indicators.get('bb_middle', current_price * 1.04),  # Target back to BB middle
                'confidence': 0.70,
                'holding_period_days': 5,
                'reasoning': f"Oversold bounce candidate: RSI {indicators.get('rsi', 0):.1f}, below BB lower",
                'indicators': {
                    'bb_position': (current_price - indicators.get('bb_lower', current_price)) / current_price * 100,
                    'rsi': indicators.get('rsi'),
                    'volume_ratio': indicators.get('volume_ratio'),
                    'weekly_momentum': indicators.get('weekly_momentum')
                }
            })
        
        # Short-term bearish signals
        elif (indicators.get('ema_9', 0) < indicators.get('ema_21', 0) and  # Bearish EMA crossover
              current_price < indicators.get('sma_10', 0) and  # Below short-term MA
              indicators.get('rsi', 50) > 30 and indicators.get('rsi', 50) < 55 and  # RSI in range
              indicators.get('weekly_momentum', 0) < -2.0):  # Negative momentum
            
            signals.append({
                'symbol': symbol,
                'signal_type': 'SELL',
                'strategy': 'short_term_momentum',
                'timeframe': 'short_term',
                'entry_price': current_price,
                'stop_loss': current_price * 1.04,  # 4% stop loss
                'target_price': current_price * 0.94,  # 6% target
                'confidence': 0.65,
                'holding_period_days': 3,
                'reasoning': f"Short-term bearish momentum: {indicators.get('weekly_momentum', 0):.1f}% weekly decline",
                'indicators': {
                    'ema_9': indicators.get('ema_9'),
                    'ema_21': indicators.get('ema_21'),
                    'weekly_momentum': indicators.get('weekly_momentum')
                }
            })
        
        return signals

    def analyze_long_term_signals(self, indicators: Dict[str, float], symbol: str) -> List[Dict]:
        """Analyze long-term trading signals (2-12 weeks holding period)"""
        signals = []
        
        if not indicators:
            return signals
        
        current_price = indicators.get('current_price', 0)
        if current_price == 0:
            return signals
        
        # Long-term trend following
        if (current_price > indicators.get('sma_50', 0) and  # Above long-term MA
            indicators.get('sma_20', 0) > indicators.get('sma_50', 0) and  # MA alignment
            indicators.get('monthly_momentum', 0) > 5.0 and  # Strong monthly momentum
            indicators.get('rsi', 50) > 40 and indicators.get('rsi', 50) < 75):  # RSI in range
            
            confidence = min(0.80, 0.6 + (indicators.get('monthly_momentum', 0) / 50))
            
            signals.append({
                'symbol': symbol,
                'signal_type': 'BUY',
                'strategy': 'long_term_trend_following',
                'timeframe': 'long_term',
                'entry_price': current_price,
                'stop_loss': indicators.get('sma_50', current_price * 0.9),  # Stop below SMA50
                'target_price': current_price * 1.20,  # 20% target for long-term
                'confidence': confidence,
                'holding_period_days': 60,
                'reasoning': f"Long-term uptrend: {indicators.get('monthly_momentum', 0):.1f}% monthly gain, above SMA50",
                'indicators': {
                    'sma_20': indicators.get('sma_20'),
                    'sma_50': indicators.get('sma_50'),
                    'monthly_momentum': indicators.get('monthly_momentum'),
                    'rsi': indicators.get('rsi')
                }
            })
        
        # Long-term value/quality signals
        elif (current_price > indicators.get('sma_20', 0) and  # Above intermediate MA
              indicators.get('volatility_pct', 10) < 3.0 and  # Low volatility (quality)
              indicators.get('monthly_momentum', 0) > 2.0 and  # Steady positive momentum
              indicators.get('rsi', 50) > 45 and indicators.get('rsi', 50) < 65):  # Neutral RSI
            
            signals.append({
                'symbol': symbol,
                'signal_type': 'BUY',
                'strategy': 'long_term_quality_growth',
                'timeframe': 'long_term',
                'entry_price': current_price,
                'stop_loss': current_price * 0.88,  # 12% stop loss for quality plays
                'target_price': current_price * 1.25,  # 25% target for quality growth
                'confidence': 0.75,
                'holding_period_days': 90,
                'reasoning': f"Quality growth: Low volatility {indicators.get('volatility_pct', 0):.1f}%, steady momentum",
                'indicators': {
                    'volatility_pct': indicators.get('volatility_pct'),
                    'monthly_momentum': indicators.get('monthly_momentum'),
                    'rsi': indicators.get('rsi')
                }
            })
        
        # Long-term contrarian signals
        elif (current_price < indicators.get('sma_50', 0) * 0.9 and  # Significant discount to SMA50
              indicators.get('monthly_momentum', 0) < -10.0 and  # Oversold on monthly basis
              indicators.get('rsi', 50) < 30 and  # RSI oversold
              indicators.get('volume_ratio', 0) > 1.5):  # High volume (capitulation)
            
            signals.append({
                'symbol': symbol,
                'signal_type': 'BUY',
                'strategy': 'long_term_contrarian',
                'timeframe': 'long_term',
                'entry_price': current_price,
                'stop_loss': current_price * 0.85,  # 15% stop loss for contrarian
                'target_price': indicators.get('sma_50', current_price * 1.15),  # Target back to SMA50
                'confidence': 0.65,
                'holding_period_days': 120,
                'reasoning': f"Contrarian opportunity: {indicators.get('monthly_momentum', 0):.1f}% monthly decline, RSI {indicators.get('rsi', 0):.1f}",
                'indicators': {
                    'sma_50_discount': (current_price / indicators.get('sma_50', current_price) - 1) * 100,
                    'monthly_momentum': indicators.get('monthly_momentum'),
                    'rsi': indicators.get('rsi'),
                    'volume_ratio': indicators.get('volume_ratio')
                }
            })
        
        return signals

    async def run_comprehensive_backtest(self, days: int = 30) -> Dict[str, Any]:
        """Run comprehensive backtest for specified period"""
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        print(f"\n{'='*80}")
        print(f"COMPREHENSIVE BACKTEST ANALYSIS - {days} DAYS")
        print(f"{'='*80}")
        print(f"Analysis Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
        
        # Get symbols to analyze
        symbols = await self.get_nifty_stocks()
        print(f"Analyzing {len(symbols)} NIFTY stocks")
        print(f"Strategies: Short-term (1-7 days) & Long-term (2-12 weeks)")
        print()
        
        results = {
            'analysis_metadata': {
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d'),
                'total_symbols': len(symbols),
                'analysis_timestamp': datetime.now().isoformat()
            },
            'short_term_signals': [],
            'long_term_signals': [],
            'performance_metrics': {},
            'sector_analysis': defaultdict(list),
            'summary': {
                'symbols_analyzed': 0,
                'symbols_with_signals': 0,
                'total_signals': 0,
                'short_term_count': 0,
                'long_term_count': 0,
                'buy_signals': 0,
                'sell_signals': 0,
                'strategies_used': Counter(),
                'avg_confidence_short': 0.0,
                'avg_confidence_long': 0.0
            }
        }
        
        # Analyze each symbol
        processed = 0
        for symbol in symbols:
            try:
                processed += 1
                if processed % 10 == 0:
                    print(f"Progress: {processed}/{len(symbols)} symbols analyzed...")
                
                # Get extended historical data for comprehensive analysis
                extended_start = start_date - timedelta(days=120)  # Extra data for indicators
                historical_data = await self.data_fetcher.get_historical_data(
                    symbol,
                    interval="1D",
                    from_date=extended_start.strftime("%Y-%m-%d"),
                    to_date=end_date.strftime("%Y-%m-%d")
                )
                
                if not historical_data or len(historical_data) < 50:
                    continue
                
                results['summary']['symbols_analyzed'] += 1
                
                # Calculate technical indicators
                indicators = self.calculate_technical_indicators(historical_data)
                if not indicators:
                    continue
                
                # Generate short-term signals
                short_signals = self.analyze_short_term_signals(indicators, symbol)
                
                # Generate long-term signals
                long_signals = self.analyze_long_term_signals(indicators, symbol)
                
                # Process signals
                all_signals = short_signals + long_signals
                if all_signals:
                    results['summary']['symbols_with_signals'] += 1
                    
                    for signal in all_signals:
                        # Add symbol sector info (simplified mapping)
                        signal['sector'] = self.get_symbol_sector(symbol)
                        results['sector_analysis'][signal['sector']].append(signal)
                        
                        if signal['timeframe'] == 'short_term':
                            results['short_term_signals'].append(signal)
                            results['summary']['short_term_count'] += 1
                        else:
                            results['long_term_signals'].append(signal)
                            results['summary']['long_term_count'] += 1
                        
                        results['summary']['strategies_used'][signal['strategy']] += 1
                        
                        if signal['signal_type'] == 'BUY':
                            results['summary']['buy_signals'] += 1
                        else:
                            results['summary']['sell_signals'] += 1
                
                results['summary']['total_signals'] += len(all_signals)
                
            except Exception as e:
                print(f"Error processing {symbol}: {e}")
                continue
        
        # Calculate performance metrics
        results['performance_metrics'] = self.calculate_performance_metrics(results)
        
        # Calculate averages
        if results['short_term_signals']:
            results['summary']['avg_confidence_short'] = sum(s['confidence'] for s in results['short_term_signals']) / len(results['short_term_signals'])
        
        if results['long_term_signals']:
            results['summary']['avg_confidence_long'] = sum(s['confidence'] for s in results['long_term_signals']) / len(results['long_term_signals'])
        
        return results

    def get_symbol_sector(self, symbol: str) -> str:
        """Get sector classification for symbol (simplified mapping)"""
        sector_map = {
            # Banking & Financial
            'HDFCBANK': 'Banking', 'ICICIBANK': 'Banking', 'SBIN': 'Banking', 'AXISBANK': 'Banking',
            'KOTAKBANK': 'Banking', 'INDUSINDBK': 'Banking', 'BAJFINANCE': 'Financial Services',
            'BAJAJFINSV': 'Financial Services',
            
            # Technology
            'TCS': 'Technology', 'INFY': 'Technology', 'HCLTECH': 'Technology', 'WIPRO': 'Technology',
            'TECHM': 'Technology',
            
            # Auto
            'MARUTI': 'Automobile', 'TATAMOTORS': 'Automobile', 'M&M': 'Automobile', 
            'BAJAJ-AUTO': 'Automobile', 'EICHERMOT': 'Automobile', 'HEROMOTOCO': 'Automobile',
            
            # Oil & Gas
            'RELIANCE': 'Oil & Gas', 'ONGC': 'Oil & Gas', 'IOC': 'Oil & Gas',
            
            # Steel & Materials
            'JSWSTEEL': 'Steel', 'HINDALCO': 'Metals', 'COALINDIA': 'Mining', 'GRASIM': 'Materials',
            
            # Consumer
            'ITC': 'Consumer Goods', 'HINDUNILVR': 'Consumer Goods', 'NESTLEIND': 'Consumer Goods',
            'BRITANNIA': 'Consumer Goods', 'TITAN': 'Consumer Goods',
            
            # Pharma
            'SUNPHARMA': 'Pharmaceuticals', 'DRREDDY': 'Pharmaceuticals', 'CIPLA': 'Pharmaceuticals',
            'DIVISLAB': 'Pharmaceuticals',
            
            # Others
            'LT': 'Construction', 'ULTRACEMCO': 'Cement', 'ASIANPAINT': 'Paints',
            'BHARTIARTL': 'Telecom', 'POWERGRID': 'Utilities', 'NTPC': 'Utilities'
        }
        
        return sector_map.get(symbol, 'Others')

    def calculate_performance_metrics(self, results: Dict) -> Dict:
        """Calculate detailed performance metrics"""
        metrics = {
            'signal_quality': {},
            'strategy_performance': {},
            'sector_distribution': {},
            'risk_metrics': {}
        }
        
        all_signals = results['short_term_signals'] + results['long_term_signals']
        
        if not all_signals:
            return metrics
        
        # Signal quality metrics
        confidences = [s['confidence'] for s in all_signals]
        risk_rewards = []
        
        for signal in all_signals:
            if signal['signal_type'] == 'BUY':
                risk = signal['entry_price'] - signal['stop_loss']
                reward = signal['target_price'] - signal['entry_price']
                if risk > 0:
                    risk_rewards.append(reward / risk)
        
        metrics['signal_quality'] = {
            'avg_confidence': sum(confidences) / len(confidences),
            'min_confidence': min(confidences),
            'max_confidence': max(confidences),
            'avg_risk_reward_ratio': sum(risk_rewards) / len(risk_rewards) if risk_rewards else 0,
            'signals_above_70_confidence': len([c for c in confidences if c >= 0.7]),
            'signal_quality_score': len([c for c in confidences if c >= 0.7]) / len(confidences) * 100
        }
        
        # Strategy performance
        strategy_stats = defaultdict(lambda: {'count': 0, 'confidences': [], 'risk_rewards': []})
        
        for signal in all_signals:
            strategy = signal['strategy']
            strategy_stats[strategy]['count'] += 1
            strategy_stats[strategy]['confidences'].append(signal['confidence'])
            
            if signal['signal_type'] == 'BUY':
                risk = signal['entry_price'] - signal['stop_loss']
                reward = signal['target_price'] - signal['entry_price']
                if risk > 0:
                    strategy_stats[strategy]['risk_rewards'].append(reward / risk)
        
        for strategy, stats in strategy_stats.items():
            metrics['strategy_performance'][strategy] = {
                'signal_count': stats['count'],
                'avg_confidence': sum(stats['confidences']) / len(stats['confidences']),
                'avg_risk_reward': sum(stats['risk_rewards']) / len(stats['risk_rewards']) if stats['risk_rewards'] else 0
            }
        
        # Sector distribution
        sector_counts = Counter([signal['sector'] for signal in all_signals])
        total_signals = sum(sector_counts.values())
        
        for sector, count in sector_counts.items():
            metrics['sector_distribution'][sector] = {
                'signal_count': count,
                'percentage': (count / total_signals) * 100
            }
        
        # Risk metrics
        stop_loss_distances = []
        target_distances = []
        
        for signal in all_signals:
            if signal['signal_type'] == 'BUY':
                stop_distance = (signal['entry_price'] - signal['stop_loss']) / signal['entry_price'] * 100
                target_distance = (signal['target_price'] - signal['entry_price']) / signal['entry_price'] * 100
                stop_loss_distances.append(stop_distance)
                target_distances.append(target_distance)
        
        if stop_loss_distances and target_distances:
            metrics['risk_metrics'] = {
                'avg_stop_loss_pct': sum(stop_loss_distances) / len(stop_loss_distances),
                'avg_target_pct': sum(target_distances) / len(target_distances),
                'max_risk_per_trade': max(stop_loss_distances),
                'min_risk_per_trade': min(stop_loss_distances)
            }
        
        return metrics

    async def save_results(self, results: Dict[str, Any], days: int):
        """Save comprehensive results to files"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save detailed results
        results_file = f"reports/comprehensive_backtest_{days}d_{timestamp}.json"
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"\n📊 Detailed results saved to: {results_file}")
        return results_file

    def print_comprehensive_summary(self, results: Dict[str, Any]):
        """Print detailed summary of results"""
        
        print(f"\n{'='*80}")
        print("COMPREHENSIVE BACKTEST RESULTS")
        print(f"{'='*80}")
        
        summary = results['summary']
        metrics = results['performance_metrics']
        
        # Basic statistics
        print(f"\n📈 ANALYSIS OVERVIEW")
        print(f"   Symbols Analyzed: {summary['symbols_analyzed']}")
        print(f"   Symbols with Signals: {summary['symbols_with_signals']} ({summary['symbols_with_signals']/summary['symbols_analyzed']*100:.1f}%)")
        print(f"   Total Signals Generated: {summary['total_signals']}")
        
        # Signal breakdown
        print(f"\n📊 SIGNAL BREAKDOWN")
        print(f"   Short-term Signals: {summary['short_term_count']} ({summary['short_term_count']/summary['total_signals']*100:.1f}%)")
        print(f"   Long-term Signals: {summary['long_term_count']} ({summary['long_term_count']/summary['total_signals']*100:.1f}%)")
        print(f"   Buy Signals: {summary['buy_signals']} ({summary['buy_signals']/summary['total_signals']*100:.1f}%)")
        print(f"   Sell Signals: {summary['sell_signals']} ({summary['sell_signals']/summary['total_signals']*100:.1f}%)")
        
        # Quality metrics
        if metrics.get('signal_quality'):
            quality = metrics['signal_quality']
            print(f"\n🎯 SIGNAL QUALITY METRICS")
            print(f"   Average Confidence: {quality['avg_confidence']:.2f}")
            print(f"   Confidence Range: {quality['min_confidence']:.2f} - {quality['max_confidence']:.2f}")
            print(f"   Average Risk/Reward Ratio: {quality['avg_risk_reward_ratio']:.2f}")
            print(f"   High Quality Signals (>70% confidence): {quality['signals_above_70_confidence']} ({quality['signal_quality_score']:.1f}%)")
        
        # Strategy performance
        if metrics.get('strategy_performance'):
            print(f"\n🔧 STRATEGY PERFORMANCE")
            for strategy, stats in metrics['strategy_performance'].items():
                print(f"   {strategy}:")
                print(f"     Signals: {stats['signal_count']}")
                print(f"     Avg Confidence: {stats['avg_confidence']:.2f}")
                print(f"     Avg Risk/Reward: {stats['avg_risk_reward']:.2f}")
        
        # Sector analysis
        if metrics.get('sector_distribution'):
            print(f"\n🏭 SECTOR DISTRIBUTION")
            sorted_sectors = sorted(metrics['sector_distribution'].items(), 
                                  key=lambda x: x[1]['signal_count'], reverse=True)
            for sector, stats in sorted_sectors[:8]:  # Top 8 sectors
                print(f"   {sector}: {stats['signal_count']} signals ({stats['percentage']:.1f}%)")
        
        # Top opportunities
        all_signals = results['short_term_signals'] + results['long_term_signals']
        if all_signals:
            print(f"\n🏆 TOP 10 OPPORTUNITIES")
            top_signals = sorted(all_signals, key=lambda x: x['confidence'], reverse=True)[:10]
            
            for i, signal in enumerate(top_signals, 1):
                risk = abs(signal['entry_price'] - signal['stop_loss'])
                reward = abs(signal['target_price'] - signal['entry_price'])
                rr_ratio = reward / risk if risk > 0 else 0
                
                print(f"   {i:2d}. {signal['symbol']} ({signal['sector']}) - {signal['signal_type']} [{signal['timeframe']}]")
                print(f"       Strategy: {signal['strategy']}")
                print(f"       Entry: ₹{signal['entry_price']:.2f} | Target: ₹{signal['target_price']:.2f} | Stop: ₹{signal['stop_loss']:.2f}")
                print(f"       Confidence: {signal['confidence']:.2f} | R/R: {rr_ratio:.2f} | Hold: {signal['holding_period_days']}d")
                print(f"       Reasoning: {signal['reasoning']}")
                print()


async def main():
    """Main execution function"""
    try:
        analyzer = ComprehensiveBacktestAnalyzer()
        
        # Run 1-month comprehensive backtest
        results = await analyzer.run_comprehensive_backtest(days=30)
        
        # Print comprehensive summary
        analyzer.print_comprehensive_summary(results)
        
        # Save results
        await analyzer.save_results(results, 30)
        
        print(f"\n{'='*80}")
        print("✅ Comprehensive backtest analysis completed successfully!")
        print(f"{'='*80}")
        
    except Exception as e:
        print(f"Error in main execution: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())