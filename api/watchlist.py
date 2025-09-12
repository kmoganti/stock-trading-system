from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from models.database import get_db
from services.watchlist import WatchlistService
from pydantic import BaseModel
import logging

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])
logger = logging.getLogger(__name__)

class WatchlistUpdate(BaseModel):
    symbols: List[str]

@router.get("", response_model=List[str])
async def get_watchlist(
    active_only: bool = True,
    db: AsyncSession = Depends(get_db)
):
    """Get all symbols in the watchlist"""
    try:
        service = WatchlistService(db)
        return await service.get_watchlist(active_only=active_only)
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
        await service.add_symbols(update.symbols)
        return {"message": f"Successfully added {len(update.symbols)} symbols to watchlist"}
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
        await service.remove_symbols(update.symbols)
        return {"message": f"Successfully removed {len(update.symbols)} symbols from watchlist"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing from watchlist: {str(e)}")
        raise HTTPException(status_code=500, detail="Error updating watchlist")
