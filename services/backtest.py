from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta, date
import logging
from .strategy import StrategyService
from .data_fetcher import DataFetcher

# Optional pandas import
try:
    import pandas as pd
    import numpy as np
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False
    # Basic replacements
    class pd:
        @staticmethod
        def DataFrame(data):
            return data
    class np:
        @staticmethod
        def mean(data):
            return sum(data) / len(data) if data else 0
from .strategy import StrategyService
import asyncio

logger = logging.getLogger(__name__)

class BacktestService:
    """Backtesting service for strategy validation"""
    
    def __init__(self, data_fetcher: DataFetcher):
        self.data_fetcher = data_fetcher
        self.strategy_service = StrategyService(data_fetcher)
    
    async def run_backtest(self, strategy_name: str, symbol: str, start_date: str, 
                          end_date: str, initial_capital: float = 100000.0) -> Dict[str, Any]:
        """Run backtest for a specific strategy"""
        try:
            # Get historical data
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            days = (end_dt - start_dt).days + 50  # Add buffer for indicators
            
            df = await self.data_fetcher.get_historical_data_df(symbol, "1D", start_date, end_date)
            
            if df is None or df.empty:
                return {"error": f"No data available for {symbol}"}
            
            # Filter data to backtest period (ensure index is datetime)
            df = df[(df.index >= start_dt) & (df.index <= end_dt)]
            
            if len(df) < 50:
                return {"error": "Insufficient data for backtesting"}
            
            # Calculate indicators
            df = self.strategy_service.calculate_indicators(df)
            
            # Run backtest simulation
            results = await self._simulate_trading(df, symbol, strategy_name, initial_capital)
            
            # Calculate performance metrics
            metrics = self._calculate_metrics(results, initial_capital)
            
            return {
                "strategy": strategy_name,
                "symbol": symbol,
                "start_date": start_date,
                "end_date": end_date,
                "initial_capital": initial_capital,
                "results": results,
                "metrics": metrics,
                "status": "completed"
            }
            
        except Exception as e:
            logger.error(f"Error running backtest: {str(e)}")
            return {"error": str(e), "status": "failed"}
    
    async def _simulate_trading(self, df: pd.DataFrame, symbol: str, 
                               strategy_name: str, initial_capital: float) -> Dict[str, Any]:
        """Simulate trading based on strategy signals"""
        
        portfolio = {
            "cash": initial_capital,
            "position": 0,
            "equity": initial_capital,
            "trades": [],
            "equity_curve": []
        }
        
        in_position = False
        entry_price = 0
        entry_date = None
        
        for i in range(50, len(df)):  # Start after indicator warmup
            current_row = df.iloc[i]
            current_date = df.index[i]
            current_price = current_row['close']
            
            # Update equity
            portfolio["equity"] = portfolio["cash"] + (portfolio["position"] * current_price)
            portfolio["equity_curve"].append({
                "date": current_date.isoformat(),
                "equity": portfolio["equity"]
            })
            
            # Generate signals based on strategy
            signal = None
            
            if strategy_name == "ema_crossover":
                signal = self._ema_crossover_signal(df.iloc[:i+1])
            elif strategy_name == "bollinger_bands":
                signal = self._bollinger_bands_signal(df.iloc[:i+1])
            elif strategy_name == "momentum":
                signal = self._momentum_signal(df.iloc[:i+1])
            
            # Execute trades based on signals
            if signal and not in_position and signal["signal_type"] == "buy":
                # Enter long position
                position_size = int(portfolio["cash"] * 0.95 / current_price)  # Use 95% of cash
                if position_size > 0:
                    portfolio["position"] = position_size
                    portfolio["cash"] -= position_size * current_price
                    entry_price = current_price
                    entry_date = current_date
                    in_position = True
                    
                    portfolio["trades"].append({
                        "type": "BUY",
                        "date": current_date.isoformat(),
                        "price": current_price,
                        "quantity": position_size,
                        "value": position_size * current_price
                    })
            
            elif in_position:
                # Check exit conditions
                should_exit = False
                exit_reason = ""
                
                # Stop loss (3% loss)
                if current_price <= entry_price * 0.97:
                    should_exit = True
                    exit_reason = "Stop Loss"
                
                # Take profit (6% gain)
                elif current_price >= entry_price * 1.06:
                    should_exit = True
                    exit_reason = "Take Profit"
                
                # Exit signal from strategy
                elif signal and signal["signal_type"] == "sell":
                    should_exit = True
                    exit_reason = "Strategy Exit"
                
                # Time-based exit (hold for max 10 days)
                elif (current_date - entry_date).days >= 10:
                    should_exit = True
                    exit_reason = "Time Exit"
                
                if should_exit:
                    # Exit position
                    exit_value = portfolio["position"] * current_price
                    portfolio["cash"] += exit_value
                    
                    trade_pnl = exit_value - (portfolio["position"] * entry_price)
                    
                    portfolio["trades"].append({
                        "type": "SELL",
                        "date": current_date.isoformat(),
                        "price": current_price,
                        "quantity": portfolio["position"],
                        "value": exit_value,
                        "pnl": trade_pnl,
                        "reason": exit_reason
                    })
                    
                    portfolio["position"] = 0
                    in_position = False
        
        # Close any remaining position at the end
        if in_position:
            final_price = df.iloc[-1]['close']
            exit_value = portfolio["position"] * final_price
            portfolio["cash"] += exit_value
            
            trade_pnl = exit_value - (portfolio["position"] * entry_price)
            
            portfolio["trades"].append({
                "type": "SELL",
                "date": df.index[-1].isoformat(),
                "price": final_price,
                "quantity": portfolio["position"],
                "value": exit_value,
                "pnl": trade_pnl,
                "reason": "End of Period"
            })
            
            portfolio["position"] = 0
        
        # Final equity calculation
        portfolio["equity"] = portfolio["cash"]
        
        return portfolio
    
    def _ema_crossover_signal(self, df: pd.DataFrame) -> Optional[Dict]:
        """Generate EMA crossover signals"""
        if len(df) < 2:
            return None
        
        current = df.iloc[-1]
        previous = df.iloc[-2]
        
        # Bullish crossover
        if (previous['ema_9'] <= previous['ema_21'] and 
            current['ema_9'] > current['ema_21'] and
            current['rsi'] < 70):
            return {"signal_type": "buy"}
        
        # Bearish crossover
        elif (previous['ema_9'] >= previous['ema_21'] and 
              current['ema_9'] < current['ema_21'] and
              current['rsi'] > 30):
            return {"signal_type": "sell"}
        
        return None
    
    def _bollinger_bands_signal(self, df: pd.DataFrame) -> Optional[Dict]:
        """Generate Bollinger Bands signals"""
        if len(df) < 2:
            return None
        
        current = df.iloc[-1]
        previous = df.iloc[-2]
        
        # Buy at lower band
        if (previous['close'] <= previous['bb_lower'] and 
            current['close'] > current['bb_lower'] and
            current['rsi'] < 40):
            return {"signal_type": "buy"}
        
        # Sell at upper band
        elif (previous['close'] >= previous['bb_upper'] and 
              current['close'] < current['bb_upper'] and
              current['rsi'] > 60):
            return {"signal_type": "sell"}
        
        return None
    
    def _momentum_signal(self, df: pd.DataFrame) -> Optional[Dict]:
        """Generate momentum signals"""
        if len(df) < 2:
            return None
        
        current = df.iloc[-1]
        previous = df.iloc[-2]
        
        # Bullish momentum
        if (current['macd'] > current['macd_signal'] and
            previous['macd'] <= previous['macd_signal'] and
            current['rsi'] > 50 and current['rsi'] < 70):
            return {"signal_type": "buy"}
        
        # Bearish momentum
        elif (current['macd'] < current['macd_signal'] and
              previous['macd'] >= previous['macd_signal'] and
              current['rsi'] < 50 and current['rsi'] > 30):
            return {"signal_type": "sell"}
        
        return None
    
    def _calculate_metrics(self, results: Dict, initial_capital: float) -> Dict[str, Any]:
        """Calculate performance metrics"""
        try:
            final_equity = results["equity"]
            trades = results["trades"]
            equity_curve = results["equity_curve"]
            
            # Basic metrics
            total_return = (final_equity - initial_capital) / initial_capital
            total_trades = len([t for t in trades if t["type"] == "SELL"])
            
            if total_trades == 0:
                return {
                    "total_return": total_return,
                    "total_trades": 0,
                    "win_rate": 0,
                    "sharpe_ratio": 0,
                    "max_drawdown": 0,
                    "profit_factor": 0
                }
            
            # Trade analysis
            winning_trades = [t for t in trades if t["type"] == "SELL" and t.get("pnl", 0) > 0]
            losing_trades = [t for t in trades if t["type"] == "SELL" and t.get("pnl", 0) <= 0]
            
            win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0
            
            avg_win = np.mean([t["pnl"] for t in winning_trades]) if winning_trades else 0
            avg_loss = np.mean([abs(t["pnl"]) for t in losing_trades]) if losing_trades else 0
            
            profit_factor = (avg_win * len(winning_trades)) / (avg_loss * len(losing_trades)) if losing_trades else float('inf')
            
            # Drawdown calculation
            max_drawdown = self._calculate_max_drawdown(equity_curve)
            
            # Sharpe ratio (simplified)
            returns = []
            for i in range(1, len(equity_curve)):
                daily_return = (equity_curve[i]["equity"] - equity_curve[i-1]["equity"]) / equity_curve[i-1]["equity"]
                returns.append(daily_return)
            
            if returns:
                avg_return = np.mean(returns)
                std_return = np.std(returns)
                sharpe_ratio = (avg_return / std_return * np.sqrt(252)) if std_return > 0 else 0
            else:
                sharpe_ratio = 0
            
            return {
                "total_return": total_return,
                "total_return_percent": total_return * 100,
                "final_equity": final_equity,
                "total_trades": total_trades,
                "winning_trades": len(winning_trades),
                "losing_trades": len(losing_trades),
                "win_rate": win_rate,
                "avg_win": avg_win,
                "avg_loss": avg_loss,
                "profit_factor": profit_factor,
                "max_drawdown": max_drawdown,
                "max_drawdown_percent": max_drawdown * 100,
                "sharpe_ratio": sharpe_ratio
            }
            
        except Exception as e:
            logger.error(f"Error calculating metrics: {str(e)}")
            return {"error": str(e)}
    
    def _calculate_max_drawdown(self, equity_curve: List[Dict]) -> float:
        """Calculate maximum drawdown"""
        if not equity_curve:
            return 0
        
        peak = equity_curve[0]["equity"]
        max_dd = 0
        
        for point in equity_curve:
            equity = point["equity"]
            if equity > peak:
                peak = equity
            
            drawdown = (peak - equity) / peak
            if drawdown > max_dd:
                max_dd = drawdown
        
        return max_dd
    
    async def run_multiple_backtests(self, strategies: List[str], symbols: List[str], 
                                   start_date: str, end_date: str, 
                                   initial_capital: float = 100000.0) -> Dict[str, Any]:
        """Run backtests for multiple strategies and symbols"""
        results = {}
        
        for strategy in strategies:
            results[strategy] = {}
            for symbol in symbols:
                try:
                    result = await self.run_backtest(
                        strategy, symbol, start_date, end_date, initial_capital
                    )
                    results[strategy][symbol] = result
                    
                    # Small delay to avoid overwhelming the system
                    await asyncio.sleep(0.1)
                    
                except Exception as e:
                    logger.error(f"Error backtesting {strategy} on {symbol}: {str(e)}")
                    results[strategy][symbol] = {"error": str(e)}
        
        return results
    
    def validate_strategy_performance(self, metrics: Dict[str, Any], 
                                    min_sharpe: float = 1.0, 
                                    max_drawdown: float = 0.15,
                                    min_win_rate: float = 0.5) -> Dict[str, Any]:
        """Validate if strategy meets performance thresholds"""
        
        validation = {
            "passed": True,
            "reasons": [],
            "score": 0
        }
        
        # Check Sharpe ratio
        sharpe = metrics.get("sharpe_ratio", 0)
        if sharpe < min_sharpe:
            validation["passed"] = False
            validation["reasons"].append(f"Sharpe ratio {sharpe:.2f} below minimum {min_sharpe}")
        else:
            validation["score"] += 1
        
        # Check max drawdown
        drawdown = metrics.get("max_drawdown", 1)
        if drawdown > max_drawdown:
            validation["passed"] = False
            validation["reasons"].append(f"Max drawdown {drawdown:.2%} above maximum {max_drawdown:.2%}")
        else:
            validation["score"] += 1
        
        # Check win rate
        win_rate = metrics.get("win_rate", 0)
        if win_rate < min_win_rate:
            validation["passed"] = False
            validation["reasons"].append(f"Win rate {win_rate:.2%} below minimum {min_win_rate:.2%}")
        else:
            validation["score"] += 1
        
        # Check positive returns
        total_return = metrics.get("total_return", -1)
        if total_return <= 0:
            validation["passed"] = False
            validation["reasons"].append(f"Negative total return: {total_return:.2%}")
        else:
            validation["score"] += 1
        
        validation["score"] = validation["score"] / 4  # Normalize to 0-1
        
        return validation
