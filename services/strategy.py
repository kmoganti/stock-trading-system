from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from .data_fetcher import DataFetcher
from .watchlist import WatchlistService
from models.signals import Signal, SignalType, SignalStatus
from config.settings import get_settings
from dataclasses import dataclass

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

@dataclass
class TradingSignal:
    """Lightweight signal class for strategy calculations"""
    symbol: str
    signal_type: SignalType
    entry_price: float
    stop_loss: float
    target_price: float
    confidence: float
    strategy: str
    metadata: Optional[Dict] = None

class StrategyService:
    """Core trading strategy service with multiple algorithms"""
    
    def __init__(self, data_fetcher: DataFetcher, db: Optional[AsyncSession] = None):
        self.data_fetcher = data_fetcher
        self.db = db
        self.settings = get_settings()
        self.watchlist_service = WatchlistService(db) if db is not None else None
        self._watchlist_by_category: Dict[Optional[str], List[str]] = {}
        from services.telegram_notifier import TelegramNotifier
        self._notifier = TelegramNotifier()
        self._strategy_map = {
            "ema_crossover": self._ema_crossover_strategy,
            "bollinger_bands": self._bollinger_bands_strategy,
            "momentum": self._momentum_strategy,
        }
    
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
            df['volume_sma'] = ta.trend.SMAIndicator(df['volume'], window=20).sma_indicator()
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
                return TradingSignal(
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
                return TradingSignal(
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
            is_bullish_crossover = previous['ema_9'] <= previous['ema_21'] and current['ema_9'] > current['ema_21']
            is_uptrend = current['close'] > current['ema_50']
            has_volume = current['volume_ratio'] > 0.9  # Relaxed volume confirmation
            
            if is_bullish_crossover and is_uptrend and has_volume and current['rsi'] < 70:
                # Volatility-adjusted stop-loss and take-profit using ATR
                stop_loss = current['close'] - (1.5 * current['atr'])
                take_profit = current['close'] + (3.0 * current['atr'])  # 2:1 Risk/Reward
                
                return TradingSignal(
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
                        "rsi": current['rsi'],
                        "atr": current['atr']
                    }
                )
            
            # Check for bearish crossover (9 EMA crosses below 21 EMA)
            is_bearish_crossover = previous['ema_9'] >= previous['ema_21'] and current['ema_9'] < current['ema_21']
            is_downtrend = current['close'] < current['ema_50'] # Trend filter
            
            if is_bearish_crossover and is_downtrend and has_volume and current['rsi'] > 30:
                # Volatility-adjusted stop-loss and take-profit using ATR
                stop_loss = current['close'] + (1.5 * current['atr'])
                take_profit = current['close'] - (3.0 * current['atr'])
                
                return TradingSignal(
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
                        "rsi": current['rsi'],
                        "atr": current['atr']
                    }
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Error in EMA crossover strategy for {symbol}: {str(e)}")
            return None
    
    def _bollinger_bands_strategy(self, df, symbol: str) -> Optional[TradingSignal]:
        """Bollinger Bands mean reversion strategy"""
        try:
            if len(df) < 2:
                return None
            
            current = df.iloc[-1]
            
            # Buy when price touches lower band and RSI is oversold
            if (current['close'] <= current['bb_lower'] and 
                current['rsi'] < 30 and 
                current['volume_ratio'] > 1.1):  # Relaxed high volume confirmation
                
                return TradingSignal(
                    symbol=symbol,
                    signal_type=SignalType.BUY,
                    entry_price=current['close'],
                    stop_loss=current['close'] - (2 * current['atr']), # Wider stop for mean reversion
                    target_price=current['bb_middle'],
                    confidence=0.75,
                    strategy="bollinger_bands",
                    metadata={
                        "bb_position": "lower_band",
                        "rsi": current['rsi'],
                        "volume_ratio": current['volume_ratio'],
                        "atr": current['atr']
                    }
                )
            
            # Sell when price touches upper band and RSI is overbought
            elif (current['close'] >= current['bb_upper'] and 
                  current['rsi'] > 70 and 
                  current['volume_ratio'] > 1.1):
                
                return TradingSignal(
                    symbol=symbol,
                    signal_type=SignalType.SELL,
                    entry_price=current['close'],
                    stop_loss=current['close'] + (2 * current['atr']),
                    target_price=current['bb_middle'],
                    confidence=0.75,
                    strategy="bollinger_bands",
                    metadata={
                        "bb_position": "upper_band",
                        "rsi": current['rsi'],
                        "volume_ratio": current['volume_ratio'],
                        "atr": current['atr']
                    }
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Error in Bollinger Bands strategy for {symbol}: {str(e)}")
            return None
    
    def _momentum_strategy(self, df, symbol: str) -> Optional[TradingSignal]:
        """Momentum strategy based on MACD and price momentum"""
        try:
            if len(df) < 3:
                return None
            
            current = df.iloc[-1]
            previous = df.iloc[-2]
            
            has_volume = current['volume_ratio'] > 0.95 # Relaxed volume confirmation
            
            # Bullish momentum: MACD crosses above signal line with strong momentum
            if (previous['macd'] <= previous['macd_signal'] and
                current['macd'] > current['macd_signal'] and
                current['price_momentum'] > 0.015 and  # Relaxed to 1.5% momentum
                has_volume and current['rsi'] > 40 and current['rsi'] < 70):
                
                return TradingSignal(
                    symbol=symbol,
                    signal_type=SignalType.BUY,
                    entry_price=current['close'],
                    stop_loss=current['close'] - (1.5 * current['atr']),
                    target_price=current['close'] + (3.0 * current['atr']),
                    confidence=0.8,
                    strategy="momentum",
                    metadata={
                        "macd": current['macd'],
                        "macd_signal": current['macd_signal'],
                        "price_momentum": current['price_momentum'],
                        "rsi": current['rsi'],
                        "atr": current['atr']
                    }
                )
            
            # Bearish momentum: MACD crosses below signal line with negative momentum
            elif (previous['macd'] >= previous['macd_signal'] and
                  current['macd'] < current['macd_signal'] and
                  current['price_momentum'] < -0.015 and  # Relaxed to -1.5% momentum
                  has_volume and current['rsi'] > 30 and current['rsi'] < 60):
                
                return TradingSignal(
                    symbol=symbol,
                    signal_type=SignalType.SELL,
                    entry_price=current['close'],
                    stop_loss=current['close'] + (1.5 * current['atr']),
                    target_price=current['close'] - (3.0 * current['atr']),
                    confidence=0.8,
                    strategy="momentum",
                    metadata={
                        "macd": current['macd'],
                        "macd_signal": current['macd_signal'],
                        "price_momentum": current['price_momentum'],
                        "rsi": current['rsi'],
                        "atr": current['atr']
                    }
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Error in momentum strategy for {symbol}: {str(e)}")
            return None
    
    async def _validate_signal(self, signal: TradingSignal, historical_data: List[Dict]) -> bool:
        """Validate signal against basic criteria"""
        try:
            # Basic validation checks
            if not signal or not signal.symbol:
                return False
            
            # Check if price is reasonable
            if signal.entry_price <= 0:
                return False
            
            # Check stop loss and target are reasonable
            if signal.signal_type == SignalType.BUY:
                if signal.stop_loss >= signal.entry_price:
                    return False
                if signal.target_price <= signal.entry_price:
                    return False
            elif signal.signal_type == SignalType.SELL:
                if signal.stop_loss <= signal.entry_price:
                    return False
                if signal.target_price >= signal.entry_price:
                    return False
            
            # Check confidence level
            if signal.confidence < 0.5:
                return False
            
            # Get current market data for additional validation
            current_price = await self.data_fetcher.get_live_price(signal.symbol)
            if current_price and abs(current_price - signal.entry_price) / signal.entry_price > 0.05:
                # Price has moved more than 5% since signal generation
                logger.warning(f"Signal for {signal.symbol} may be stale - price moved from {signal.entry_price} to {current_price}")
                return False
            
            # Check liquidity (soft-fail if unavailable)
            liquidity_info = await self.data_fetcher.get_liquidity_info(signal.symbol)
            if liquidity_info and liquidity_info.get('liquidity_score', 0) < 20:  # Low liquidity threshold
                logger.warning(f"Low liquidity for {signal.symbol}: {liquidity_info.get('liquidity_score', 0)}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating signal for {signal.symbol}: {str(e)}")
            return False
    
    async def get_watchlist(self, category: Optional[str] = None) -> List[str]:
        """Get the current watchlist, optionally by category"""
        if category not in self._watchlist_by_category:
            if self.watchlist_service is not None:
                self._watchlist_by_category[category] = await self.watchlist_service.get_watchlist(category=category)
            else:
                self._watchlist_by_category[category] = []
        return self._watchlist_by_category[category]

    async def update_watchlist(
        self, symbols: List[str], category: Optional[str] = None
    ) -> None:
        """Update the watchlist with new symbols"""
        if self.watchlist_service is not None:
            await self.watchlist_service.add_symbols(symbols, category=category)
            self._watchlist_by_category[category] = await self.watchlist_service.get_watchlist(category=category)

    async def remove_from_watchlist(self, symbols: List[str], category: Optional[str] = None) -> None:
        """Remove symbols from the watchlist"""
        if self.watchlist_service is not None:
            await self.watchlist_service.remove_symbols(symbols, category=category)
            if category in self._watchlist_by_category:
                self._watchlist_by_category[category] = [s for s in self._watchlist_by_category[category] if s not in [sym.upper() for sym in symbols]]

    async def generate_signals(
        self, symbol: str, category: str = "short_term", strategy_name: Optional[str] = None
    ) -> List[TradingSignal]:
        """Generate trading signals for a symbol"""
        try:
            # Notify when screening starts for the first symbol per category in this session
            if getattr(self.settings, "telegram_notifications_enabled", True):
                key = f"_notified_{category}"
                if not hasattr(self, key):
                    try:
                        await self._notifier.send(f"▶️ Starting {category.replace('_', ' ')} screening...")
                    except Exception:
                        pass
                    setattr(self, key, True)
            # Determine data fetching parameters based on trading category
            interval = "1D"
            days_to_fetch = 100
            
            if category == "day_trading":
                interval = "5m"  # 5-minute interval for intraday
                days_to_fetch = 2  # Fetch last 2 days of 5-min data for context
            elif category == "long_term":
                interval = "1D"
                days_to_fetch = 250 # ~1 year of data for long term trends
            else: # short_term
                interval = "1D"
                days_to_fetch = 100 # Default for swing trading

            # Get historical data
            # By passing explicit dates, we ensure the cache key in data_fetcher is consistent
            to_date = datetime.now()
            from_date = to_date - timedelta(days=days_to_fetch)
            
            data = await self.data_fetcher.get_historical_data(
                symbol, interval=interval, from_date=from_date.strftime("%Y-%m-%d"), to_date=to_date.strftime("%Y-%m-%d")
            )
            
            if not data:
                logger.warning(f"No historical data for {symbol} (interval: {interval}), trying live data fallback")
                return await self._generate_signals_from_live_data(symbol)
            
            # Calculate indicators
            if HAS_PANDAS:
                df = pd.DataFrame(data)
                indicators = self.calculate_indicators(df)
            else:
                indicators = self._calculate_basic_indicators(data)
            
            signals = []
            
            if HAS_PANDAS and self._strategy_map:
                strategies_to_run = (
                    {strategy_name: self._strategy_map[strategy_name]}
                    if strategy_name and strategy_name in self._strategy_map
                    else self._strategy_map
                )
                for name, func in strategies_to_run.items():
                    # Full-featured strategies expect a dataframe
                    signal = func(indicators, symbol)
                    if signal:
                        signals.append(signal)
            elif not HAS_PANDAS:
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

    async def generate_signals_from_data(
        self,
        symbol: str,
        data: List[Dict],
        strategy_name: Optional[str] = None,
        validate: bool = True,
    ) -> List[TradingSignal]:
        """Generate signals using pre-fetched historical data (skips any data calls).

        - Expects already normalized list of dicts with at least close/high/low/open/volume/date.
        - Allows disabling validation to avoid extra live/depth calls when optimizing batch runs.
        """
        try:
            if not data:
                return []

            if HAS_PANDAS:
                df = pd.DataFrame(data)
                indicators = self.calculate_indicators(df)
            else:
                indicators = self._calculate_basic_indicators(data)

            signals: List[TradingSignal] = []
            if HAS_PANDAS and self._strategy_map:
                strategies_to_run = (
                    {strategy_name: self._strategy_map[strategy_name]}
                    if strategy_name and strategy_name in self._strategy_map
                    else self._strategy_map
                )
                for name, func in strategies_to_run.items():
                    signal = func(indicators, symbol)
                    if signal:
                        signals.append(signal)
            elif not HAS_PANDAS:
                basic_signal = self._basic_trend_strategy(indicators, symbol)
                if basic_signal:
                    signals.append(basic_signal)

            if not validate:
                return signals

            filtered: List[TradingSignal] = []
            for sig in signals:
                if await self._validate_signal(sig, data):
                    filtered.append(sig)
            return filtered
        except Exception as e:
            logger.error(f"Error generating signals from pre-fetched data for {symbol}: {e}")
            return []
    
    async def calculate_position_size(self, signal: 'TradingSignal', available_capital: float) -> int:
        """Calculate position size based on risk management"""
        try:
            symbol = signal.symbol
            entry_price = signal.entry_price
            stop_loss = signal.stop_loss
            
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
                symbol, position_size, signal.signal_type.value, entry_price
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
    
    async def _generate_signals_from_live_data(self, symbol: str) -> List[TradingSignal]:
        """Generate signals using live price data when historical data is unavailable"""
        try:
            # Get current live price
            current_price = await self.data_fetcher.get_live_price(symbol)
            
            if not current_price:
                logger.warning(f"No live price available for {symbol}")
                return await self._generate_mock_signals(symbol)
            
            # Get market depth for additional context
            depth = await self.data_fetcher.get_market_depth(symbol)
            liquidity_info = await self.data_fetcher.get_liquidity_info(symbol)
            
            signals = []
            
            # Simple momentum signal based on bid-ask spread and liquidity
            if depth and liquidity_info:
                spread_percent = liquidity_info.get('bid_ask_spread', 0)
                liquidity_score = liquidity_info.get('liquidity_score', 0)
                
                # Generate buy signal for liquid stocks with tight spreads
                if spread_percent < 0.5 and liquidity_score > 50:
                    signal = TradingSignal(
                        symbol=symbol,
                        signal_type=SignalType.BUY,
                        entry_price=current_price,
                        stop_loss=current_price * 0.97,  # 3% stop loss
                        target_price=current_price * 1.05,  # 5% target
                        confidence=0.65,
                        strategy="live_data_momentum",
                        metadata={
                            "spread_percent": spread_percent,
                            "liquidity_score": liquidity_score,
                            "current_price": current_price
                        }
                    )
                    
                    # Validate the signal
                    if await self._validate_signal(signal, []):
                        signals.append(signal)
            
            return signals
            
        except Exception as e:
            logger.error(f"Error generating signals from live data for {symbol}: {str(e)}")
            return await self._generate_mock_signals(symbol)
    
    async def _generate_mock_signals(self, symbol: str) -> List[TradingSignal]:
        """Generate mock signals for testing when no real data is available"""
        try:
            import random
            
            # Generate a mock current price based on symbol
            base_prices = {
                "RELIANCE": 2800,
                "TCS": 3500,
                "INFY": 1800,
                "HDFCBANK": 1600,
                "ICICIBANK": 1200,
                "SBIN": 800,
                "ITC": 450,
                "LT": 3200,
                "HINDUNILVR": 2600,
                "BAJFINANCE": 7000
            }
            
            base_price = base_prices.get(symbol, 1000)
            # Add some random variation (±5%)
            current_price = base_price * (1 + random.uniform(-0.05, 0.05))
            
            signals = []
            
            # Randomly generate a signal (30% chance)
            if random.random() < 0.3:
                signal_type = random.choice([SignalType.BUY, SignalType.SELL])
                
                if signal_type == SignalType.BUY:
                    signal = TradingSignal(
                        symbol=symbol,
                        signal_type=SignalType.BUY,
                        entry_price=current_price,
                        stop_loss=current_price * 0.95,  # 5% stop loss
                        target_price=current_price * 1.08,  # 8% target
                        confidence=0.7,
                        strategy="mock_signal",
                        metadata={
                            "mock_data": True,
                            "base_price": base_price,
                            "variation": (current_price - base_price) / base_price
                        }
                    )
                else:
                    signal = TradingSignal(
                        symbol=symbol,
                        signal_type=SignalType.SELL,
                        entry_price=current_price,
                        stop_loss=current_price * 1.05,  # 5% stop loss
                        target_price=current_price * 0.92,  # 8% target
                        confidence=0.7,
                        strategy="mock_signal",
                        metadata={
                            "mock_data": True,
                            "base_price": base_price,
                            "variation": (current_price - base_price) / base_price
                        }
                    )
                
                signals.append(signal)
                logger.info(f"Generated mock {signal_type.value} signal for {symbol} at Rs.{current_price:.2f}")
            
            return signals
            
        except Exception as e:
            logger.error(f"Error generating mock signals for {symbol}: {str(e)}")
            return []
