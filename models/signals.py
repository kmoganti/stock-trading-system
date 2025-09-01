from sqlalchemy import Column, Integer, String, Float, DateTime, Text, JSON, Enum
from sqlalchemy.sql import func
from .database import Base
import enum
from datetime import datetime
from typing import Optional, Dict, Any

class SignalType(str, enum.Enum):
    BUY = "buy"
    SELL = "sell"
    EXIT = "exit"

class SignalStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"
    EXPIRED = "expired"
    FAILED = "failed"

class Signal(Base):
    __tablename__ = "signals"
    
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    signal_type = Column(Enum(SignalType), nullable=False)
    reason = Column(Text, nullable=True)
    stop_loss = Column(Float, nullable=True)
    take_profit = Column(Float, nullable=True)
    margin_required = Column(Float, nullable=False, default=0.0)
    status = Column(Enum(SignalStatus), nullable=False, default=SignalStatus.PENDING)
    expiry_time = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False, default=func.now())
    approved_at = Column(DateTime, nullable=True)
    executed_at = Column(DateTime, nullable=True)
    extras = Column(JSON, nullable=True)
    
    # Additional fields for order tracking
    order_id = Column(String(50), nullable=True)
    quantity = Column(Integer, nullable=True)
    price = Column(Float, nullable=True)
    
    def __repr__(self):
        return f"<Signal(id={self.id}, symbol={self.symbol}, type={self.signal_type}, status={self.status})>"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "symbol": self.symbol,
            "signal_type": self.signal_type.value,
            "reason": self.reason,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "margin_required": self.margin_required,
            "status": self.status.value,
            "expiry_time": self.expiry_time.isoformat() if self.expiry_time else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "executed_at": self.executed_at.isoformat() if self.executed_at else None,
            "extras": self.extras,
            "order_id": self.order_id,
            "quantity": self.quantity,
            "price": self.price
        }
