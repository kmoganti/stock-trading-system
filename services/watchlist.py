from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from models.watchlist import Watchlist, WatchlistCategory
import logging

logger = logging.getLogger(__name__)

class WatchlistService:
    """Service for managing watchlist items"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_watchlist(self, active_only: bool = True, category: Optional[str] = None) -> List[str]:
        """Get watchlist symbols, optionally filtered by category"""
        base_query = select(Watchlist.symbol)
        if active_only:
            base_query = base_query.where(Watchlist.is_active == True)
        if category:
            base_query = base_query.where(Watchlist.category == category)
        query = base_query
        result = await self.db.execute(query)
        return [row[0] for row in result.all()]
    
    async def add_symbols(self, symbols: List[str], category: Optional[str] = None) -> None:
        """Add symbols to watchlist for a given category"""
        category_value = category or WatchlistCategory.SHORT_TERM.value
        existing = set(await self.get_watchlist(active_only=False, category=category_value))
        new_symbols = [s.upper() for s in symbols if s and s.upper() not in existing]
        
        for symbol in new_symbols:
            self.db.add(Watchlist(symbol=symbol, category=category_value))
        
        if new_symbols:
            await self.db.commit()
            logger.info(f"Added {len(new_symbols)} symbols to watchlist [{category_value}]")
    
    async def remove_symbols(self, symbols: List[str], category: Optional[str] = None) -> None:
        """Remove symbols from watchlist (soft delete), optionally by category"""
        symbols = [s.upper() for s in symbols if s]
        stmt = update(Watchlist).where(Watchlist.symbol.in_(symbols))
        if category:
            stmt = stmt.where(Watchlist.category == category)
        stmt = stmt.values(is_active=False)
        await self.db.execute(stmt)
        await self.db.commit()
        logger.info(f"Removed {len(symbols)} symbols from watchlist{f' [{category}]' if category else ''}")

    async def set_category(self, symbol: str, category: str) -> None:
        """Move a symbol to a different category and activate it"""
        symbol = symbol.upper()
        stmt = (
            update(Watchlist)
            .where(Watchlist.symbol == symbol)
            .values(category=category, is_active=True)
        )
        await self.db.execute(stmt)
        await self.db.commit()
        logger.info(f"Set category for {symbol} to {category}")
