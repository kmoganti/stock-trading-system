from sqlalchemy import Column, Integer, Float, Date, DateTime
from sqlalchemy.sql import func
from .database import Base
from typing import Dict, Any

class PnLReport(Base):
    __tablename__ = "pnl_reports"
    
    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, nullable=False, unique=True, index=True)
    daily_pnl = Column(Float, nullable=False, default=0.0)
    cumulative_pnl = Column(Float, nullable=False, default=0.0)
    drawdown = Column(Float, nullable=False, default=0.0)
    
    # Additional metrics
    realized_pnl = Column(Float, nullable=False, default=0.0)
    unrealized_pnl = Column(Float, nullable=False, default=0.0)
    total_trades = Column(Integer, nullable=False, default=0)
    winning_trades = Column(Integer, nullable=False, default=0)
    losing_trades = Column(Integer, nullable=False, default=0)
    
    # Portfolio metrics
    starting_equity = Column(Float, nullable=True)
    ending_equity = Column(Float, nullable=True)
    max_drawdown = Column(Float, nullable=False, default=0.0)
    
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<PnLReport(date={self.date}, daily_pnl={self.daily_pnl}, cumulative_pnl={self.cumulative_pnl})>"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "date": self.date.isoformat() if self.date else None,
            "daily_pnl": self.daily_pnl,
            "cumulative_pnl": self.cumulative_pnl,
            "drawdown": self.drawdown,
            "realized_pnl": self.realized_pnl,
            "unrealized_pnl": self.unrealized_pnl,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "starting_equity": self.starting_equity,
            "ending_equity": self.ending_equity,
            "max_drawdown": self.max_drawdown,
            "win_rate": self.winning_trades / self.total_trades if self.total_trades > 0 else 0.0,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
