from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
import logging
from .data_fetcher import DataFetcher
from models.signals import Signal, SignalType, SignalStatus
from config.settings import get_settings

# Optional imports for advanced features
try:
    import pandas as pd
    import numpy as np
    import ta
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False
    # Create dummy classes for basic functionality
    class pd:
        class DataFrame:
            def __init__(self, data=None):
                self.data = data or []
                self.empty = len(self.data) == 0
                self.columns = []
            def __len__(self):
                return len(self.data)
    
    class np:
        @staticmethod
        def mean(data):
            return sum(data) / len(data) if data else 0
        
        @staticmethod
        def std(data):
            if not data:
                return 0
            mean_val = np.mean(data)
            return (sum((x - mean_val) ** 2 for x in data) / len(data)) ** 0.5

logger = logging.getLogger(__name__)

class StrategyService:
    """Core trading strategy service with multiple algorithms"""
    
    def __init__(self, data_fetcher: DataFetcher):
        self.data_fetcher = data_fetcher
        self.settings = get_settings()
        self.watchlist = ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK", "SBIN", "ITC", "LT", "HINDUNILVR", "BAJFINANCE"]
    
    def calculate_indicators(self, df) -> Dict:
        """Calculate technical indicators for the dataframe"""
        try:
            if not HAS_PANDAS:
                logger.warning("Pandas not available, using basic indicators")
                return self._calculate_basic_indicators(df)
            
            if df.empty or len(df) < 50:
                return df
            
            # Ensure we have the required columns
            required_cols = ['open', 'high', 'low', 'close', 'volume']
            if not all(col in df.columns for col in required_cols):
                logger.error("Missing required OHLCV columns")
                return df
            
            # Moving Averages
            df['ema_9'] = ta.trend.EMAIndicator(df['close'], window=9).ema_indicator()
            df['ema_21'] = ta.trend.EMAIndicator(df['close'], window=21).ema_indicator()
            df['ema_50'] = ta.trend.EMAIndicator(df['close'], window=50).ema_indicator()
            df['sma_20'] = ta.trend.SMAIndicator(df['close'], window=20).sma_indicator()
            
            # Bollinger Bands
            bb = ta.volatility.BollingerBands(df['close'], window=20, window_dev=2)
            df['bb_upper'] = bb.bollinger_hband()
            df['bb_middle'] = bb.bollinger_mavg()
            df['bb_lower'] = bb.bollinger_lband()
            df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']
            
            # RSI
            df['rsi'] = ta.momentum.RSIIndicator(df['close'], window=14).rsi()
            
            # MACD
            macd = ta.trend.MACD(df['close'])
            df['macd'] = macd.macd()
            df['macd_signal'] = macd.macd_signal()
            df['macd_histogram'] = macd.macd_diff()
            
            # ATR for volatility
            df['atr'] = ta.volatility.AverageTrueRange(df['high'], df['low'], df['close'], window=14).average_true_range()
            
            # Volume indicators
            df['volume_sma'] = ta.volume.VolumeSMAIndicator(df['close'], df['volume'], window=20).volume_sma()
            df['volume_ratio'] = df['volume'] / df['volume_sma']
            
            # Support and Resistance levels
            df['support'] = df['low'].rolling(window=20).min()
            df['resistance'] = df['high'].rolling(window=20).max()
            
            # Price momentum
            df['price_change'] = df['close'].pct_change()
            df['price_momentum'] = df['close'].pct_change(periods=5)
            
            return df
            
        except Exception as e:
            logger.error(f"Error calculating indicators: {str(e)}")
            return df
    
    def _calculate_basic_indicators(self, data: List[Dict]) -> Dict:
        """Calculate basic indicators without pandas/ta"""
        if not data or len(data) < 20:
            return {}
        
        try:
            # Extract close prices
            closes = [float(item.get('close', 0)) for item in data]
            
            # Simple moving average
            sma_20 = np.mean(closes[-20:]) if len(closes) >= 20 else np.mean(closes)
            
            # Basic trend detection
            recent_avg = np.mean(closes[-5:]) if len(closes) >= 5 else closes[-1]
            older_avg = np.mean(closes[-10:-5]) if len(closes) >= 10 else closes[0]
            
            trend = "up" if recent_avg > older_avg else "down"
            
            return {
                "sma_20": sma_20,
                "current_price": closes[-1],
                "trend": trend,
                "price_change": closes[-1] - closes[-2] if len(closes) >= 2 else 0
            }
            
        except Exception as e:
            logger.error(f"Error in basic indicators: {str(e)}")
            return {}
    
    def _basic_trend_strategy(self, indicators: Dict, symbol: str) -> Optional[Signal]:
        """Basic trend following strategy without pandas"""
        try:
            if not indicators:
                return None
            
            current_price = indicators.get('current_price', 0)
            sma_20 = indicators.get('sma_20', 0)
            trend = indicators.get('trend', 'neutral')
            price_change = indicators.get('price_change', 0)
            
            # Simple buy signal: price above SMA and uptrend
            if current_price > sma_20 and trend == 'up' and price_change > 0:
                return Signal(
                    symbol=symbol,
                    signal_type=SignalType.BUY,
                    entry_price=current_price,
                    stop_loss=current_price * 0.95,  # 5% stop loss
                    target_price=current_price * 1.10,  # 10% target
                    confidence=0.6,
                    strategy="basic_trend",
                    metadata={
                        "sma_20": sma_20,
                        "trend": trend,
                        "price_change": price_change
                    }
                )
            
            # Simple sell signal: price below SMA and downtrend
            elif current_price < sma_20 and trend == 'down' and price_change < 0:
                return Signal(
                    symbol=symbol,
                    signal_type=SignalType.SELL,
                    entry_price=current_price,
                    stop_loss=current_price * 1.05,  # 5% stop loss
                    target_price=current_price * 0.90,  # 10% target
                    confidence=0.6,
                    strategy="basic_trend",
                    metadata={
                        "sma_20": sma_20,
                        "trend": trend,
                        "price_change": price_change
                    }
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Error in basic trend strategy: {str(e)}")
            return None
    
    def _ema_crossover_strategy(self, df, symbol: str) -> Optional[Signal]:
        """EMA crossover strategy (9 EMA crosses 21 EMA)"""
        try:
            if len(df) < 2:
                return None
            
            current = df.iloc[-1]
            previous = df.iloc[-2]
            
            # Check for bullish crossover (9 EMA crosses above 21 EMA)
            if (previous['ema_9'] <= previous['ema_21'] and 
                current['ema_9'] > current['ema_21'] and
                current['rsi'] < 70):  # Not overbought
                
                stop_loss = current['close'] * 0.98  # 2% stop loss
                take_profit = current['close'] * 1.06  # 6% take profit
                
                return Signal(
                    symbol=symbol,
                    signal_type=SignalType.BUY,
                    entry_price=current['close'],
                    stop_loss=stop_loss,
                    target_price=take_profit,
                    confidence=0.7,
                    strategy="ema_crossover",
                    metadata={
                        "ema_9": current['ema_9'],
                        "ema_21": current['ema_21'],
                        "rsi": current['rsi']
                    }
                )
            
            # Check for bearish crossover (9 EMA crosses below 21 EMA)
            elif (previous['ema_9'] >= previous['ema_21'] and 
                  current['ema_9'] < current['ema_21'] and
                  current['rsi'] > 30):  # Not oversold
                
                stop_loss = current['close'] * 1.02  # 2% stop loss for short
                take_profit = current['close'] * 0.94  # 6% take profit for short
                
                return Signal(
                    symbol=symbol,
                    signal_type=SignalType.SELL,
                    entry_price=current['close'],
                    stop_loss=stop_loss,
                    target_price=take_profit,
                    confidence=0.7,
                    strategy="ema_crossover",
                    metadata={
                        "ema_9": current['ema_9'],
                        "ema_21": current['ema_21'],
                        "rsi": current['rsi']
                    }
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Error in EMA crossover strategy for {symbol}: {str(e)}")
            return None
    
    async def generate_signals(self, symbol: str) -> List[Signal]:
        """Generate trading signals for a symbol"""
        try:
            # Get historical data
            data = await self.data_fetcher.get_historical_data(symbol, days=100)
            
            if not data:
                logger.warning(f"No data available for {symbol}")
                return []
            
            # Calculate indicators
            if HAS_PANDAS:
                df = pd.DataFrame(data)
                indicators = self.calculate_indicators(df)
            else:
                indicators = self._calculate_basic_indicators(data)
            
            signals = []
            
            if HAS_PANDAS:
                # Advanced strategies with pandas
                ema_signal = self._ema_crossover_strategy(indicators, symbol)
                if ema_signal:
                    signals.append(ema_signal)
                
                bb_signal = self._bollinger_bands_strategy(indicators, symbol)
                if bb_signal:
                    signals.append(bb_signal)
                
                momentum_signal = self._momentum_strategy(indicators, symbol)
                if momentum_signal:
                    signals.append(momentum_signal)
            else:
                # Basic strategy without pandas
                basic_signal = self._basic_trend_strategy(indicators, symbol)
                if basic_signal:
                    signals.append(basic_signal)
            
            # Filter signals
            filtered_signals = []
            for signal in signals:
                if await self._validate_signal(signal, data):
                    filtered_signals.append(signal)
            
            return filtered_signals
            
        except Exception as e:
            logger.error(f"Error generating signals for {symbol}: {str(e)}")
            return []
    
    async def calculate_position_size(self, signal: Signal, available_capital: float) -> int:
        """Calculate position size based on risk management"""
        try:
            symbol = signal.symbol
            entry_price = signal.entry_price
            stop_loss = signal.stop_loss
            symbol = signal['symbol']
            entry_price = signal['entry_price']
            stop_loss = signal['stop_loss']
            
            # Calculate risk per share
            risk_per_share = abs(entry_price - stop_loss)
            
            # Calculate position size based on risk per trade
            risk_amount = available_capital * self.settings.risk_per_trade
            position_size = int(risk_amount / risk_per_share)
            
            # Ensure minimum position size
            if position_size < 1:
                position_size = 1
            
            # Calculate required margin
            margin_required = await self.data_fetcher.calculate_required_margin(
                symbol, position_size, signal['signal_type'].value, entry_price
            )
            
            if margin_required and margin_required > available_capital:
                # Reduce position size to fit available capital
                position_size = int(available_capital / (margin_required / position_size))
                position_size = max(1, position_size)
            
            return position_size
            
        except Exception as e:
            logger.error(f"Error calculating position size: {str(e)}")
            return 1
    
    def get_exit_signals(self, positions: List[Dict]) -> List[Dict]:
        """Generate exit signals for existing positions"""
        exit_signals = []
        
        for position in positions:
            try:
                symbol = position.get('symbol')
                if not symbol:
                    continue
                
                # Simple exit conditions (can be enhanced)
                pnl_percent = position.get('pnl_percent', 0)
                
                # Take profit at 5% gain
                if pnl_percent >= 5.0:
                    exit_signals.append({
                        'symbol': symbol,
                        'signal_type': SignalType.EXIT,
                        'reason': f'Take Profit - PnL: {pnl_percent:.2f}%',
                        'confidence': 0.9,
                        'position_id': position.get('id')
                    })
                
                # Stop loss at 3% loss
                elif pnl_percent <= -3.0:
                    exit_signals.append({
                        'symbol': symbol,
                        'signal_type': SignalType.EXIT,
                        'reason': f'Stop Loss - PnL: {pnl_percent:.2f}%',
                        'confidence': 1.0,
                        'position_id': position.get('id')
                    })
                
            except Exception as e:
                logger.error(f"Error generating exit signal: {str(e)}")
                continue
        
        return exit_signals
