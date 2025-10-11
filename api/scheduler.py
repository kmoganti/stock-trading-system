"""
Scheduler Management API
========================

REST API endpoints for managing the trading strategy scheduler:
- Start/Stop scheduler
- View job status and execution statistics  
- Modify schedule frequencies
- Monitor performance metrics
"""

from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel
from datetime import datetime

from services.scheduler import get_trading_scheduler, StrategyType
from config.settings import get_settings

router = APIRouter(prefix="/scheduler", tags=["scheduler"])

class SchedulerStatusResponse(BaseModel):
    """Response model for scheduler status"""
    scheduler_running: bool
    total_jobs: int
    active_jobs: int
    last_updated: datetime
    jobs: Dict[str, Any]
    execution_stats: Dict[str, Any]

class ScheduleUpdateRequest(BaseModel):
    """Request model for updating schedule frequencies"""
    day_trading_frequency: Optional[int] = None
    short_selling_frequency: Optional[int] = None  
    short_term_frequency: Optional[int] = None
    long_term_frequency: Optional[int] = None

@router.get("/status", response_model=SchedulerStatusResponse)
async def get_scheduler_status():
    """Get current scheduler status and job information"""
    try:
        scheduler = get_trading_scheduler()
        status = scheduler.get_job_status()
        
        return SchedulerStatusResponse(
            scheduler_running=status['scheduler_running'],
            total_jobs=len(status['jobs']),
            active_jobs=len([j for j in status['jobs'].values() if j['pending_execution']]),
            last_updated=datetime.now(),
            jobs=status['jobs'],
            execution_stats=status['execution_stats']
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get scheduler status: {str(e)}")

@router.post("/start")
async def start_scheduler(background_tasks: BackgroundTasks):
    """Start the trading strategy scheduler"""
    try:
        settings = get_settings()
        
        if not settings.enable_scheduler:
            raise HTTPException(
                status_code=400, 
                detail="Scheduler is disabled in configuration. Set ENABLE_SCHEDULER=true to enable."
            )
        
        scheduler = get_trading_scheduler()
        
        # Start scheduler in background
        background_tasks.add_task(scheduler.start)
        
        return {
            "message": "Scheduler start initiated",
            "status": "starting",
            "timestamp": datetime.now()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start scheduler: {str(e)}")

@router.post("/stop")
async def stop_scheduler(background_tasks: BackgroundTasks):
    """Stop the trading strategy scheduler"""
    try:
        scheduler = get_trading_scheduler()
        
        # Stop scheduler in background
        background_tasks.add_task(scheduler.stop)
        
        return {
            "message": "Scheduler stop initiated", 
            "status": "stopping",
            "timestamp": datetime.now()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to stop scheduler: {str(e)}")

@router.get("/stats")
async def get_execution_stats():
    """Get detailed execution statistics for all strategies"""
    try:
        scheduler = get_trading_scheduler()
        stats = scheduler.get_execution_stats()
        
        return {
            "execution_stats": stats,
            "summary": {
                "total_strategies": len(stats),
                "strategies_with_runs": len([s for s in stats.values() if s['total_runs'] > 0]),
                "average_success_rate": sum(s['success_rate'] for s in stats.values()) / len(stats) if stats else 0,
                "last_updated": datetime.now()
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get execution stats: {str(e)}")

@router.post("/execute/{strategy_type}")
async def execute_strategy_manually(
    strategy_type: str, 
    background_tasks: BackgroundTasks
):
    """Manually execute a specific strategy"""
    try:
        # Validate strategy type
        valid_strategies = {
            "day_trading": "execute_day_trading_strategy",
            "short_selling": "execute_short_selling_strategy", 
            "short_term": "execute_short_term_strategy",
            "long_term": "execute_long_term_strategy"
        }
        
        if strategy_type not in valid_strategies:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid strategy type. Valid options: {list(valid_strategies.keys())}"
            )
        
        scheduler = get_trading_scheduler()
        
        # Get the execution method
        execution_method = getattr(scheduler, valid_strategies[strategy_type])
        
        # Execute in background
        background_tasks.add_task(execution_method)
        
        return {
            "message": f"Manual execution of {strategy_type} strategy initiated",
            "strategy": strategy_type,
            "timestamp": datetime.now()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to execute strategy manually: {str(e)}")

@router.get("/next-runs")
async def get_next_run_times():
    """Get next scheduled run times for all strategies"""
    try:
        scheduler = get_trading_scheduler()
        status = scheduler.get_job_status()
        
        next_runs = {}
        for job_id, job_info in status['jobs'].items():
            if job_info['next_run_time']:
                strategy_name = job_id.replace('_strategy', '').replace('_', ' ').title()
                next_runs[strategy_name] = {
                    'next_run_time': job_info['next_run_time'],
                    'trigger': job_info['trigger'],
                    'job_id': job_id
                }
        
        return {
            "next_runs": next_runs,
            "scheduler_running": status['scheduler_running'],
            "current_time": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get next run times: {str(e)}")

@router.get("/performance")
async def get_performance_metrics():
    """Get performance metrics and recommendations"""
    try:
        scheduler = get_trading_scheduler()
        stats = scheduler.get_execution_stats()
        
        # Calculate performance metrics
        performance_metrics = {}
        recommendations = []
        
        for strategy, data in stats.items():
            if data['total_runs'] > 0:
                performance_metrics[strategy] = {
                    'success_rate': data['success_rate'],
                    'avg_execution_time': data['avg_execution_time'],
                    'total_runs': data['total_runs'],
                    'performance_grade': 'A' if data['success_rate'] >= 90 else 'B' if data['success_rate'] >= 75 else 'C'
                }
                
                # Generate recommendations
                if data['success_rate'] < 80:
                    recommendations.append(f"{strategy}: Success rate below 80%, consider reviewing strategy parameters")
                
                if data['avg_execution_time'] > 300:  # 5 minutes
                    recommendations.append(f"{strategy}: Execution time high ({data['avg_execution_time']:.1f}s), consider optimization")
        
        return {
            "performance_metrics": performance_metrics,
            "recommendations": recommendations,
            "overall_health": "Good" if all(m['success_rate'] >= 75 for m in performance_metrics.values()) else "Needs Attention",
            "last_updated": datetime.now()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get performance metrics: {str(e)}")

@router.get("/health")
async def scheduler_health_check():
    """Health check endpoint for scheduler"""
    try:
        scheduler = get_trading_scheduler()
        status = scheduler.get_job_status()
        
        health_status = "healthy"
        issues = []
        
        # Check if scheduler is running
        if not status['scheduler_running']:
            health_status = "unhealthy"
            issues.append("Scheduler is not running")
        
        # Check for failed executions
        stats = status['execution_stats']
        for strategy, data in stats.items():
            if data['total_runs'] > 0 and data['success_rate'] < 50:
                health_status = "degraded"
                issues.append(f"{strategy} has low success rate: {data['success_rate']:.1f}%")
        
        return {
            "status": health_status,
            "scheduler_running": status['scheduler_running'],
            "total_jobs": len(status['jobs']),
            "issues": issues,
            "timestamp": datetime.now()
        }
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now()
        }