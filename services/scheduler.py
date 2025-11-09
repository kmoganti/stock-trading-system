"""
Trading Strategy Scheduler
=========================

Optimized scheduling system for different trading strategies:
- Day Trading: High-frequency execution (every 5-15 minutes during market hours)
- Short Selling: Frequent monitoring (every 30 minutes during market hours)  
- Short Term: Regular intervals (every 2-4 hours during market hours)
- Long Term: Daily execution (once per day after market close)

Features:
- Market hours awareness
- Strategy-specific frequencies
- Resource optimization
- Error handling and recovery
- Performance monitoring
"""

import asyncio
import logging
from datetime import datetime, time, timedelta
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass
from enum import Enum
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.job import Job

from config.settings import get_settings
from services.strategy import StrategyService
from services.data_fetcher import DataFetcher
from services.iifl_api import IIFLAPIService

logger = logging.getLogger(__name__)

class StrategyType(Enum):
    """Trading strategy types with different execution frequencies"""
    DAY_TRADING = "day_trading"
    SHORT_SELLING = "short_selling"
    SHORT_TERM = "short_term"
    LONG_TERM = "long_term"

@dataclass
class ScheduleConfig:
    """Configuration for strategy scheduling"""
    strategy_type: StrategyType
    enabled: bool
    # Market hours execution (IST timezone)
    market_start_time: time
    market_end_time: time
    # Execution frequency during market hours
    interval_minutes: int
    # Pre-market and post-market execution
    pre_market_enabled: bool = False
    post_market_enabled: bool = False
    # Weekend execution (for long-term analysis)
    weekend_enabled: bool = False
    # Maximum concurrent executions
    max_concurrent: int = 1
    # Timeout for strategy execution
    timeout_minutes: int = 15

class TradingScheduler:
    """Advanced scheduler for trading strategies with market awareness"""
    
    def __init__(self):
        self.settings = get_settings()
        self.scheduler = AsyncIOScheduler()
        self.ist_timezone = pytz.timezone('Asia/Kolkata')
        
        # Initialize services (will be set up when scheduler starts)
        self.iifl_api: Optional[IIFLAPIService] = None
        self.data_fetcher: Optional[DataFetcher] = None
        self.strategy_service: Optional[StrategyService] = None
        
        # Track running jobs to prevent overlaps
        self.running_jobs: Dict[StrategyType, bool] = {}
        
        # Performance monitoring
        self.execution_stats: Dict[StrategyType, Dict[str, Any]] = {}
        
        # Schedule configurations based on analysis results
        self.schedule_configs = {
            StrategyType.DAY_TRADING: ScheduleConfig(
                strategy_type=StrategyType.DAY_TRADING,
                enabled=True,
                market_start_time=time(9, 15),  # 9:15 AM IST
                market_end_time=time(15, 30),   # 3:30 PM IST
                interval_minutes=5,             # Every 5 minutes (high frequency)
                pre_market_enabled=True,        # Pre-market gap analysis
                post_market_enabled=False,      # Intraday only
                weekend_enabled=False,
                max_concurrent=2,               # Allow some overlap for gap analysis
                timeout_minutes=10              # Quick execution required
            ),
            StrategyType.SHORT_SELLING: ScheduleConfig(
                strategy_type=StrategyType.SHORT_SELLING,
                enabled=True,
                market_start_time=time(9, 15),  # 9:15 AM IST
                market_end_time=time(15, 30),   # 3:30 PM IST
                interval_minutes=30,            # Every 30 minutes (frequent monitoring)
                pre_market_enabled=False,       # Market hours only
                post_market_enabled=True,       # End-of-day overbought analysis
                weekend_enabled=False,
                max_concurrent=1,
                timeout_minutes=15
            ),
            StrategyType.SHORT_TERM: ScheduleConfig(
                strategy_type=StrategyType.SHORT_TERM,
                enabled=True,
                market_start_time=time(9, 15),  # 9:15 AM IST
                market_end_time=time(15, 30),   # 3:30 PM IST
                interval_minutes=120,           # Every 2 hours (regular intervals)
                pre_market_enabled=True,        # Pre-market preparation
                post_market_enabled=True,       # Post-market analysis
                weekend_enabled=False,
                max_concurrent=1,
                timeout_minutes=20
            ),
            StrategyType.LONG_TERM: ScheduleConfig(
                strategy_type=StrategyType.LONG_TERM,
                enabled=True,
                market_start_time=time(16, 0),  # 4:00 PM IST (after market close)
                market_end_time=time(16, 0),    # Single execution
                interval_minutes=1440,          # Once per day
                pre_market_enabled=False,
                post_market_enabled=True,       # After market close only
                weekend_enabled=True,           # Weekend analysis allowed
                max_concurrent=1,
                timeout_minutes=30              # More comprehensive analysis
            )
        }
    
    async def initialize_services(self):
        """Initialize trading services with timeout protection"""
        try:
            # Initialize with timeout to prevent hanging
            logger.info("Initializing trading services for scheduler...")
            
            # Initialize running job tracking first (doesn't require IIFL)
            for strategy_type in StrategyType:
                self.running_jobs[strategy_type] = False
                self.execution_stats[strategy_type] = {
                    'total_runs': 0,
                    'successful_runs': 0,
                    'failed_runs': 0,
                    'avg_execution_time': 0.0,
                    'last_execution': None,
                    'last_success': None,
                    'last_error': None
                }
            
            # Initialize IIFL API with timeout protection (15 seconds)
            try:
                async def init_iifl_services():
                    """Initialize IIFL services"""
                    self.iifl_api = IIFLAPIService()
                    self.data_fetcher = DataFetcher(self.iifl_api)
                    self.strategy_service = StrategyService(self.data_fetcher)
                
                await asyncio.wait_for(
                    init_iifl_services(),
                    timeout=15.0
                )
                logger.info("✅ Trading services initialized successfully")
            except asyncio.TimeoutError:
                logger.warning("⏱️ IIFL API initialization timed out - services will be initialized on first job run")
                # Set to None so jobs can reinitialize if needed
                self.iifl_api = None
                self.data_fetcher = None
                self.strategy_service = None
            except Exception as e:
                logger.warning(f"⚠️ Failed to initialize IIFL services: {e} - services will be initialized on first job run")
                self.iifl_api = None
                self.data_fetcher = None
                self.strategy_service = None
            
        except Exception as e:
            logger.error(f"Failed to initialize trading services: {e}")
            # Don't raise - allow scheduler to start without services
            logger.warning("Scheduler will start but services are not initialized")
    
    def is_market_day(self, date: datetime) -> bool:
        """Check if given date is a trading day (excludes weekends and holidays)"""
        # For now, exclude weekends. Could be extended to include market holidays
        return date.weekday() < 5  # Monday=0, Sunday=6
    
    def is_market_hours(self, current_time: datetime, config: ScheduleConfig) -> bool:
        """Check if current time is within market hours for the strategy"""
        current_time_ist = current_time.astimezone(self.ist_timezone)
        current_time_only = current_time_ist.time()
        
        # Check if it's a market day
        if not config.weekend_enabled and not self.is_market_day(current_time_ist):
            return False
        
        # For single execution strategies (like long-term)
        if config.interval_minutes >= 1440:  # Daily or less frequent
            return True
        
        # Check market hours
        return config.market_start_time <= current_time_only <= config.market_end_time
    
    async def _ensure_services_initialized(self):
        """Ensure services are initialized before running jobs"""
        if self.strategy_service is None:
            logger.info("Services not initialized, initializing now...")
            try:
                self.iifl_api = IIFLAPIService()
                self.data_fetcher = DataFetcher(self.iifl_api)
                self.strategy_service = StrategyService(self.data_fetcher)
                logger.info("✅ Services initialized successfully")
            except Exception as e:
                logger.error(f"❌ Failed to initialize services: {e}")
                raise RuntimeError("Cannot execute job: services not available")
        return True
    
    async def execute_day_trading_strategy(self):
        """Execute day trading strategy - high frequency gap and breakout analysis"""
        strategy_type = StrategyType.DAY_TRADING
        config = self.schedule_configs[strategy_type]
        
        if self.running_jobs[strategy_type]:
            logger.warning("Day trading strategy already running, skipping execution")
            return
        
        start_time = datetime.now()
        
        try:
            self.running_jobs[strategy_type] = True
            
            # Check if services are initialized
            try:
                await asyncio.wait_for(
                    self._ensure_services_initialized(),
                    timeout=10.0
                )
            except asyncio.TimeoutError:
                logger.error("⏱️ Service initialization timed out for day trading")
                self._update_execution_stats(strategy_type, False, 0, "Service initialization timeout")
                return
            except Exception as e:
                logger.error(f"❌ Service initialization failed: {e}")
                self._update_execution_stats(strategy_type, False, 0, str(e))
                return
            
            logger.info("🚀 Executing day trading strategy...")
            
            # Focus on high-volume, liquid stocks for day trading
            symbols = [
                'RELIANCE', 'TCS', 'HDFCBANK', 'INFY', 'HINDUNILVR', 
                'ICICIBANK', 'KOTAKBANK', 'LT', 'ITC', 'AXISBANK'
            ]
            
            signals_generated = []
            
            # Execute with overall timeout
            try:
                async def generate_all_signals():
                    for symbol in symbols:
                        try:
                            # Generate day trading signals with timeout per symbol
                            signals = await asyncio.wait_for(
                                self.strategy_service.generate_signals(
                                    symbol, 
                                    category="day_trading",
                                    strategy_name=None
                                ),
                                timeout=30.0  # 30 seconds per symbol
                            )
                            
                            if signals:
                                signals_generated.extend(signals)
                                logger.info(f"📈 Day trading signals for {symbol}: {len(signals)} signals")
                        
                        except asyncio.TimeoutError:
                            logger.warning(f"⏱️ Timeout generating day trading signals for {symbol}")
                        except Exception as e:
                            logger.error(f"Error generating day trading signals for {symbol}: {e}")
                
                # Execute all with overall timeout (config timeout in minutes)
                await asyncio.wait_for(
                    generate_all_signals(),
                    timeout=config.timeout_minutes * 60
                )
                
            except asyncio.TimeoutError:
                logger.error(f"⏱️ Day trading strategy execution exceeded {config.timeout_minutes} minute timeout")
            
            # Log execution results
            execution_time = (datetime.now() - start_time).total_seconds()
            self._update_execution_stats(strategy_type, True, execution_time)
            
            logger.info(f"✅ Day trading strategy completed: {len(signals_generated)} signals in {execution_time:.2f}s")
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            self._update_execution_stats(strategy_type, False, execution_time, str(e))
            logger.error(f"❌ Day trading strategy failed: {e}")
            
        finally:
            self.running_jobs[strategy_type] = False
    
    async def execute_short_selling_strategy(self):
        """Execute short selling strategy - monitor overbought conditions"""
        strategy_type = StrategyType.SHORT_SELLING
        config = self.schedule_configs[strategy_type]
        
        if self.running_jobs[strategy_type]:
            logger.warning("Short selling strategy already running, skipping execution")
            return
        
        start_time = datetime.now()
        
        try:
            self.running_jobs[strategy_type] = True
            
            # Check if services are initialized
            try:
                await asyncio.wait_for(
                    self._ensure_services_initialized(),
                    timeout=10.0
                )
            except (asyncio.TimeoutError, Exception) as e:
                error_msg = "Service initialization timeout" if isinstance(e, asyncio.TimeoutError) else str(e)
                logger.error(f"❌ Service initialization failed for short selling: {error_msg}")
                self._update_execution_stats(strategy_type, False, 0, error_msg)
                return
            
            logger.info("🔴 Executing short selling strategy...")
            
            # Focus on stocks that showed short signals in backtest
            symbols = [
                'EICHERMOT', 'HEROMOTOCO', 'DRREDDY', 'ADANIENT', 'MARUTI',
                'HINDUNILVR', 'TCS', 'RELIANCE', 'HDFCBANK', 'BAJFINANCE'
            ]
            
            short_signals = []
            
            # Execute with timeout protection
            try:
                # Use the specialized short selling analyzer
                from short_selling_daytrading_backtest import ShortSellingDayTradingAnalyzer
                analyzer = ShortSellingDayTradingAnalyzer()
                
                async def analyze_all_symbols():
                    for symbol in symbols[:5]:  # Limit to 5 for frequent execution
                        try:
                            analysis = await asyncio.wait_for(
                                analyzer.analyze_symbol(symbol),
                                timeout=60.0  # 60 seconds per symbol
                            )
                            if analysis.get('short_selling_signals'):
                                short_signals.extend(analysis['short_selling_signals'])
                                logger.info(f"🔻 Short selling signals for {symbol}: {len(analysis['short_selling_signals'])} signals")
                        
                        except asyncio.TimeoutError:
                            logger.warning(f"⏱️ Timeout analyzing short selling for {symbol}")
                        except Exception as e:
                            logger.error(f"Error analyzing short selling for {symbol}: {e}")
                
                await asyncio.wait_for(
                    analyze_all_symbols(),
                    timeout=config.timeout_minutes * 60
                )
                
            except asyncio.TimeoutError:
                logger.error(f"⏱️ Short selling strategy exceeded {config.timeout_minutes} minute timeout")
            
            execution_time = (datetime.now() - start_time).total_seconds()
            self._update_execution_stats(strategy_type, True, execution_time)
            
            logger.info(f"✅ Short selling strategy completed: {len(short_signals)} signals in {execution_time:.2f}s")
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            self._update_execution_stats(strategy_type, False, execution_time, str(e))
            logger.error(f"❌ Short selling strategy failed: {e}")
            
        finally:
            self.running_jobs[strategy_type] = False
    
    async def execute_short_term_strategy(self):
        """Execute short term strategy - swing trading signals"""
        strategy_type = StrategyType.SHORT_TERM
        config = self.schedule_configs[strategy_type]
        
        if self.running_jobs[strategy_type]:
            logger.warning("Short term strategy already running, skipping execution")
            return
        
        start_time = datetime.now()
        
        try:
            self.running_jobs[strategy_type] = True
            
            # Check if services are initialized
            try:
                await asyncio.wait_for(
                    self._ensure_services_initialized(),
                    timeout=10.0
                )
            except (asyncio.TimeoutError, Exception) as e:
                error_msg = "Service initialization timeout" if isinstance(e, asyncio.TimeoutError) else str(e)
                logger.error(f"❌ Service initialization failed for short term: {error_msg}")
                self._update_execution_stats(strategy_type, False, 0, error_msg)
                return
            
            logger.info("📈 Executing short term strategy...")
            
            # Use broader set of stocks for short-term analysis
            symbols = [
                'RELIANCE', 'TCS', 'HDFCBANK', 'INFY', 'HINDUNILVR', 
                'ICICIBANK', 'KOTAKBANK', 'LT', 'ITC', 'AXISBANK',
                'SBIN', 'BHARTIARTL', 'ASIANPAINT', 'MARUTI', 'BAJFINANCE'
            ]
            
            signals_generated = []
            
            try:
                async def generate_all_signals():
                    for symbol in symbols:
                        try:
                            signals = await asyncio.wait_for(
                                self.strategy_service.generate_signals(
                                    symbol, 
                                    category="short_term",
                                    strategy_name=None
                                ),
                                timeout=45.0  # 45 seconds per symbol
                            )
                            
                            if signals:
                                signals_generated.extend(signals)
                                logger.info(f"📊 Short term signals for {symbol}: {len(signals)} signals")
                        
                        except asyncio.TimeoutError:
                            logger.warning(f"⏱️ Timeout generating short term signals for {symbol}")
                        except Exception as e:
                            logger.error(f"Error generating short term signals for {symbol}: {e}")
                
                await asyncio.wait_for(
                    generate_all_signals(),
                    timeout=config.timeout_minutes * 60
                )
                
            except asyncio.TimeoutError:
                logger.error(f"⏱️ Short term strategy exceeded {config.timeout_minutes} minute timeout")
            
            execution_time = (datetime.now() - start_time).total_seconds()
            self._update_execution_stats(strategy_type, True, execution_time)
            
            logger.info(f"✅ Short term strategy completed: {len(signals_generated)} signals in {execution_time:.2f}s")
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            self._update_execution_stats(strategy_type, False, execution_time, str(e))
            logger.error(f"❌ Short term strategy failed: {e}")
            
        finally:
            self.running_jobs[strategy_type] = False
    
    async def execute_long_term_strategy(self):
        """Execute long term strategy - comprehensive daily analysis"""
        strategy_type = StrategyType.LONG_TERM
        config = self.schedule_configs[strategy_type]
        
        if self.running_jobs[strategy_type]:
            logger.warning("Long term strategy already running, skipping execution")
            return
        
        start_time = datetime.now()
        
        try:
            self.running_jobs[strategy_type] = True
            
            # Check if services are initialized
            try:
                await asyncio.wait_for(
                    self._ensure_services_initialized(),
                    timeout=10.0
                )
            except (asyncio.TimeoutError, Exception) as e:
                error_msg = "Service initialization timeout" if isinstance(e, asyncio.TimeoutError) else str(e)
                logger.error(f"❌ Service initialization failed for long term: {error_msg}")
                self._update_execution_stats(strategy_type, False, 0, error_msg)
                return
            
            logger.info("📈 Executing long term strategy...")
            
            # Use full NIFTY universe for comprehensive analysis
            symbols = [
                'RELIANCE', 'TCS', 'HDFCBANK', 'INFY', 'HINDUNILVR', 'ICICIBANK', 
                'KOTAKBANK', 'LT', 'ITC', 'AXISBANK', 'SBIN', 'BHARTIARTL', 
                'ASIANPAINT', 'MARUTI', 'BAJFINANCE', 'HCLTECH', 'WIPRO', 
                'ULTRACEMCO', 'TITAN', 'NESTLEIND', 'POWERGRID', 'NTPC'
            ]
            
            signals_generated = []
            
            try:
                async def generate_all_signals():
                    for symbol in symbols:
                        try:
                            signals = await asyncio.wait_for(
                                self.strategy_service.generate_signals(
                                    symbol, 
                                    category="long_term",
                                    strategy_name=None
                                ),
                                timeout=60.0  # 60 seconds per symbol
                            )
                            
                            if signals:
                                signals_generated.extend(signals)
                                logger.info(f"📈 Long term signals for {symbol}: {len(signals)} signals")
                        
                        except asyncio.TimeoutError:
                            logger.warning(f"⏱️ Timeout generating long term signals for {symbol}")
                        except Exception as e:
                            logger.error(f"Error generating long term signals for {symbol}: {e}")
                
                await asyncio.wait_for(
                    generate_all_signals(),
                    timeout=config.timeout_minutes * 60
                )
                
            except asyncio.TimeoutError:
                logger.error(f"⏱️ Long term strategy exceeded {config.timeout_minutes} minute timeout")
            
            execution_time = (datetime.now() - start_time).total_seconds()
            self._update_execution_stats(strategy_type, True, execution_time)
            
            logger.info(f"✅ Long term strategy completed: {len(signals_generated)} signals in {execution_time:.2f}s")
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            self._update_execution_stats(strategy_type, False, execution_time, str(e))
            logger.error(f"❌ Long term strategy failed: {e}")
            
        finally:
            self.running_jobs[strategy_type] = False
    
    def _update_execution_stats(self, strategy_type: StrategyType, success: bool, 
                              execution_time: float, error: Optional[str] = None):
        """Update execution statistics for monitoring"""
        stats = self.execution_stats[strategy_type]
        stats['total_runs'] += 1
        
        if success:
            stats['successful_runs'] += 1
            stats['last_success'] = datetime.now()
        else:
            stats['failed_runs'] += 1
            stats['last_error'] = error
        
        # Update average execution time
        current_avg = stats['avg_execution_time']
        total_runs = stats['total_runs']
        stats['avg_execution_time'] = (current_avg * (total_runs - 1) + execution_time) / total_runs
        stats['last_execution'] = datetime.now()
    
    def get_execution_stats(self) -> Dict[str, Any]:
        """Get execution statistics for all strategies"""
        return {
            strategy_type.value: {
                **stats,
                'success_rate': (stats['successful_runs'] / max(stats['total_runs'], 1)) * 100,
                'last_execution': stats['last_execution'].isoformat() if stats['last_execution'] else None,
                'last_success': stats['last_success'].isoformat() if stats['last_success'] else None
            }
            for strategy_type, stats in self.execution_stats.items()
        }
    
    def setup_schedules(self):
        """Setup all strategy schedules based on configurations"""
        
        # Day Trading - Every 5 minutes during market hours
        self.scheduler.add_job(
            func=self.execute_day_trading_strategy,
            trigger=CronTrigger(
                minute='*/5',  # Every 5 minutes
                second=0,
                start_date='2025-01-01 09:15:00',
                end_date='2030-12-31 15:30:00',
                timezone=self.ist_timezone
            ),
            id='day_trading_strategy',
            name='Day Trading Strategy',
            max_instances=2,  # Allow some overlap
            coalesce=True,
            misfire_grace_time=60
        )
        
        # Short Selling - Every 30 minutes during market hours + post-market
        self.scheduler.add_job(
            func=self.execute_short_selling_strategy,
            trigger=CronTrigger(
                minute='0,30',  # Every 30 minutes
                second=0,
                start_date='2025-01-01 09:15:00',
                end_date='2030-12-31 16:00:00',
                timezone=self.ist_timezone
            ),
            id='short_selling_strategy',
            name='Short Selling Strategy',
            max_instances=1,
            coalesce=True,
            misfire_grace_time=300
        )
        
        # Short Term - Every 2 hours during extended hours
        self.scheduler.add_job(
            func=self.execute_short_term_strategy,
            trigger=CronTrigger(
                hour='9,11,13,15,17',  # 5 times per day
                minute=15,
                second=0,
                timezone=self.ist_timezone
            ),
            id='short_term_strategy',
            name='Short Term Strategy',
            max_instances=1,
            coalesce=True,
            misfire_grace_time=600
        )
        
        # Long Term - Once daily after market close
        self.scheduler.add_job(
            func=self.execute_long_term_strategy,
            trigger=CronTrigger(
                hour=16,  # 4:00 PM IST
                minute=0,
                second=0,
                timezone=self.ist_timezone
            ),
            id='long_term_strategy',
            name='Long Term Strategy',
            max_instances=1,
            coalesce=True,
            misfire_grace_time=3600
        )
        
        logger.info("All strategy schedules configured successfully")
    
    async def start(self):
        """Start the scheduler"""
        try:
            await self.initialize_services()
            self.setup_schedules()
            
            self.scheduler.start()
            logger.info("🚀 Trading scheduler started successfully")
            logger.info("📅 Active schedules:")
            
            for job in self.scheduler.get_jobs():
                next_run = job.next_run_time
                logger.info(f"  • {job.name}: Next run at {next_run}")
            
        except Exception as e:
            logger.error(f"Failed to start trading scheduler: {e}")
            raise
    
    async def stop(self):
        """Stop the scheduler"""
        try:
            self.scheduler.shutdown(wait=True)
            logger.info("🛑 Trading scheduler stopped")
        except Exception as e:
            logger.error(f"Error stopping scheduler: {e}")
    
    def get_job_status(self) -> Dict[str, Any]:
        """Get current status of all scheduled jobs"""
        jobs_status = {}
        
        for job in self.scheduler.get_jobs():
            jobs_status[job.id] = {
                'name': job.name,
                'next_run_time': job.next_run_time.isoformat() if job.next_run_time else None,
                'trigger': str(job.trigger),
                'max_instances': getattr(job, 'max_instances', 1),
                'pending_execution': self.running_jobs.get(
                    StrategyType(job.id.replace('_strategy', '')), False
                ) if job.id.endswith('_strategy') else False
            }
        
        return {
            'scheduler_running': self.scheduler.running,
            'jobs': jobs_status,
            'execution_stats': self.get_execution_stats()
        }

# Global scheduler instance
_trading_scheduler: Optional[TradingScheduler] = None

def get_trading_scheduler() -> TradingScheduler:
    """Get trading scheduler singleton"""
    global _trading_scheduler
    if _trading_scheduler is None:
        _trading_scheduler = TradingScheduler()
    return _trading_scheduler

async def start_trading_scheduler():
    """Start the trading scheduler"""
    scheduler = get_trading_scheduler()
    await scheduler.start()

async def stop_trading_scheduler():
    """Stop the trading scheduler"""
    scheduler = get_trading_scheduler()
    await scheduler.stop()