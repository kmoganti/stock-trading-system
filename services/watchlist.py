from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert 
from models.watchlist import Watchlist, WatchlistCategory
import logging
import csv
from pathlib import Path

logger = logging.getLogger(__name__)

def _load_symbols_from_csv(file_path: str, symbol_column: str) -> List[str]:
    """Loads a list of symbols from a CSV file, assuming it has a header."""
    symbols = []
    # Assumes the app runs from the project root (e.g., 'stock-trading-system/')
    full_path = Path(file_path)
    if not full_path.is_file():
        logger.error(f"CSV file not found at path: {full_path.resolve()}")
        return []
    
    try:
        with open(full_path, mode='r', encoding='utf-8-sig') as infile:
            reader = csv.DictReader(infile)
            for row in reader:
                symbol = row.get(symbol_column)
                if symbol:
                    symbols.append(symbol.strip().upper())
        logger.info(f"Loaded {len(symbols)} symbols from {file_path}")
        return symbols
    except Exception as e:
        logger.error(f"Error reading CSV file {file_path}: {e}")
        return []

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

    async def refresh_index_symbols(self, index_symbols: List[str], holding_symbols: List[str], default_category: str) -> int:
        """
        Efficiently adds or updates a list of index symbols in the watchlist.
        - Symbols present in `holding_symbols` are assigned the 'hold' category.
        - All other symbols are assigned the `default_category`.
        - All symbols are marked as active.
        """
        if not index_symbols:
            return 0

        holding_symbols_set = {s.upper() for s in holding_symbols}
        values_to_upsert = []

        for symbol in index_symbols:
            category = "hold" if symbol in holding_symbols_set else default_category
            values_to_upsert.append({
                "symbol": symbol,
                "category": category,
                "is_active": True
            })

        # Use PostgreSQL's "ON CONFLICT" for an efficient "upsert"
        stmt = pg_insert(Watchlist).values(values_to_upsert)
        update_stmt = stmt.on_conflict_do_update(
            index_elements=['symbol'],
            set_={'category': stmt.excluded.category, 'is_active': stmt.excluded.is_active}
        )
        await self.db.execute(update_stmt)
        await self.db.commit()
        logger.info(f"Upserted {len(values_to_upsert)} symbols into the watchlist.")
        return len(values_to_upsert)
