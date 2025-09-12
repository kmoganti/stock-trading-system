from sqlalchemy import Column, Integer, String, DateTime, Boolean
from .database import Base
from datetime import datetime

class Watchlist(Base):
    """Model for storing watchlist items"""
    __tablename__ = "watchlist"
    
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(50), nullable=False, index=True)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<Watchlist {self.symbol} ({'active' if self.is_active else 'inactive'})>"
