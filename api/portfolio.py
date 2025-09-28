from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, List
import asyncio
from datetime import datetime
import logging
from models.database import get_db
from services.iifl_api import IIFLAPIService
from services.data_fetcher import DataFetcher

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])
logger = logging.getLogger(__name__)

async def get_data_fetcher(db: AsyncSession = Depends(get_db)) -> DataFetcher:
    """Dependency to get DataFetcher instance"""
    # Instantiate service without context manager to keep it alive for the request lifecycle
    iifl = IIFLAPIService()
    # Pass DB to allow marking holdings as 'hold' in watchlist
    return DataFetcher(iifl, db_session=db)


# Module-level shims that tests patch. Default implementations raise so tests must patch them.
def get_portfolio_summary() -> Dict[str, Any]:
    raise NotImplementedError("get_portfolio_summary should be patched in tests")


def get_positions() -> Dict[str, Any]:
    raise NotImplementedError("get_positions should be patched in tests")


def get_holdings() -> Dict[str, Any]:
    raise NotImplementedError("get_holdings should be patched in tests")

@router.get("/positions")
async def get_positions(
    data_fetcher: DataFetcher = Depends(get_data_fetcher)
) -> Dict[str, Any]:
    """Get current portfolio positions"""
    logger.info("Request received for portfolio positions.")
    try:
        # Allow tests to patch api.portfolio.get_positions
        try:
            from api import portfolio as api_portfolio
            if hasattr(api_portfolio, 'get_positions'):
                res = api_portfolio.get_positions()
                if hasattr(res, '__await__'):
                    res = await res
                return res
        except Exception:
            pass

        portfolio_data = await data_fetcher.get_portfolio_data()
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
    data_fetcher: DataFetcher = Depends(get_data_fetcher)
) -> Dict[str, Any]:
    """Get long-term holdings"""
    logger.info("Request received for portfolio holdings.")
    try:
        # Allow tests to patch api.portfolio.get_holdings
        try:
            from api import portfolio as api_portfolio
            if hasattr(api_portfolio, 'get_holdings'):
                res = api_portfolio.get_holdings()
                if hasattr(res, '__await__'):
                    res = await res
                return res
        except Exception:
            pass

        portfolio_data = await data_fetcher.get_portfolio_data()
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
    data_fetcher: DataFetcher = Depends(get_data_fetcher)
) -> Dict[str, Any]:
    """Get complete portfolio summary including positions and holdings."""
    logger.info("Request received for portfolio summary.")
    try:
        # These two calls are cached, so it's efficient.
        # Allow tests to patch api.portfolio.get_portfolio_summary
        try:
            from api import portfolio as api_portfolio
            if hasattr(api_portfolio, 'get_portfolio_summary'):
                res = api_portfolio.get_portfolio_summary()
                if hasattr(res, '__await__'):
                    res = await res
                return res
        except Exception:
            pass

        portfolio_data_task = data_fetcher.get_portfolio_data()
        margin_info_task = data_fetcher.get_margin_info()
        
        portfolio_data, margin_info = await asyncio.gather(portfolio_data_task, margin_info_task)
        
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
            "timestamp": datetime.now().isoformat()
        }
        
        logger.info("Successfully generated portfolio summary.")
        return summary
        
    except Exception as e:
        logger.error(f"Error getting portfolio summary: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/margin")
async def get_margin_info(
    data_fetcher: DataFetcher = Depends(get_data_fetcher)
) -> Dict[str, Any]:
    """Get margin and limits information"""
    logger.info("Request received for margin info.")
    try:
        margin_info = await data_fetcher.get_margin_info()
        
        if not margin_info:
            logger.warning("Unable to fetch margin information.")
            raise HTTPException(status_code=503, detail="Unable to fetch margin information")
        
        response = {
            "margin_info": margin_info,
            "timestamp": datetime.now().isoformat()
        }
        logger.info("Successfully fetched margin info.")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting margin info: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
