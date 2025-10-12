#!/usr/bin/env python3
"""
Comprehensive Short Selling & Day Trading Backtest Analysis
===========================================================

Analyzes past 30-day data for:
1. Short Selling Opportunities (bearish reversals, overbought conditions)
2. Day Trading Signals (intraday momentum, scalping setups)

Focus Areas:
- RSI overbought (>70) short selling signals
- Bearish divergence patterns  
- Resistance level breakdowns
- Gap analysis for day trading
- Opening range breakouts
- Intraday momentum scalps
- Volume-weighted price action
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import numpy as np
import pandas as pd

# Import our services
from services.iifl_api import IIFLAPIService
from services.data_fetcher import DataFetcher
from services.strategy import StrategyService
from config.settings import get_settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ShortSellingDayTradingAnalyzer:
    """Advanced analyzer for short selling and day trading strategies"""
    
    def __init__(self):
        self.settings = get_settings()
        self.iifl = IIFLAPIService()
        self.data_fetcher = DataFetcher(self.iifl)
        self.strategy_service = StrategyService(self.data_fetcher)
        
        # Analysis period: last 30 days
        self.end_date = datetime.now()
        self.start_date = self.end_date - timedelta(days=30)
        
        # NIFTY 100 symbols for comprehensive analysis
        self.symbols = [
            'RELIANCE', 'TCS', 'HDFCBANK', 'INFY', 'HINDUNILVR', 'ICICIBANK', 'KOTAKBANK',
            'LT', 'ITC', 'AXISBANK', 'SBIN', 'BHARTIARTL', 'ASIANPAINT', 'MARUTI', 'BAJFINANCE',
            'HCLTECH', 'WIPRO', 'ULTRACEMCO', 'TITAN', 'NESTLEIND', 'POWERGRID', 'NTPC',
            'TECHM', 'SUNPHARMA', 'JSWSTEEL', 'TATAMOTORS', 'COALINDIA', 'INDUSINDBK', 'GRASIM',
            'BRITANNIA', 'CIPLA', 'EICHERMOT', 'HEROMOTOCO', 'BPCL', 'DRREDDY', 'ADANIENT',
            'BAJAJFINSV', 'TATACONSUM', 'ONGC', 'ADANIPORTS', 'APOLLOHOSP', 'DIVISLAB'
        ]
        
    async def calculate_enhanced_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate enhanced indicators for short selling and day trading"""
        if len(df) < 50:
            return df
            
        try:
            # Basic price indicators
            df['sma_20'] = df['close'].rolling(window=20).mean()
            df['sma_50'] = df['close'].rolling(window=50).mean()
            df['ema_9'] = df['close'].ewm(span=9).mean()
            df['ema_21'] = df['close'].ewm(span=21).mean()
            
            # Volatility indicators
            df['atr'] = self._calculate_atr(df)
            df['bb_upper'], df['bb_middle'], df['bb_lower'] = self._calculate_bollinger_bands(df)
            
            # Momentum indicators
            df['rsi'] = self._calculate_rsi(df['close'])
            df['macd'], df['macd_signal'] = self._calculate_macd(df['close'])
            
            # Volume indicators
            df['volume_sma'] = df['volume'].rolling(window=20).mean()
            df['volume_ratio'] = df['volume'] / df['volume_sma']
            df['volume_weighted_price'] = (df['close'] * df['volume']).rolling(window=20).sum() / df['volume'].rolling(window=20).sum()
            
            # Short selling specific indicators
            df['resistance_level'] = df['high'].rolling(window=20).max()
            df['support_level'] = df['low'].rolling(window=20).min()
            df['price_vs_resistance'] = (df['close'] - df['resistance_level']) / df['resistance_level']
            df['price_vs_support'] = (df['close'] - df['support_level']) / df['support_level']
            
            # Day trading specific indicators
            df['daily_range'] = df['high'] - df['low']
            df['gap_up'] = (df['open'] - df['close'].shift(1)) / df['close'].shift(1)
            df['gap_down'] = (df['close'].shift(1) - df['open']) / df['close'].shift(1)
            df['opening_momentum'] = (df['close'] - df['open']) / df['open']
            
            # Intraday patterns
            df['morning_star'] = self._detect_morning_star(df)
            df['evening_star'] = self._detect_evening_star(df)
            df['hammer'] = self._detect_hammer(df)
            df['shooting_star'] = self._detect_shooting_star(df)
            
            return df
            
        except Exception as e:
            logger.error(f"Error calculating enhanced indicators: {e}")
            return df
    
    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate Average True Range"""
        high_low = df['high'] - df['low']
        high_close_prev = np.abs(df['high'] - df['close'].shift())
        low_close_prev = np.abs(df['low'] - df['close'].shift())
        
        true_range = pd.concat([high_low, high_close_prev, low_close_prev], axis=1).max(axis=1)
        return true_range.rolling(window=period).mean()
    
    def _calculate_bollinger_bands(self, df: pd.DataFrame, period: int = 20, std: float = 2) -> tuple:
        """Calculate Bollinger Bands"""
        sma = df['close'].rolling(window=period).mean()
        std_dev = df['close'].rolling(window=period).std()
        
        upper = sma + (std_dev * std)
        lower = sma - (std_dev * std)
        
        return upper, sma, lower
    
    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate Relative Strength Index"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    
    def _calculate_macd(self, prices: pd.Series) -> tuple:
        """Calculate MACD and Signal Line"""
        ema_12 = prices.ewm(span=12).mean()
        ema_26 = prices.ewm(span=26).mean()
        macd = ema_12 - ema_26
        signal = macd.ewm(span=9).mean()
        
        return macd, signal
    
    def _detect_morning_star(self, df: pd.DataFrame) -> pd.Series:
        """Detect Morning Star bullish reversal pattern"""
        conditions = [
            # First candle: bearish
            (df['close'].shift(2) < df['open'].shift(2)),
            # Second candle: small body (doji-like)
            (np.abs(df['close'].shift(1) - df['open'].shift(1)) < 0.3 * (df['high'].shift(1) - df['low'].shift(1))),
            # Third candle: bullish with gap up
            (df['close'] > df['open']),
            (df['open'] > df['close'].shift(1))
        ]
        
        return pd.Series(np.all(conditions, axis=0), index=df.index)
    
    def _detect_evening_star(self, df: pd.DataFrame) -> pd.Series:
        """Detect Evening Star bearish reversal pattern"""
        conditions = [
            # First candle: bullish
            (df['close'].shift(2) > df['open'].shift(2)),
            # Second candle: small body (doji-like)
            (np.abs(df['close'].shift(1) - df['open'].shift(1)) < 0.3 * (df['high'].shift(1) - df['low'].shift(1))),
            # Third candle: bearish with gap down
            (df['close'] < df['open']),
            (df['open'] < df['close'].shift(1))
        ]
        
        return pd.Series(np.all(conditions, axis=0), index=df.index)
    
    def _detect_hammer(self, df: pd.DataFrame) -> pd.Series:
        """Detect Hammer bullish reversal pattern"""
        body = np.abs(df['close'] - df['open'])
        lower_shadow = np.minimum(df['close'], df['open']) - df['low']
        upper_shadow = df['high'] - np.maximum(df['close'], df['open'])
        
        conditions = [
            (lower_shadow >= 2 * body),  # Long lower shadow
            (upper_shadow <= 0.1 * body),  # Very small upper shadow
            (body > 0)  # Has a body
        ]
        
        return pd.Series(np.all(conditions, axis=0), index=df.index)
    
    def _detect_shooting_star(self, df: pd.DataFrame) -> pd.Series:
        """Detect Shooting Star bearish reversal pattern"""
        body = np.abs(df['close'] - df['open'])
        lower_shadow = np.minimum(df['close'], df['open']) - df['low']
        upper_shadow = df['high'] - np.maximum(df['close'], df['open'])
        
        conditions = [
            (upper_shadow >= 2 * body),  # Long upper shadow
            (lower_shadow <= 0.1 * body),  # Very small lower shadow
            (body > 0)  # Has a body
        ]
        
        return pd.Series(np.all(conditions, axis=0), index=df.index)
    
    async def detect_short_selling_signals(self, df: pd.DataFrame, symbol: str) -> List[Dict[str, Any]]:
        """Detect short selling opportunities"""
        signals = []
        
        if len(df) < 50:
            return signals
        
        for i in range(50, len(df)):
            current = df.iloc[i]
            previous = df.iloc[i-1]
            
            # Short Selling Strategy 1: RSI Overbought + Resistance Rejection
            if (current['rsi'] > 75 and 
                current['close'] >= current['bb_upper'] and
                current['close'] < current['resistance_level'] * 0.99 and  # Failed to break resistance
                current['volume_ratio'] > 1.5):  # High volume rejection
                
                entry_price = current['close']
                stop_loss = current['resistance_level'] * 1.01  # 1% above resistance
                target_price = current['support_level'] * 1.02  # Near support level
                
                risk = (stop_loss - entry_price) / entry_price
                reward = (entry_price - target_price) / entry_price
                
                if risk > 0 and reward > 0 and reward/risk >= 1.5:  # Min 1.5:1 R/R
                    signals.append({
                        'symbol': symbol,
                        'strategy': 'short_selling_overbought',
                        'signal_type': 'SELL',
                        'entry_price': entry_price,
                        'stop_loss': stop_loss,
                        'target_price': target_price,
                        'confidence': min(0.85, 0.5 + (current['rsi'] - 70) * 0.01 + current['volume_ratio'] * 0.1),
                        'risk_reward_ratio': reward / risk,
                        'date': current['date'],
                        'holding_period_days': 3,  # Short-term short selling
                        'metadata': {
                            'rsi': current['rsi'],
                            'resistance_rejection': True,
                            'volume_spike': current['volume_ratio'],
                            'bb_position': 'above_upper'
                        }
                    })
            
            # Short Selling Strategy 2: Bearish Divergence
            if (i >= 55 and 
                current['close'] > df.iloc[i-5]['close'] and  # Price making higher high
                current['rsi'] < df.iloc[i-5]['rsi'] and      # RSI making lower high (divergence)
                current['rsi'] > 65 and                        # Still overbought territory
                current['evening_star']):                      # Evening star pattern
                
                entry_price = current['close']
                stop_loss = current['close'] * 1.04  # 4% stop loss
                target_price = current['close'] * 0.92  # 8% target (2:1 R/R)
                
                signals.append({
                    'symbol': symbol,
                    'strategy': 'short_selling_divergence',
                    'signal_type': 'SELL',
                    'entry_price': entry_price,
                    'stop_loss': stop_loss,
                    'target_price': target_price,
                    'confidence': 0.75,
                    'risk_reward_ratio': 2.0,
                    'date': current['date'],
                    'holding_period_days': 5,  # Medium-term short selling
                    'metadata': {
                        'bearish_divergence': True,
                        'evening_star': True,
                        'rsi': current['rsi']
                    }
                })
            
            # Short Selling Strategy 3: Gap Down Momentum
            if (current['gap_down'] > 0.02 and  # Gap down >2%
                current['rsi'] < 45 and          # Momentum continuation
                current['volume_ratio'] > 2.0 and # High volume
                current['close'] < current['open']):  # Bearish follow-through
                
                entry_price = current['close']
                stop_loss = current['open']  # Gap fill stop
                target_price = current['support_level'] * 1.01
                
                risk = (stop_loss - entry_price) / entry_price
                reward = (entry_price - target_price) / entry_price
                
                if risk > 0 and reward > 0 and reward/risk >= 1.2:
                    signals.append({
                        'symbol': symbol,
                        'strategy': 'short_selling_gap_momentum',
                        'signal_type': 'SELL',
                        'entry_price': entry_price,
                        'stop_loss': stop_loss,
                        'target_price': target_price,
                        'confidence': 0.70,
                        'risk_reward_ratio': reward / risk,
                        'date': current['date'],
                        'holding_period_days': 2,  # Quick gap play
                        'metadata': {
                            'gap_down_percent': current['gap_down'] * 100,
                            'volume_surge': current['volume_ratio'],
                            'bearish_follow_through': True
                        }
                    })
        
        return signals
    
    async def detect_day_trading_signals(self, df: pd.DataFrame, symbol: str) -> List[Dict[str, Any]]:
        """Detect day trading opportunities (intraday scalping)"""
        signals = []
        
        if len(df) < 30:
            return signals
        
        for i in range(30, len(df)):
            current = df.iloc[i]
            previous = df.iloc[i-1]
            
            # Day Trading Strategy 1: Gap Up Momentum
            if (current['gap_up'] > 0.015 and  # Gap up >1.5%
                current['volume_ratio'] > 2.0 and  # High volume
                current['opening_momentum'] > 0.005 and  # Positive opening momentum
                current['close'] > current['ema_9']):  # Above short EMA
                
                entry_price = current['close']
                stop_loss = current['open'] * 0.995  # Just below gap open
                target_price = current['close'] * 1.02  # 2% target
                
                risk = (entry_price - stop_loss) / entry_price
                reward = (target_price - entry_price) / entry_price
                
                if risk > 0 and reward > 0:
                    signals.append({
                        'symbol': symbol,
                        'strategy': 'day_trading_gap_momentum',
                        'signal_type': 'BUY',
                        'entry_price': entry_price,
                        'stop_loss': stop_loss,
                        'target_price': target_price,
                        'confidence': min(0.80, 0.5 + current['volume_ratio'] * 0.1),
                        'risk_reward_ratio': reward / risk if risk > 0 else 0,
                        'date': current['date'],
                        'holding_period_hours': 4,  # Intraday scalp
                        'metadata': {
                            'gap_up_percent': current['gap_up'] * 100,
                            'opening_momentum': current['opening_momentum'] * 100,
                            'volume_surge': current['volume_ratio']
                        }
                    })
            
            # Day Trading Strategy 2: Opening Range Breakout
            if (i >= 35 and
                current['high'] > df.iloc[i-5:i]['high'].max() and  # Breaking 5-day high
                current['volume_ratio'] > 1.5 and  # Above average volume
                current['rsi'] > 55 and current['rsi'] < 75 and  # Momentum but not overbought
                current['close'] > current['ema_21']):  # Above trend
                
                entry_price = current['close']
                recent_low = df.iloc[i-10:i]['low'].min()
                stop_loss = max(recent_low, current['close'] * 0.97)  # 3% or recent low
                target_price = current['close'] * 1.06  # 6% target (2:1 R/R)
                
                risk = (entry_price - stop_loss) / entry_price
                reward = (target_price - entry_price) / entry_price
                
                if risk > 0 and reward/risk >= 1.5:
                    signals.append({
                        'symbol': symbol,
                        'strategy': 'day_trading_breakout',
                        'signal_type': 'BUY',
                        'entry_price': entry_price,
                        'stop_loss': stop_loss,
                        'target_price': target_price,
                        'confidence': 0.75,
                        'risk_reward_ratio': reward / risk,
                        'date': current['date'],
                        'holding_period_hours': 6,  # Day trading hold
                        'metadata': {
                            'breakout_level': df.iloc[i-5:i]['high'].max(),
                            'volume_confirmation': current['volume_ratio'],
                            'rsi': current['rsi']
                        }
                    })
            
            # Day Trading Strategy 3: Mean Reversion Scalp
            if (current['close'] < current['bb_lower'] and  # Oversold
                current['rsi'] < 35 and  # RSI oversold
                current['hammer'] and  # Hammer reversal pattern
                current['volume_ratio'] > 1.2):  # Volume confirmation
                
                entry_price = current['close']
                stop_loss = current['close'] * 0.98  # 2% stop
                target_price = current['bb_middle']  # Target middle band
                
                risk = (entry_price - stop_loss) / entry_price
                reward = (target_price - entry_price) / entry_price
                
                if risk > 0 and reward > 0 and reward/risk >= 1.0:
                    signals.append({
                        'symbol': symbol,
                        'strategy': 'day_trading_mean_reversion',
                        'signal_type': 'BUY',
                        'entry_price': entry_price,
                        'stop_loss': stop_loss,
                        'target_price': target_price,
                        'confidence': 0.70,
                        'risk_reward_ratio': reward / risk,
                        'date': current['date'],
                        'holding_period_hours': 2,  # Quick scalp
                        'metadata': {
                            'oversold_rsi': current['rsi'],
                            'hammer_pattern': True,
                            'bb_position': 'below_lower'
                        }
                    })
        
        return signals
    
    async def analyze_symbol(self, symbol: str) -> Dict[str, Any]:
        """Comprehensive analysis for a single symbol"""
        try:
            logger.info(f"Analyzing {symbol}...")
            
            # Get 30-day daily data
            from_date = self.start_date.strftime("%Y-%m-%d")
            to_date = self.end_date.strftime("%Y-%m-%d")
            
            data = await self.data_fetcher.get_historical_data(
                symbol, 
                interval="1D", 
                from_date=from_date, 
                to_date=to_date
            )
            
            if not data or len(data) < 20:
                logger.warning(f"Insufficient data for {symbol}")
                return {
                    'symbol': symbol,
                    'status': 'insufficient_data',
                    'short_selling_signals': [],
                    'day_trading_signals': []
                }
            
            # Convert to DataFrame and add indicators
            df = pd.DataFrame(data)
            df['date'] = pd.to_datetime(df['date'])
            df = await self.calculate_enhanced_indicators(df)
            
            # Generate signals
            short_selling_signals = await self.detect_short_selling_signals(df, symbol)
            day_trading_signals = await self.detect_day_trading_signals(df, symbol)
            
            # Calculate performance metrics
            total_signals = len(short_selling_signals) + len(day_trading_signals)
            avg_confidence_short = np.mean([s['confidence'] for s in short_selling_signals]) if short_selling_signals else 0
            avg_confidence_day = np.mean([s['confidence'] for s in day_trading_signals]) if day_trading_signals else 0
            avg_rr_short = np.mean([s['risk_reward_ratio'] for s in short_selling_signals]) if short_selling_signals else 0
            avg_rr_day = np.mean([s['risk_reward_ratio'] for s in day_trading_signals]) if day_trading_signals else 0
            
            return {
                'symbol': symbol,
                'status': 'analyzed',
                'data_points': len(df),
                'analysis_period': f"{from_date} to {to_date}",
                'short_selling_signals': short_selling_signals,
                'day_trading_signals': day_trading_signals,
                'summary': {
                    'total_signals': total_signals,
                    'short_selling_count': len(short_selling_signals),
                    'day_trading_count': len(day_trading_signals),
                    'avg_confidence_short_selling': round(avg_confidence_short, 3),
                    'avg_confidence_day_trading': round(avg_confidence_day, 3),
                    'avg_risk_reward_short_selling': round(avg_rr_short, 2),
                    'avg_risk_reward_day_trading': round(avg_rr_day, 2)
                }
            }
            
        except Exception as e:
            logger.error(f"Error analyzing {symbol}: {e}")
            return {
                'symbol': symbol,
                'status': 'error',
                'error': str(e),
                'short_selling_signals': [],
                'day_trading_signals': []
            }
    
    async def run_comprehensive_backtest(self) -> Dict[str, Any]:
        """Run comprehensive 30-day backtest for all symbols"""
        logger.info(f"Starting comprehensive short selling & day trading backtest...")
        logger.info(f"Analysis period: {self.start_date.strftime('%Y-%m-%d')} to {self.end_date.strftime('%Y-%m-%d')}")
        logger.info(f"Analyzing {len(self.symbols)} symbols")
        
        results = {}
        all_short_signals = []
        all_day_signals = []
        
        for i, symbol in enumerate(self.symbols, 1):
            logger.info(f"Progress: {i}/{len(self.symbols)} - Analyzing {symbol}")
            
            analysis = await self.analyze_symbol(symbol)
            results[symbol] = analysis
            
            # Collect all signals for aggregate analysis
            all_short_signals.extend(analysis.get('short_selling_signals', []))
            all_day_signals.extend(analysis.get('day_trading_signals', []))
        
        # Generate comprehensive summary
        summary = self._generate_comprehensive_summary(results, all_short_signals, all_day_signals)
        
        # Prepare final results
        final_results = {
            'analysis_metadata': {
                'analysis_date': datetime.now().isoformat(),
                'analysis_period': f"{self.start_date.strftime('%Y-%m-%d')} to {self.end_date.strftime('%Y-%m-%d')}",
                'total_symbols_analyzed': len(self.symbols),
                'successful_analyses': len([r for r in results.values() if r['status'] == 'analyzed']),
                'analysis_type': 'short_selling_day_trading_backtest'
            },
            'aggregate_summary': summary,
            'symbol_results': results,
            'all_short_selling_signals': sorted(all_short_signals, key=lambda x: x['confidence'], reverse=True),
            'all_day_trading_signals': sorted(all_day_signals, key=lambda x: x['confidence'], reverse=True)
        }
        
        return final_results
    
    def _generate_comprehensive_summary(self, results: Dict, all_short_signals: List, all_day_signals: List) -> Dict[str, Any]:
        """Generate comprehensive analysis summary"""
        
        # Basic counts
        total_symbols = len([r for r in results.values() if r['status'] == 'analyzed'])
        symbols_with_short_signals = len([r for r in results.values() if r.get('short_selling_signals', [])])
        symbols_with_day_signals = len([r for r in results.values() if r.get('day_trading_signals', [])])
        
        # Signal statistics
        total_short_signals = len(all_short_signals)
        total_day_signals = len(all_day_signals)
        
        # Confidence analysis
        high_confidence_short = len([s for s in all_short_signals if s['confidence'] >= 0.75])
        high_confidence_day = len([s for s in all_day_signals if s['confidence'] >= 0.75])
        
        # Risk/Reward analysis
        avg_rr_short = np.mean([s['risk_reward_ratio'] for s in all_short_signals]) if all_short_signals else 0
        avg_rr_day = np.mean([s['risk_reward_ratio'] for s in all_day_signals]) if all_day_signals else 0
        
        # Strategy distribution
        short_strategies = {}
        day_strategies = {}
        
        for signal in all_short_signals:
            strategy = signal['strategy']
            short_strategies[strategy] = short_strategies.get(strategy, 0) + 1
        
        for signal in all_day_signals:
            strategy = signal['strategy']
            day_strategies[strategy] = day_strategies.get(strategy, 0) + 1
        
        # Top opportunities
        top_short_signals = sorted(all_short_signals, key=lambda x: x['confidence'], reverse=True)[:5]
        top_day_signals = sorted(all_day_signals, key=lambda x: x['confidence'], reverse=True)[:5]
        
        return {
            'overview': {
                'total_symbols_analyzed': total_symbols,
                'symbols_with_short_signals': symbols_with_short_signals,
                'symbols_with_day_signals': symbols_with_day_signals,
                'signal_generation_rate_short': round(symbols_with_short_signals / total_symbols * 100, 1) if total_symbols > 0 else 0,
                'signal_generation_rate_day': round(symbols_with_day_signals / total_symbols * 100, 1) if total_symbols > 0 else 0
            },
            'signal_counts': {
                'total_short_selling_signals': total_short_signals,
                'total_day_trading_signals': total_day_signals,
                'high_confidence_short_signals': high_confidence_short,
                'high_confidence_day_signals': high_confidence_day,
                'short_signal_quality_rate': round(high_confidence_short / total_short_signals * 100, 1) if total_short_signals > 0 else 0,
                'day_signal_quality_rate': round(high_confidence_day / total_day_signals * 100, 1) if total_day_signals > 0 else 0
            },
            'performance_metrics': {
                'avg_confidence_short_selling': round(np.mean([s['confidence'] for s in all_short_signals]), 3) if all_short_signals else 0,
                'avg_confidence_day_trading': round(np.mean([s['confidence'] for s in all_day_signals]), 3) if all_day_signals else 0,
                'avg_risk_reward_short_selling': round(avg_rr_short, 2),
                'avg_risk_reward_day_trading': round(avg_rr_day, 2),
                'median_confidence_short': round(np.median([s['confidence'] for s in all_short_signals]), 3) if all_short_signals else 0,
                'median_confidence_day': round(np.median([s['confidence'] for s in all_day_signals]), 3) if all_day_signals else 0
            },
            'strategy_distribution': {
                'short_selling_strategies': short_strategies,
                'day_trading_strategies': day_strategies
            },
            'top_opportunities': {
                'best_short_selling_signals': [
                    {
                        'symbol': s['symbol'],
                        'strategy': s['strategy'],
                        'confidence': s['confidence'],
                        'risk_reward_ratio': s['risk_reward_ratio'],
                        'entry_price': s['entry_price']
                    } for s in top_short_signals
                ],
                'best_day_trading_signals': [
                    {
                        'symbol': s['symbol'],
                        'strategy': s['strategy'],
                        'confidence': s['confidence'],
                        'risk_reward_ratio': s['risk_reward_ratio'],
                        'entry_price': s['entry_price']
                    } for s in top_day_signals
                ]
            }
        }

async def main():
    """Main execution function"""
    analyzer = ShortSellingDayTradingAnalyzer()
    
    try:
        # Run comprehensive backtest
        results = await analyzer.run_comprehensive_backtest()
        
        # Save results to file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"reports/short_selling_daytrading_backtest_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        logger.info(f"Analysis complete! Results saved to {filename}")
        
        # Print summary
        summary = results['aggregate_summary']
        print("\n" + "="*70)
        print("🎯 SHORT SELLING & DAY TRADING BACKTEST SUMMARY")
        print("="*70)
        
        print(f"\n📊 ANALYSIS OVERVIEW:")
        print(f"   • Analysis Period: {results['analysis_metadata']['analysis_period']}")
        print(f"   • Symbols Analyzed: {summary['overview']['total_symbols_analyzed']}")
        print(f"   • Short Signal Generation Rate: {summary['overview']['signal_generation_rate_short']}%")
        print(f"   • Day Trading Signal Rate: {summary['overview']['signal_generation_rate_day']}%")
        
        print(f"\n🎯 SIGNAL QUALITY METRICS:")
        print(f"   Short Selling Signals:")
        print(f"     ├─ Total Signals: {summary['signal_counts']['total_short_selling_signals']}")
        print(f"     ├─ High Quality (>75%): {summary['signal_counts']['high_confidence_short_signals']}")
        print(f"     ├─ Avg Confidence: {summary['performance_metrics']['avg_confidence_short_selling']}")
        print(f"     └─ Avg Risk/Reward: {summary['performance_metrics']['avg_risk_reward_short_selling']}:1")
        
        print(f"   Day Trading Signals:")
        print(f"     ├─ Total Signals: {summary['signal_counts']['total_day_trading_signals']}")
        print(f"     ├─ High Quality (>75%): {summary['signal_counts']['high_confidence_day_signals']}")
        print(f"     ├─ Avg Confidence: {summary['performance_metrics']['avg_confidence_day_trading']}")
        print(f"     └─ Avg Risk/Reward: {summary['performance_metrics']['avg_risk_reward_day_trading']}:1")
        
        print(f"\n🔥 TOP SHORT SELLING OPPORTUNITIES:")
        for i, signal in enumerate(summary['top_opportunities']['best_short_selling_signals'][:3], 1):
            print(f"   {i}. {signal['symbol']} - {signal['strategy']}")
            print(f"      Confidence: {signal['confidence']:.1%} | R/R: {signal['risk_reward_ratio']:.1f}:1")
        
        print(f"\n⚡ TOP DAY TRADING OPPORTUNITIES:")
        for i, signal in enumerate(summary['top_opportunities']['best_day_trading_signals'][:3], 1):
            print(f"   {i}. {signal['symbol']} - {signal['strategy']}")
            print(f"      Confidence: {signal['confidence']:.1%} | R/R: {signal['risk_reward_ratio']:.1f}:1")
        
        print(f"\n📁 Detailed results saved to: {filename}")
        print("="*70)
        
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())