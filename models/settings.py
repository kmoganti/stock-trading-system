from sqlalchemy import Column, String, Text, DateTime
from sqlalchemy.sql import func
from .database import Base
from typing import Dict, Any, Union

class Setting(Base):
    __tablename__ = "settings"
    
    key = Column(String(100), primary_key=True, index=True)
    value = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<Setting(key={self.key}, value={self.value})>"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "value": self.value,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
    def get_typed_value(self) -> Union[str, int, float, bool]:
        """Convert string value to appropriate type"""
        value = self.value.lower()
        
        # Boolean conversion
        if value in ('true', 'false'):
            return value == 'true'
        
        # Integer conversion
        try:
            if '.' not in self.value:
                return int(self.value)
        except ValueError:
            pass
        
        # Float conversion
        try:
            return float(self.value)
        except ValueError:
            pass
        
        # Return as string
        return self.value


from dataclasses import dataclass


@dataclass
class Settings:
    """Lightweight settings object used by tests and simple parts of the app.

    This is intentionally minimal and independent from the SQLAlchemy `Setting`
    model above. It provides defaults used in the test-suite.
    """
    auto_trade: bool = False
    risk_per_trade: float = 0.02
    max_positions: int = 10
    max_daily_loss: float = 0.05
    signal_timeout: int = 300
    min_price: float = 10.0
    min_liquidity: int = 100000
    environment: str = "development"
