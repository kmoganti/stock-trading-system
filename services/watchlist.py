from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from models.watchlist import Watchlist
import logging

logger = logging.getLogger(__name__)

class WatchlistService:
    """Service for managing watchlist items"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_watchlist(self, active_only: bool = True) -> List[str]:
        """Get all watchlist symbols"""
        query = select(Watchlist.symbol).where(Watchlist.is_active == True) if active_only else select(Watchlist.symbol)
        result = await self.db.execute(query)
        return [row[0] for row in result.all()]
    
    async def add_symbols(self, symbols: List[str]) -> None:
        """Add symbols to watchlist"""
        existing = set(await self.get_watchlist(active_only=False))
        new_symbols = [s.upper() for s in symbols if s.upper() not in existing]
        
        for symbol in new_symbols:
            self.db.add(Watchlist(symbol=symbol))
        
        if new_symbols:
            await self.db.commit()
            logger.info(f"Added {len(new_symbols)} symbols to watchlist")
    
    async def remove_symbols(self, symbols: List[str]) -> None:
        """Remove symbols from watchlist (soft delete)"""
        symbols = [s.upper() for s in symbols]
        stmt = (
            update(Watchlist)
            .where(Watchlist.symbol.in_(symbols))
            .values(is_active=False)
        )
        await self.db.execute(stmt)
        await self.db.commit()
        logger.info(f"Removed {len(symbols)} symbols from watchlist")
