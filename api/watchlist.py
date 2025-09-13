from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from models.database import get_db
from services.watchlist import WatchlistService, NIFTY_100_SYMBOLS
from pydantic import BaseModel
import logging

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])
logger = logging.getLogger(__name__)

class WatchlistUpdate(BaseModel):
    symbols: List[str]
    category: Optional[str] = None

@router.get("", response_model=List[str])
async def get_watchlist(
    active_only: bool = True,
    category: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Get all symbols in the watchlist"""
    try:
        service = WatchlistService(db)
        return await service.get_watchlist(active_only=active_only, category=category)
    except Exception as e:
        logger.error(f"Error getting watchlist: {str(e)}")
        raise HTTPException(status_code=500, detail="Error retrieving watchlist")

@router.post("")
async def add_to_watchlist(
    update: WatchlistUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Add symbols to the watchlist"""
    try:
        if not update.symbols:
            raise HTTPException(status_code=400, detail="No symbols provided")
            
        service = WatchlistService(db)
        await service.add_symbols(update.symbols, category=update.category)
        return {"message": f"Successfully added {len(update.symbols)} symbols to watchlist", "category": update.category or "short_term"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding to watchlist: {str(e)}")
        raise HTTPException(status_code=500, detail="Error updating watchlist")

@router.delete("")
async def remove_from_watchlist(
    update: WatchlistUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Remove symbols from the watchlist"""
    try:
        if not update.symbols:
            raise HTTPException(status_code=400, detail="No symbols provided")
            
        service = WatchlistService(db)
        await service.remove_symbols(update.symbols, category=update.category)
        return {"message": f"Successfully removed {len(update.symbols)} symbols from watchlist", "category": update.category}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing from watchlist: {str(e)}")
        raise HTTPException(status_code=500, detail="Error updating watchlist")

@router.put("/category")
async def change_symbol_category(
    symbol: str,
    category: str,
    db: AsyncSession = Depends(get_db)
):
    """Change the category of a symbol (and activate it)."""
    try:
        if not symbol or not category:
            raise HTTPException(status_code=400, detail="Symbol and category are required")
        if category not in {"long_term", "short_term", "day_trading"}:
            raise HTTPException(status_code=400, detail="Invalid category")
        service = WatchlistService(db)
        await service.set_category(symbol, category)
        return {"message": f"Updated {symbol.upper()} to category {category}"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error changing symbol category: {str(e)}")
        raise HTTPException(status_code=500, detail="Error updating category")

@router.post("/refresh/nifty100")
async def refresh_nifty100_watchlist(
    category: str = "day_trading",
    db: AsyncSession = Depends(get_db)
):
    """Populate the watchlist with Nifty 100 symbols for intraday/day trading."""
    try:
        if category not in {"long_term", "short_term", "day_trading"}:
            raise HTTPException(status_code=400, detail="Invalid category")
        service = WatchlistService(db)
        await service.add_symbols(NIFTY_100_SYMBOLS, category=category)
        return {"message": f"Nifty 100 symbols added to {category}", "count": len(NIFTY_100_SYMBOLS)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error refreshing Nifty 100 watchlist: {str(e)}")
        raise HTTPException(status_code=500, detail="Error refreshing watchlist")

@router.post("/refresh/csv")
async def refresh_watchlist_from_csv(
    file_path: str = "data/ind_nifty100list.csv",
    category: Optional[str] = None,
    deactivate_missing: bool = True,
    db: AsyncSession = Depends(get_db)
):
    """Refresh the watchlist from a CSV file placed under data/.

    - file_path: path to CSV file (default: data/ind_nifty100list.csv)
    - category: override category for all symbols (default: short_term)
    - deactivate_missing: deactivates symbols in the category not present in CSV
    """
    try:
        service = WatchlistService(db)
        result = await service.refresh_from_csv(
            file_path=file_path,
            category=category,
            deactivate_missing=deactivate_missing,
        )
        return {"message": "Watchlist refreshed from CSV", **result}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error refreshing watchlist from CSV: {str(e)}")
        raise HTTPException(status_code=500, detail="Error refreshing watchlist from CSV")
