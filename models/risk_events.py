from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, Enum
from sqlalchemy.sql import func
from .database import Base
import enum
from typing import Dict, Any, Optional

class RiskEventType(str, enum.Enum):
    DAILY_LOSS_HALT = "daily_loss_halt"
    DRAWDOWN_HALT = "drawdown_halt"
    MARGIN_INSUFFICIENT = "margin_insufficient"
    POSITION_LIMIT_EXCEEDED = "position_limit_exceeded"
    API_ERROR = "api_error"
    SYSTEM_ERROR = "system_error"
    MANUAL_HALT = "manual_halt"
    STRATEGY_ERROR = "strategy_error"

class RiskEvent(Base):
    __tablename__ = "risk_events"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, nullable=False, default=func.now(), index=True)
    event_type = Column(Enum(RiskEventType), nullable=False, index=True)
    message = Column(Text, nullable=False)
    meta = Column(JSON, nullable=True)
    
    # Additional context
    symbol = Column(String(20), nullable=True)
    severity = Column(String(10), nullable=False, default="medium")  # low, medium, high, critical
    resolved = Column(String(1), nullable=False, default="N")  # Y/N
    resolved_at = Column(DateTime, nullable=True)
    
    def __repr__(self):
        return f"<RiskEvent(id={self.id}, type={self.event_type}, timestamp={self.timestamp})>"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "event_type": self.event_type.value,
            "message": self.message,
            "meta": self.meta,
            "symbol": self.symbol,
            "severity": self.severity,
            "resolved": self.resolved == "Y",
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None
        }
