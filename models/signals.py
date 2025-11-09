from sqlalchemy import Column, Integer, String, Float, DateTime, Text, JSON, Enum
from sqlalchemy.sql import func
from .database import Base
import enum
from datetime import datetime, timezone
from typing import Optional, Dict, Any
import urllib.parse
import json

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
    
    @staticmethod
    def _iso_utc(dt: Optional[datetime]) -> Optional[str]:
        """Serialize datetimes as ISO8601 in UTC with Z suffix.

        Assumes naive datetimes are in UTC (server default)."""
        if not dt:
            return None
        # If naive, assume UTC; else convert to UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        # Use isoformat and ensure Z suffix
        iso = dt.isoformat()
        # Python may render +00:00; normalize to Z for client parsing
        return iso.replace("+00:00", "Z")

    def to_dict(self) -> Dict[str, Any]:
        base = {
            "id": self.id,
            "symbol": self.symbol,
            "signal_type": self.signal_type.value,
            "reason": self.reason,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "margin_required": self.margin_required,
            "status": self.status.value,
            "expiry_time": self._iso_utc(self.expiry_time),
            "created_at": self._iso_utc(self.created_at),
            "approved_at": self._iso_utc(self.approved_at),
            "executed_at": self._iso_utc(self.executed_at),
            "extras": self.extras,
            "order_id": self.order_id,
            "quantity": self.quantity,
            "price": self.price
        }

        # Attach Gemini review URL (lightweight client-side validation prompt)
        try:
            prompt_payload = {
                "symbol": self.symbol,
                "type": self.signal_type.value.upper(),
                "entry_price": self.price,
                "stop_loss": self.stop_loss,
                "take_profit": self.take_profit,
                "reason": self.reason,
                "strategy": (self.extras or {}).get("strategy"),
                "confidence": (self.extras or {}).get("confidence"),
                "created_at": base["created_at"],
            }
            prompt_text = (
                "Review trading signal and assess risk. "
                f"Symbol: {prompt_payload['symbol']}. Type: {prompt_payload['type']}. "
                f"Entry: {prompt_payload['entry_price']}. SL: {prompt_payload['stop_loss']}. TP: {prompt_payload['take_profit']}. "
                f"Strategy: {prompt_payload['strategy']}. Confidence: {prompt_payload['confidence']}. "
                "List potential risks, market conditions to watch, and recommend position sizing adjustments."
            )
            encoded = urllib.parse.quote(prompt_text)
            base["gemini_review_url"] = f"https://gemini.google.com/app?prompt={encoded}"
            base["gemini_prompt"] = prompt_text  # Optional transparency for clients
        except Exception:
            base["gemini_review_url"] = None

        return base
