from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, List
import asyncio
from datetime import datetime
import logging
from models.database import get_db
from services.iifl_api import IIFLAPIService
from services.data_fetcher import DataFetcher
from services.iifl_api import IIFLAPIService

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])
logger = logging.getLogger(__name__)

async def get_data_fetcher(db: AsyncSession = Depends(get_db)) -> DataFetcher:
    """Dependency to get DataFetcher instance"""
    # Instantiate service without context manager to keep it alive for the request lifecycle
    iifl = IIFLAPIService()
    # Pass DB to allow marking holdings as 'hold' in watchlist
    return DataFetcher(iifl, db_session=db)

@router.get("/positions")
async def get_positions(
    data_fetcher: DataFetcher = Depends(get_data_fetcher),
    force: bool = False,
) -> Dict[str, Any]:
    """Get current portfolio positions"""
    logger.info("Request received for portfolio positions.")
    try:
        portfolio_data = await data_fetcher.get_portfolio_data(force_refresh=force)
        response = {
            "positions": portfolio_data.get("positions", []),
            "total_pnl": portfolio_data.get("total_pnl", 0.0),
            "timestamp": datetime.now().isoformat()
        }
        logger.info(f"Returning {len(response['positions'])} positions.")
        return response
        
    except Exception as e:
        logger.error(f"Error getting positions: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/holdings")
async def get_holdings(
    data_fetcher: DataFetcher = Depends(get_data_fetcher),
    force: bool = False,
) -> Dict[str, Any]:
    """Get long-term holdings"""
    logger.info("Request received for portfolio holdings.")
    try:
        portfolio_data = await data_fetcher.get_portfolio_data(force_refresh=force)
        response = {
            "holdings": portfolio_data.get("holdings", []),
            "timestamp": datetime.now().isoformat()
        }
        logger.info(f"Returning {len(response['holdings'])} holdings.")
        return response
        
    except Exception as e:
        logger.error(f"Error getting holdings: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/summary")
async def get_portfolio_summary(
    data_fetcher: DataFetcher = Depends(get_data_fetcher),
    force: bool = False,
) -> Dict[str, Any]:
    """Get complete portfolio summary including positions and holdings."""
    logger.info("Request received for portfolio summary.")
    
    try:
        # Use asyncio.wait_for to add timeout protection
        async def fetch_with_timeout():
            results = await asyncio.gather(
                data_fetcher.get_portfolio_data(force_refresh=force),
                data_fetcher.get_margin_info(force_refresh=force),
                return_exceptions=True
            )
            return results
        
        # 8 second timeout for IIFL API calls
        results = await asyncio.wait_for(fetch_with_timeout(), timeout=8.0)
        
        # Handle potential exceptions from IIFL API
        portfolio_data = results[0] if not isinstance(results[0], Exception) else {}
        margin_info = results[1] if not isinstance(results[1], Exception) else None
        
        if isinstance(results[0], Exception):
            logger.warning(f"Failed to get portfolio data: {results[0]}")
        if isinstance(results[1], Exception):
            logger.warning(f"Failed to get margin info: {results[1]}")
        
        available_cash = margin_info.get("availableMargin", 0) if margin_info else 0
        total_equity = portfolio_data.get("total_value", 0.0) + float(available_cash or 0)

        summary = {
            "total_equity": total_equity,
            "total_value": portfolio_data.get("total_value", 0.0),
            "total_invested": portfolio_data.get("total_invested", 0.0),
            "total_pnl": portfolio_data.get("total_pnl", 0.0),
            "total_pnl_percent": portfolio_data.get("total_pnl_percent", 0.0),
            "available_margin": available_cash,
            "used_margin": margin_info.get("usedMargin", 0) if margin_info else 0,
            "positions": portfolio_data.get("positions", []),
            "holdings": portfolio_data.get("holdings", []),
            "holdings_count": len(portfolio_data.get("holdings", [])),
            "positions_count": len(portfolio_data.get("positions", [])),
            "timestamp": datetime.now().isoformat(),
            "api_available": not isinstance(results[0], Exception)
        }
        
        logger.info("Successfully generated portfolio summary.")
        return summary
        
    except asyncio.TimeoutError:
        logger.error("Portfolio API timeout - IIFL API took too long")
        return {
            "total_equity": 0.0,
            "total_value": 0.0,
            "total_invested": 0.0,
            "total_pnl": 0.0,
            "total_pnl_percent": 0.0,
            "available_margin": 0,
            "used_margin": 0,
            "positions": [],
            "holdings": [],
            "holdings_count": 0,
            "positions_count": 0,
            "timestamp": datetime.now().isoformat(),
            "api_available": False,
            "error": "Timeout fetching portfolio data"
        }
    # except Exception as e:
    #     logger.error(f"Error getting portfolio summary: {str(e)}", exc_info=True)
    #     return {
    #         "total_equity": 0.0,
    #         "total_value": 0.0,
    #         "total_invested": 0.0,
    #         "total_pnl": 0.0,
    #         "total_pnl_percent": 0.0,
    #         "available_margin": 0,
    #         "used_margin": 0,
    #         "positions": [],
    #         "holdings": [],
    #         "holdings_count": 0,
    #         "positions_count": 0,
    #         "timestamp": datetime.now().isoformat(),
    #         "api_available": False,
    #         "error": str(e)
    #     }

@router.get("/margin")
async def get_margin_info(
    data_fetcher: DataFetcher = Depends(get_data_fetcher)
) -> Dict[str, Any]:
    """Get margin and limits information"""
    logger.info("Request received for margin info.")
    try:
        # Add timeout protection
        margin_info = await asyncio.wait_for(
            data_fetcher.get_margin_info(),
            timeout=8.0
        )
        
        if not margin_info:
            logger.warning("Unable to fetch margin information.")
            raise HTTPException(status_code=503, detail="Unable to fetch margin information")
        
        response = {
            "margin_info": margin_info,
            "timestamp": datetime.now().isoformat()
        }
        logger.info("Successfully fetched margin info.")
        return response
        
    except asyncio.TimeoutError:
        logger.error("Margin API timeout - IIFL API took too long")
        raise HTTPException(status_code=504, detail="Timeout fetching margin information")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting margin info: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/holdings/raw")
async def get_holdings_raw(force: bool = False) -> Dict[str, Any]:
    """Return raw holdings payload from broker for debugging.

    This endpoint is for diagnostics: it bypasses DataFetcher processing and returns
    a compact view of the provider response with counts and a small preview.
    """
    try:
        service = IIFLAPIService()
        if force:
            # Best-effort clear redis caches so we re-fetch fresh
            try:
                from services.redis_service import get_redis_service, CacheKeys  # type: ignore
                redis = await get_redis_service()
                if redis:
                    try:
                        await redis.delete(CacheKeys.API_HOLDINGS)
                    except Exception:
                        pass
            except Exception:
                pass
        raw = await service.get_holdings()
        count = 0
        preview = None
        status = None
        message = None
        if isinstance(raw, dict):
            status = raw.get("status") or raw.get("stat")
            message = raw.get("message") or raw.get("emsg")
            container = None
            for k in ("result", "resultData", "data"):
                v = raw.get(k)
                if isinstance(v, list):
                    container = v
                    break
            if isinstance(container, list):
                count = len(container)
                if container:
                    item = container[0]
                    if isinstance(item, dict):
                        preview = {"keys": list(item.keys())[:20]}
                    else:
                        preview = {"type": str(type(item)), "repr": str(item)[:200]}
        return {
            "status": status,
            "message": message,
            "count": count,
            "preview": preview,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error getting raw holdings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
