from sqlalchemy import Column, Integer, Float, Date, DateTime
from sqlalchemy.sql import func
from .database import Base
from typing import Dict, Any, Optional

from sqlalchemy.orm import declared_attr

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
    # Additional commonly referenced fields in tests/consumers
    fees = Column(Float, nullable=False, default=0.0)
    
    # Portfolio metrics
    starting_equity = Column(Float, nullable=True)
    ending_equity = Column(Float, nullable=True)
    max_drawdown = Column(Float, nullable=False, default=0.0)
    
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<PnLReport(date={self.date}, daily_pnl={self.daily_pnl}, cumulative_pnl={self.cumulative_pnl})>"
    
    def __init__(self, **kwargs):
        # Accept alias fields used in tests and map to our canonical schema
        # - trades_count -> total_trades
        # - total_pnl is not stored; it's computed via property
        # - win_rate provided will be cached for property access
        self._win_rate_override: Optional[float] = None
        if 'total_pnl' in kwargs:
            # Ignore provided total_pnl; it's derived from realized/unrealized/fees
            kwargs.pop('total_pnl', None)
        if 'trades_count' in kwargs:
            kwargs['total_trades'] = kwargs.pop('trades_count') or 0
        if 'win_rate' in kwargs:
            try:
                self._win_rate_override = float(kwargs.pop('win_rate'))
            except Exception:
                self._win_rate_override = None
        super().__init__(**kwargs)  # type: ignore

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
            "fees": self.fees,
            "starting_equity": self.starting_equity,
            "ending_equity": self.ending_equity,
            "max_drawdown": self.max_drawdown,
            "win_rate": self.win_rate,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

    # Alias/computed properties expected by tests
    @property
    def total_pnl(self) -> float:
        # Tests expect total_pnl to be realized + unrealized (fees are reported separately)
        try:
            return float(self.realized_pnl or 0.0) + float(self.unrealized_pnl or 0.0)
        except Exception:
            return (self.realized_pnl or 0.0) + (self.unrealized_pnl or 0.0)

    @property
    def trades_count(self) -> int:
        return int(self.total_trades or 0)

    @property
    def win_rate(self) -> float:
        if self._win_rate_override is not None:
            return self._win_rate_override
        if (self.total_trades or 0) > 0:
            return float(self.winning_trades or 0) / float(self.total_trades)
        return 0.0
