import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, date, timedelta
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from models.pnl_reports import PnLReport
from models.signals import Signal, SignalStatus
from .data_fetcher import DataFetcher

logger = logging.getLogger(__name__)

class PnLService:
    """Profit and Loss tracking service"""
    
    def __init__(self, data_fetcher: DataFetcher = None, db_session: AsyncSession = None):
        # Allow optional dependencies for tests
        self.data_fetcher = data_fetcher
        self.db = db_session
        self.daily_start_equity = 0.0
        # In-memory report storage for tests when DB is not provided
        self._in_memory_reports: Dict[str, Dict] = {}
    
    async def initialize_daily_tracking(self):
        """Initialize daily P&L tracking"""
        try:
            # Get starting equity for the day (guard if no data_fetcher in tests)
            if self.data_fetcher and hasattr(self.data_fetcher, 'get_margin_info'):
                margin_info = await self.data_fetcher.get_margin_info()
                if margin_info:
                    # support multiple naming conventions
                    self.daily_start_equity = float(margin_info.get('totalEquity', margin_info.get('availableMargin', 0) or 0))
            else:
                # No data_fetcher available in some test fixtures
                self.daily_start_equity = 0.0
            
            # Create or update today's P&L report
            today = date.today()
            await self._ensure_daily_report(today)
            
            logger.info(f"Daily P&L tracking initialized - Starting equity: ₹{self.daily_start_equity:,.2f}")
            
        except Exception as e:
            logger.error(f"Error initializing daily P&L tracking: {str(e)}")
    
    async def update_daily_pnl(self, *args, **kwargs) -> Dict[str, Any]:
        """Compatibility wrapper: accepts keywords like realized_pnl/unrealized_pnl/fees for tests.

        Original implementation computes values from portfolio; tests may call with explicit values.
        """
        # If called with explicit values, apply them to today's report directly
        if {'realized_pnl', 'unrealized_pnl', 'fees'}.issubset(set(kwargs.keys())):
            try:
                realized = float(kwargs.get('realized_pnl', 0))
                unrealized = float(kwargs.get('unrealized_pnl', 0))
                fees = float(kwargs.get('fees', 0))
                today = date.today()
                # If using in-memory reports (no DB), update dict directly
                if not self.db:
                    key = today.isoformat()
                    if key not in self._in_memory_reports:
                        await self._ensure_daily_report(today)
                    r = self._in_memory_reports.get(key)
                    if r is None:
                        r = {
                            "date": key,
                            "daily_pnl": 0.0,
                            "realized_pnl": 0.0,
                            "unrealized_pnl": 0.0,
                            "total_trades": 0,
                            "starting_equity": self.daily_start_equity,
                            "ending_equity": self.daily_start_equity,
                            "drawdown": 0.0,
                            "cumulative_pnl": 0.0,
                        }
                        self._in_memory_reports[key] = r
                    r["daily_pnl"] = realized + unrealized - fees
                    r["realized_pnl"] = realized
                    r["unrealized_pnl"] = unrealized
                    r["total_trades"] = r.get("total_trades", 0)
                    return r

                report = await self._get_or_create_daily_report(today)
                report.daily_pnl = realized + unrealized - fees
                report.realized_pnl = realized
                report.unrealized_pnl = unrealized
                report.total_trades = report.total_trades or 0
                if self.db:
                    await self.db.commit()
                return report.to_dict()
            except Exception as e:
                logger.error(f"Error in compatibility update_daily_pnl: {e}")
                return {"error": str(e)}

        # Fallback to existing implementation
        """Update daily P&L calculations"""
        try:
            today = date.today()
            
            # Get current portfolio data
            portfolio_data = await self.data_fetcher.get_portfolio_data()
            current_pnl = portfolio_data.get('total_pnl', 0.0)
            
            # Get margin info for current equity
            margin_info = await self.data_fetcher.get_margin_info()
            current_equity = float(margin_info.get('totalEquity', 0)) if margin_info else 0
            
            # Calculate realized P&L from executed trades
            realized_pnl = await self._calculate_realized_pnl(today)
            
            # Calculate unrealized P&L
            unrealized_pnl = current_pnl - realized_pnl
            
            # Get trade statistics
            trade_stats = await self._get_trade_statistics(today)
            
            # Calculate drawdown
            drawdown = 0.0
            if self.daily_start_equity > 0:
                drawdown = max(0, (self.daily_start_equity - current_equity) / self.daily_start_equity)
            
            # Update or create daily report
            report = await self._get_or_create_daily_report(today)
            
            report.daily_pnl = current_pnl
            report.realized_pnl = realized_pnl
            report.unrealized_pnl = unrealized_pnl
            report.total_trades = trade_stats['total_trades']
            report.winning_trades = trade_stats['winning_trades']
            report.losing_trades = trade_stats['losing_trades']
            report.starting_equity = self.daily_start_equity
            report.ending_equity = current_equity
            report.drawdown = drawdown
            
            # Update cumulative P&L
            report.cumulative_pnl = await self._calculate_cumulative_pnl(today)
            
            # Update max drawdown
            report.max_drawdown = await self._calculate_max_drawdown(today)
            
            await self.db.commit()
            
            logger.info(f"Daily P&L updated: ₹{current_pnl:,.2f}")
            
            return report.to_dict()
            
        except Exception as e:
            logger.error(f"Error updating daily P&L: {str(e)}")
            await self.db.rollback()
            return {"error": str(e)}
    
    async def _calculate_realized_pnl(self, target_date: date) -> float:
        """Calculate realized P&L from executed trades"""
        try:
            # Get executed signals for the day
            stmt = select(Signal).where(
                Signal.status == SignalStatus.EXECUTED,
                func.date(Signal.executed_at) == target_date
            )
            
            result = await self.db.execute(stmt)
            executed_signals = result.scalars().all()
            
            realized_pnl = 0.0
            
            for signal in executed_signals:
                # This would typically calculate P&L based on entry/exit prices
                # For now, we'll use a simplified calculation
                if signal.extras and 'realized_pnl' in signal.extras:
                    realized_pnl += signal.extras['realized_pnl']
            
            return realized_pnl
            
        except Exception as e:
            logger.error(f"Error calculating realized P&L: {str(e)}")
            return 0.0
    
    async def _get_trade_statistics(self, target_date: date) -> Dict[str, int]:
        """Get trade statistics for the day"""
        try:
            # Get executed signals for the day
            stmt = select(Signal).where(
                Signal.status == SignalStatus.EXECUTED,
                func.date(Signal.executed_at) == target_date
            )
            
            result = await self.db.execute(stmt)
            executed_signals = result.scalars().all()
            
            total_trades = len(executed_signals)
            winning_trades = 0
            losing_trades = 0
            
            for signal in executed_signals:
                if signal.extras and 'realized_pnl' in signal.extras:
                    pnl = signal.extras['realized_pnl']
                    if pnl > 0:
                        winning_trades += 1
                    elif pnl < 0:
                        losing_trades += 1
            
            return {
                'total_trades': total_trades,
                'winning_trades': winning_trades,
                'losing_trades': losing_trades
            }
            
        except Exception as e:
            logger.error(f"Error getting trade statistics: {str(e)}")
            return {'total_trades': 0, 'winning_trades': 0, 'losing_trades': 0}
    
    async def _get_or_create_daily_report(self, target_date: date) -> PnLReport:
        """Get or create daily P&L report"""
        try:
            # If DB is not available (tests), use in-memory dict
            if not self.db:
                key = target_date.isoformat()
                if key not in self._in_memory_reports:
                    self._in_memory_reports[key] = {
                        "date": key,
                        "daily_pnl": 0.0,
                        "realized_pnl": 0.0,
                        "unrealized_pnl": 0.0,
                        "total_trades": 0,
                        "starting_equity": self.daily_start_equity,
                        "ending_equity": self.daily_start_equity,
                        "drawdown": 0.0,
                        "cumulative_pnl": 0.0,
                    }
                # Create a lightweight object that mimics PnLReport.to_dict()
                class _ReportObj:
                    def __init__(self, d):
                        self._d = d
                    def to_dict(self):
                        return self._d
                return _ReportObj(self._in_memory_reports[key])

            stmt = select(PnLReport).where(PnLReport.date == target_date)
            result = await self.db.execute(stmt)
            report = result.scalar_one_or_none()

            if not report:
                report = PnLReport(
                    date=target_date,
                    daily_pnl=0.0,
                    cumulative_pnl=0.0,
                    drawdown=0.0
                )
                self.db.add(report)
                await self.db.flush()

            return report
            
        except Exception as e:
            logger.error(f"Error getting/creating daily report: {str(e)}")
            raise
    
    async def _ensure_daily_report(self, target_date: date):
        """Ensure daily report exists"""
        obj = await self._get_or_create_daily_report(target_date)
        # If using DB, commit; if in-memory, nothing to do
        if self.db:
            await self.db.commit()
    
    async def _calculate_cumulative_pnl(self, target_date: date) -> float:
        """Calculate cumulative P&L up to target date"""
        try:
            stmt = select(func.sum(PnLReport.daily_pnl)).where(
                PnLReport.date <= target_date
            )
            
            result = await self.db.execute(stmt)
            cumulative_pnl = result.scalar() or 0.0
            
            return float(cumulative_pnl)
            
        except Exception as e:
            logger.error(f"Error calculating cumulative P&L: {str(e)}")
            return 0.0
    
    async def _calculate_max_drawdown(self, target_date: date) -> float:
        """Calculate maximum drawdown up to target date"""
        try:
            # Get all reports up to target date
            stmt = select(PnLReport).where(
                PnLReport.date <= target_date
            ).order_by(PnLReport.date)
            
            result = await self.db.execute(stmt)
            reports = result.scalars().all()
            
            if not reports:
                return 0.0
            
            # Calculate running equity and max drawdown
            peak_equity = reports[0].starting_equity or 100000  # Default starting equity
            max_drawdown = 0.0
            
            for report in reports:
                current_equity = report.ending_equity or peak_equity
                
                if current_equity > peak_equity:
                    peak_equity = current_equity
                
                drawdown = (peak_equity - current_equity) / peak_equity if peak_equity > 0 else 0
                max_drawdown = max(max_drawdown, drawdown)
            
            return max_drawdown
            
        except Exception as e:
            logger.error(f"Error calculating max drawdown: {str(e)}")
            return 0.0
    
    async def get_daily_report(self, target_date: Optional[date] = None) -> Dict[str, Any]:
        """Get daily P&L report"""
        if target_date is None:
            target_date = date.today()
        
        try:
            # If in-memory
            if not self.db:
                key = target_date.isoformat()
                r = self._in_memory_reports.get(key)
                if r:
                    return r
                return {"date": key, "daily_pnl": 0.0, "cumulative_pnl": 0.0, "message": "No report found for this date"}

            stmt = select(PnLReport).where(PnLReport.date == target_date)
            result = await self.db.execute(stmt)
            report = result.scalar_one_or_none()
            
            if report:
                return report.to_dict()
            else:
                return {
                    "date": target_date.isoformat(),
                    "daily_pnl": 0.0,
                    "cumulative_pnl": 0.0,
                    "message": "No report found for this date"
                }
                
        except Exception as e:
            logger.error(f"Error getting daily report: {str(e)}")
            return {"error": str(e)}
    
    async def get_period_summary(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """Get P&L summary for a period"""
        try:
            stmt = select(PnLReport).where(
                PnLReport.date >= start_date,
                PnLReport.date <= end_date
            ).order_by(PnLReport.date)
            
            result = await self.db.execute(stmt)
            reports = result.scalars().all()
            
            if not reports:
                return {
                    "period": f"{start_date} to {end_date}",
                    "total_pnl": 0.0,
                    "reports": []
                }
            
            # Calculate summary statistics
            total_pnl = sum(report.daily_pnl for report in reports)
            total_trades = sum(report.total_trades for report in reports)
            total_winning = sum(report.winning_trades for report in reports)
            total_losing = sum(report.losing_trades for report in reports)
            
            win_rate = total_winning / total_trades if total_trades > 0 else 0
            max_daily_gain = max(report.daily_pnl for report in reports)
            max_daily_loss = min(report.daily_pnl for report in reports)
            
            return {
                "period": f"{start_date} to {end_date}",
                "total_pnl": total_pnl,
                "total_trades": total_trades,
                "winning_trades": total_winning,
                "losing_trades": total_losing,
                "win_rate": win_rate,
                "max_daily_gain": max_daily_gain,
                "max_daily_loss": max_daily_loss,
                "trading_days": len(reports),
                "avg_daily_pnl": total_pnl / len(reports) if reports else 0,
                "reports": [report.to_dict() for report in reports]
            }
            
        except Exception as e:
            logger.error(f"Error getting period summary: {str(e)}")
            return {"error": str(e)}

    async def get_monthly_summary(self, month_str: str) -> Dict[str, Any]:
        """Return a simple monthly summary for a given 'YYYY-MM' month string. Used by tests."""
        try:
            # Parse month
            year, month = month_str.split('-')
            start = date(int(year), int(month), 1)
            # Rough end of month
            if int(month) == 12:
                end = date(int(year) + 1, 1, 1) - timedelta(days=1)
            else:
                end = date(int(year), int(month) + 1, 1) - timedelta(days=1)

            summary = await self.get_period_summary(start, end)
            # Map to expected keys
            return {
                "month": month_str,
                "monthly_pnl": summary.get('total_pnl', 0.0),
                "total_trades": summary.get('total_trades', 0),
                "win_rate": summary.get('win_rate', 0.0),
                "reports": summary.get('reports', [])
            }
        except Exception as e:
            logger.error(f"Error getting monthly summary: {e}")
            return {"month": month_str, "monthly_pnl": 0.0, "total_trades": 0, "win_rate": 0.0}
    
    async def get_equity_curve(self, days: int = 30) -> List[Dict[str, Any]]:
        """Get equity curve data for charting"""
        try:
            end_date = date.today()
            start_date = end_date - timedelta(days=days)
            
            stmt = select(PnLReport).where(
                PnLReport.date >= start_date,
                PnLReport.date <= end_date
            ).order_by(PnLReport.date)
            
            result = await self.db.execute(stmt)
            reports = result.scalars().all()
            
            equity_curve = []
            
            for report in reports:
                equity_curve.append({
                    "date": report.date.isoformat(),
                    "equity": report.ending_equity or 0,
                    "daily_pnl": report.daily_pnl,
                    "cumulative_pnl": report.cumulative_pnl
                })
            
            return equity_curve
            
        except Exception as e:
            logger.error(f"Error getting equity curve: {str(e)}")
            return []
    
    async def calculate_performance_metrics(self, days: int = 30) -> Dict[str, Any]:
        """Calculate comprehensive performance metrics"""
        try:
            end_date = date.today()
            start_date = end_date - timedelta(days=days)
            
            period_summary = await self.get_period_summary(start_date, end_date)
            
            if not period_summary.get("reports"):
                return {"error": "No data available for metrics calculation"}
            
            reports = period_summary["reports"]
            daily_returns = [report["daily_pnl"] / (report["starting_equity"] or 100000) for report in reports if report.get("starting_equity")]
            
            if not daily_returns:
                return {"error": "Insufficient data for metrics calculation"}
            
            # Calculate metrics
            import numpy as np
            
            avg_return = np.mean(daily_returns)
            std_return = np.std(daily_returns)
            
            # Sharpe ratio (annualized)
            sharpe_ratio = (avg_return / std_return * np.sqrt(252)) if std_return > 0 else 0
            
            # Sortino ratio (downside deviation)
            negative_returns = [r for r in daily_returns if r < 0]
            downside_std = np.std(negative_returns) if negative_returns else 0
            sortino_ratio = (avg_return / downside_std * np.sqrt(252)) if downside_std > 0 else 0
            
            # Maximum drawdown
            max_drawdown = max(report.get("max_drawdown", 0) for report in reports)
            
            # Calmar ratio
            calmar_ratio = (avg_return * 252 / max_drawdown) if max_drawdown > 0 else 0
            
            return {
                "period_days": days,
                "total_return": period_summary["total_pnl"],
                "avg_daily_return": avg_return,
                "volatility": std_return,
                "sharpe_ratio": sharpe_ratio,
                "sortino_ratio": sortino_ratio,
                "max_drawdown": max_drawdown,
                "calmar_ratio": calmar_ratio,
                "win_rate": period_summary["win_rate"],
                "total_trades": period_summary["total_trades"],
                "profit_factor": self._calculate_profit_factor(reports)
            }
            
        except Exception as e:
            logger.error(f"Error calculating performance metrics: {str(e)}")
            return {"error": str(e)}
    
    def _calculate_profit_factor(self, reports: List[Dict]) -> float:
        """Calculate profit factor"""
        try:
            total_wins = sum(report.get("winning_trades", 0) for report in reports)
            total_losses = sum(report.get("losing_trades", 0) for report in reports)
            
            if total_losses == 0:
                return float('inf') if total_wins > 0 else 0
            
            # Simplified profit factor calculation
            # In a real implementation, you'd use actual win/loss amounts
            return total_wins / total_losses
            
        except Exception as e:
            logger.error(f"Error calculating profit factor: {str(e)}")
            return 0.0

    async def calculate_portfolio_pnl(self, positions: List[Dict]) -> float:
        """Calculate total PnL for a given set of positions (used by tests)."""
        try:
            total = 0.0
            for p in positions:
                qty = p.get('quantity', 0)
                avg = p.get('avg_price') or p.get('avgPrice') or p.get('avg')
                cur = p.get('current_price') or p.get('ltp') or p.get('currentPrice')
                total += qty * (cur - avg)
            return float(total)
        except Exception as e:
            logger.error(f"Error calculating portfolio pnl: {e}")
            return 0.0
            return 0.0
