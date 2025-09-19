from sqlalchemy import Column, Integer, String, DateTime, Boolean
from .database import Base
from datetime import datetime
from enum import Enum as PyEnum

class WatchlistCategory(PyEnum):
    """Category types for watchlist symbols"""
    LONG_TERM = "long_term"
    SHORT_TERM = "short_term"
    DAY_TRADING = "day_trading"
    HOLD = "hold"


class Watchlist(Base):
    """Model for storing watchlist items"""
    __tablename__ = "watchlist"
    
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(50), nullable=False, index=True)
    category = Column(String(20), nullable=False, index=True, default=WatchlistCategory.SHORT_TERM.value)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<Watchlist {self.symbol} [{self.category}] ({'active' if self.is_active else 'inactive'})>"
