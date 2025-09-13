from typing import List, Optional, Set
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert 
from models.watchlist import Watchlist, WatchlistCategory
import logging
<<<<<<< HEAD
import csv
from pathlib import Path
=======
from pathlib import Path
import csv
>>>>>>> cursor/document-code-configurations-and-db-entries-05e7

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

<<<<<<< HEAD
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
=======
    def _load_symbols_from_csv(self, file_path: str) -> List[str]:
        """Load symbols from a CSV file. Accepts header with 'Symbol'/'symbol' or first column.

        Returns a unique uppercased list.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"CSV file not found: {file_path}")

        symbols: List[str] = []
        with path.open("r", newline="", encoding="utf-8") as f:
            # Try dict reader first
            try:
                reader = csv.DictReader(f)
                if reader.fieldnames:
                    # Normalize field names
                    lower_fields = {name.lower(): name for name in reader.fieldnames}
                    symbol_key = lower_fields.get("symbol") or lower_fields.get("ticker") or lower_fields.get("security")
                    if symbol_key:
                        for row in reader:
                            val = (row.get(symbol_key) or "").strip()
                            if val:
                                symbols.append(val)
                    else:
                        # Fallback to first column behavior below
                        raise ValueError("No symbol-like column found in CSV header")
                else:
                    raise ValueError("Missing header")
            except Exception:
                # Rewind and use simple reader, take first column
                f.seek(0)
                simple_reader = csv.reader(f)
                for row in simple_reader:
                    if not row:
                        continue
                    val = (row[0] or "").strip()
                    if val and val.lower() != "symbol":  # skip header-like first row
                        symbols.append(val)

        # Deduplicate and uppercase
        seen: Set[str] = set()
        unique_symbols: List[str] = []
        for s in symbols:
            u = s.upper()
            if u and u not in seen:
                seen.add(u)
                unique_symbols.append(u)
        return unique_symbols

    async def refresh_from_csv(
        self,
        file_path: str = "data/ind_nifty100list.csv",
        category: Optional[str] = None,
        deactivate_missing: bool = True,
    ) -> dict:
        """Refresh watchlist from a CSV file.

        - Adds any new symbols
        - Activates existing symbols present in the file
        - Optionally deactivates symbols for the category that are not in the file
        """
        symbols = self._load_symbols_from_csv(file_path)
        target_category = category or WatchlistCategory.SHORT_TERM.value

        # Current symbols in this category (active or not)
        current_query = select(Watchlist.symbol, Watchlist.is_active).where(Watchlist.category == target_category)
        result = await self.db.execute(current_query)
        current_rows = result.all()
        current_symbols_set: Set[str] = {row[0].upper() for row in current_rows}

        to_add = [s for s in symbols if s not in current_symbols_set]
        to_activate = [s for s in symbols if s in current_symbols_set]

        # Add new symbols
        for sym in to_add:
            self.db.add(Watchlist(symbol=sym, category=target_category, is_active=True))

        # Activate existing
        if to_activate:
            stmt = (
                update(Watchlist)
                .where(Watchlist.symbol.in_(to_activate), Watchlist.category == target_category)
                .values(is_active=True)
            )
            await self.db.execute(stmt)

        # Deactivate missing ones in this category
        deactivated_count = 0
        if deactivate_missing:
            missing = list(current_symbols_set.difference(symbols))
            if missing:
                stmt = (
                    update(Watchlist)
                    .where(Watchlist.symbol.in_(missing), Watchlist.category == target_category)
                    .values(is_active=False)
                )
                result = await self.db.execute(stmt)
                # rowcount may be None on some dialects; ignore if so
                deactivated_count = getattr(result, "rowcount", 0) or 0

        await self.db.commit()

        added_count = len(to_add)
        activated_count = len(to_activate)
        logger.info(
            f"Refreshed watchlist from {file_path}: added={added_count}, activated={activated_count}, deactivated={deactivated_count} in category={target_category}"
        )
        return {
            "added": added_count,
            "activated": activated_count,
            "deactivated": deactivated_count,
            "category": target_category,
            "total": len(symbols),
        }

    async def mark_holdings_as_hold(self, symbols: List[str]) -> int:
        """Mark given symbols as 'hold' in watchlist, upserting as needed.

        Uses category='hold' to denote holding status without requiring schema changes.
        Returns number of symbols affected.
        """
        if not symbols:
            return 0
        upper = [s.upper() for s in symbols if s]
        if not upper:
            return 0

        # Find existing entries for these symbols
        existing_query = select(Watchlist.symbol).where(Watchlist.symbol.in_(upper))
        result = await self.db.execute(existing_query)
        existing_set: Set[str] = {row[0].upper() for row in result.all()}

        # Update existing to category='hold' and is_active=True
        if existing_set:
            stmt = (
                update(Watchlist)
                .where(Watchlist.symbol.in_(list(existing_set)))
                .values(category="hold", is_active=True)
            )
            await self.db.execute(stmt)

        # Insert missing
        to_insert = [s for s in upper if s not in existing_set]
        for sym in to_insert:
            self.db.add(Watchlist(symbol=sym, category="hold", is_active=True))

        await self.db.commit()
        affected = len(existing_set) + len(to_insert)
        logger.info(f"Marked {affected} holdings as 'hold' in watchlist")
        return affected
>>>>>>> cursor/document-code-configurations-and-db-entries-05e7
