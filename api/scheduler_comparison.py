"""
API endpoints for comparing old vs optimized scheduler performance
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any, Optional
import logging
from datetime import datetime

from services.scheduler import get_trading_scheduler
from services.optimized_scheduler import get_optimized_scheduler

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/scheduler/status")
async def get_scheduler_status():
    """
    Get status of both schedulers (old and optimized)
    """
    try:
        old_scheduler = get_trading_scheduler()
        new_scheduler = get_optimized_scheduler()
        
        # Get old scheduler jobs
        old_jobs = []
        for job in old_scheduler.scheduler.get_jobs():
            old_jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run": str(job.next_run_time) if job.next_run_time else None
            })
        
        # Get new scheduler jobs
        new_jobs = []
        for job in new_scheduler.scheduler.get_jobs():
            new_jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run": str(job.next_run_time) if job.next_run_time else None
            })
        
        return {
            "old_scheduler": {
                "running": old_scheduler.scheduler.running,
                "jobs": old_jobs,
                "job_count": len(old_jobs)
            },
            "optimized_scheduler": {
                "running": new_scheduler.scheduler.running,
                "jobs": new_jobs,
                "job_count": len(new_jobs)
            }
        }
    except Exception as e:
        logger.error(f"Error getting scheduler status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/scheduler/stats/comparison")
async def compare_scheduler_stats():
    """
    Compare execution statistics between old and optimized schedulers
    """
    try:
        old_scheduler = get_trading_scheduler()
        new_scheduler = get_optimized_scheduler()
        
        # Get execution stats
        old_stats = old_scheduler.execution_stats if hasattr(old_scheduler, 'execution_stats') else {}
        new_stats = new_scheduler.get_execution_stats()
        
        # Calculate improvements
        improvements = {}
        for category in new_stats.keys():
            if category in old_stats:
                old_avg = old_stats[category].get('avg_execution_time', 0)
                new_avg = new_stats[category].get('avg_execution_time', 0)
                
                if old_avg > 0:
                    improvement_pct = ((old_avg - new_avg) / old_avg) * 100
                    improvements[category] = {
                        "old_avg_time": round(old_avg, 2),
                        "new_avg_time": round(new_avg, 2),
                        "improvement_percent": round(improvement_pct, 2)
                    }
        
        return {
            "old_scheduler_stats": old_stats,
            "optimized_scheduler_stats": new_stats,
            "improvements": improvements,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error comparing scheduler stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/scheduler/cache/stats")
async def get_cache_stats():
    """
    Get cache statistics from optimized scheduler
    """
    try:
        scheduler = get_optimized_scheduler()
        cache_stats = scheduler.get_cache_stats()
        
        # Get detailed cache info
        cache_details = []
        for symbol, data in scheduler.symbol_cache.items():
            cache_details.append({
                "symbol": symbol,
                "is_valid": data.is_valid(),
                "last_updated": data.last_updated.isoformat() if data.last_updated else None,
                "candle_count": len(data.historical_data),
                "has_hourly_data": bool(data.indicators.get('hourly_data')),
                "has_minute_data": bool(data.indicators.get('minute_data'))
            })
        
        return {
            "summary": cache_stats,
            "cache_details": cache_details,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/scheduler/cache/clear")
async def clear_cache():
    """
    Clear the cache in optimized scheduler (for testing)
    """
    try:
        scheduler = get_optimized_scheduler()
        symbols_cleared = len(scheduler.symbol_cache)
        scheduler.symbol_cache.clear()
        
        return {
            "success": True,
            "symbols_cleared": symbols_cleared,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/scheduler/test/unified-scan")
async def test_unified_scan(categories: Optional[str] = "day_trading,short_selling"):
    """
    Test unified scan with specific categories
    
    Query params:
    - categories: Comma-separated list of categories (day_trading, short_selling, short_term, long_term)
    
    Example: /scheduler/test/unified-scan?categories=day_trading,short_selling
    """
    try:
        from services.optimized_scheduler import StrategyCategory
        import asyncio
        
        # Parse categories
        category_map = {
            "day_trading": StrategyCategory.DAY_TRADING,
            "short_selling": StrategyCategory.SHORT_SELLING,
            "short_term": StrategyCategory.SHORT_TERM,
            "long_term": StrategyCategory.LONG_TERM
        }
        
        requested_categories = [cat.strip() for cat in categories.split(",")]
        strategy_categories = []
        
        for cat_name in requested_categories:
            if cat_name in category_map:
                strategy_categories.append(category_map[cat_name])
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid category: {cat_name}. Must be one of: {list(category_map.keys())}"
                )
        
        # Run unified scan
        scheduler = get_optimized_scheduler()
        start_time = datetime.now()
        
        await scheduler.execute_unified_scan(strategy_categories)
        
        execution_time = (datetime.now() - start_time).total_seconds()
        
        return {
            "success": True,
            "categories": requested_categories,
            "execution_time_seconds": round(execution_time, 2),
            "cache_stats": scheduler.get_cache_stats(),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error testing unified scan: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/scheduler/api-calls/estimate")
async def estimate_api_calls():
    """
    Estimate daily API calls for both schedulers
    """
    try:
        # Old scheduler estimates
        old_estimates = {
            "day_trading": {
                "symbols": 10,
                "runs_per_day": 12,  # Every 5 min for 1 hour
                "timeframes": 3,
                "calls_per_day": 10 * 12 * 3
            },
            "short_selling": {
                "symbols": 10,
                "runs_per_day": 2,  # Every 30 min
                "timeframes": 3,
                "calls_per_day": 10 * 2 * 3
            },
            "short_term": {
                "symbols": 15,
                "runs_per_day": 5,
                "timeframes": 3,
                "calls_per_day": 15 * 5 * 3
            },
            "long_term": {
                "symbols": 22,
                "runs_per_day": 1,
                "timeframes": 3,
                "calls_per_day": 22 * 1 * 3
            }
        }
        
        old_total = sum(cat['calls_per_day'] for cat in old_estimates.values())
        
        # Optimized scheduler estimates
        # With 60-70% cache hit rate
        cache_hit_rate = 0.65
        
        new_estimates = {
            "frequent_scan": {
                "symbols": 22,  # Unique symbols (not 20)
                "runs_per_day": 12,
                "timeframes": 3,
                "cache_hit_rate": cache_hit_rate,
                "calls_per_day": int(22 * 12 * 3 * (1 - cache_hit_rate))
            },
            "regular_scan": {
                "symbols": 15,
                "runs_per_day": 5,
                "timeframes": 3,
                "cache_hit_rate": cache_hit_rate,
                "calls_per_day": int(15 * 5 * 3 * (1 - cache_hit_rate))
            },
            "daily_scan": {
                "symbols": 22,
                "runs_per_day": 1,
                "timeframes": 3,
                "cache_hit_rate": 0,  # No cache benefit for once-daily
                "calls_per_day": 22 * 1 * 3
            },
            "comprehensive_scan": {
                "symbols": 22,
                "runs_per_day": 2,
                "timeframes": 3,
                "cache_hit_rate": 0.8,  # High cache hit (runs after other scans)
                "calls_per_day": int(22 * 2 * 3 * (1 - 0.8))
            }
        }
        
        new_total = sum(cat['calls_per_day'] for cat in new_estimates.values())
        
        reduction_percent = ((old_total - new_total) / old_total) * 100
        
        return {
            "old_scheduler": {
                "breakdown": old_estimates,
                "total_calls_per_day": old_total
            },
            "optimized_scheduler": {
                "breakdown": new_estimates,
                "total_calls_per_day": new_total,
                "cache_hit_rate": f"{cache_hit_rate * 100}%"
            },
            "savings": {
                "calls_saved_per_day": old_total - new_total,
                "reduction_percent": round(reduction_percent, 2)
            },
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error estimating API calls: {e}")
        raise HTTPException(status_code=500, detail=str(e))
