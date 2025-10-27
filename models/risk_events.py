from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, Enum, Float, Boolean
from sqlalchemy.sql import func
from .database import Base
import enum
from typing import Dict, Any, Optional

class RiskEventType(str, enum.Enum):
    # Existing events
    DAILY_LOSS_HALT = "daily_loss_halt"
    DAILY_LOSS_LIMIT_EXCEEDED = "daily_loss_limit_exceeded"
    DRAWDOWN_HALT = "drawdown_halt"
    MARGIN_INSUFFICIENT = "margin_insufficient"
    MARGIN_CALL = "margin_call"
    POSITION_LIMIT_EXCEEDED = "position_limit_exceeded"
    STOP_LOSS_TRIGGERED = "stop_loss_triggered"
    API_ERROR = "api_error"
    SYSTEM_ERROR = "system_error"
    MANUAL_HALT = "manual_halt"
    STRATEGY_ERROR = "strategy_error"
    
    # New real-time monitoring events
    STOP_LOSS_HIT = "stop_loss_hit"
    DAILY_LOSS_LIMIT = "daily_loss_limit"
    POSITION_SIZE_EXCEEDED = "position_size_exceeded"
    MAX_POSITIONS_EXCEEDED = "max_positions_exceeded"
    MARGIN_SHORTAGE = "margin_shortage"
    API_FAILURE = "api_failure"
    UNUSUAL_MARKET_MOVEMENT = "unusual_market_movement"
    EMERGENCY_HALT = "emergency_halt"

class RiskSeverity(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class RiskEvent(Base):
    __tablename__ = "risk_events"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, nullable=False, default=func.now(), index=True)
    event_type = Column(Enum(RiskEventType), nullable=False, index=True)
    message = Column(Text, nullable=False)
    meta = Column(JSON, nullable=True)
    
    # Additional context
    symbol = Column(String(20), nullable=True, index=True)
    severity = Column(Enum(RiskSeverity), nullable=False, default=RiskSeverity.MEDIUM, index=True)
    resolved = Column(Boolean, nullable=False, default=False, index=True)
    resolved_at = Column(DateTime, nullable=True)
    
    # Enhanced fields for real-time monitoring
    portfolio_value = Column(Float, nullable=True)
    daily_pnl = Column(Float, nullable=True)
    position_pnl = Column(Float, nullable=True)
    risk_amount = Column(Float, nullable=True)
    
    # Response tracking
    action_taken = Column(String(200), nullable=True)
    alert_sent = Column(Boolean, default=False, nullable=False)
    alert_sent_at = Column(DateTime, nullable=True)
    
    def __repr__(self):
        return f"<RiskEvent(id={self.id}, type={self.event_type}, timestamp={self.timestamp})>"

    def __init__(self, **kwargs):
        # Accept 'description' alias from tests, map to message
        if 'description' in kwargs and 'message' not in kwargs:
            kwargs['message'] = kwargs.pop('description')
        # Accept 'data' alias for meta
        if 'data' in kwargs and 'meta' not in kwargs:
            kwargs['meta'] = kwargs.pop('data')
        super().__init__(**kwargs)  # type: ignore

    # Compat alias for tests: .data <-> .meta
    @property
    def data(self) -> Optional[Dict[str, Any]]:
        return self.meta

    @data.setter
    def data(self, value: Optional[Dict[str, Any]]):
        self.meta = value
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "event_type": self.event_type.value,
            "message": self.message,
            "meta": self.meta,
            "symbol": self.symbol,
            "severity": self.severity.value if hasattr(self.severity, 'value') else self.severity,
            "resolved": self.resolved,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "portfolio_value": self.portfolio_value,
            "daily_pnl": self.daily_pnl,
            "position_pnl": self.position_pnl,
            "risk_amount": self.risk_amount,
            "action_taken": self.action_taken,
            "alert_sent": self.alert_sent
        }

class RiskMetricsSnapshot(Base):
    """Snapshots of risk metrics for historical analysis"""
    __tablename__ = "risk_metrics_snapshots"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=func.now(), nullable=False, index=True)
    
    # Portfolio metrics
    total_portfolio_value = Column(Float, nullable=False)
    available_margin = Column(Float, nullable=False)
    used_margin = Column(Float, nullable=False)
    
    # P&L metrics
    daily_pnl = Column(Float, nullable=False)
    daily_pnl_percentage = Column(Float, nullable=False)
    unrealized_pnl = Column(Float, nullable=False)
    realized_pnl = Column(Float, nullable=False)
    
    # Position metrics
    open_positions_count = Column(Integer, nullable=False)
    max_single_position_risk = Column(Float, nullable=False)
    
    # Risk metrics
    portfolio_beta = Column(Float, nullable=True)
    var_95 = Column(Float, nullable=True)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "total_portfolio_value": self.total_portfolio_value,
            "available_margin": self.available_margin,
            "used_margin": self.used_margin,
            "daily_pnl": self.daily_pnl,
            "daily_pnl_percentage": self.daily_pnl_percentage,
            "unrealized_pnl": self.unrealized_pnl,
            "realized_pnl": self.realized_pnl,
            "open_positions_count": self.open_positions_count,
            "max_single_position_risk": self.max_single_position_risk,
            "portfolio_beta": self.portfolio_beta,
            "var_95": self.var_95
        }

class EmergencyAction(Base):
    """Emergency actions taken by risk management system"""
    __tablename__ = "emergency_actions"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=func.now(), nullable=False, index=True)
    
    # Trigger information
    trigger_event_id = Column(Integer, nullable=True)
    trigger_reason = Column(Text, nullable=False)
    trigger_severity = Column(Enum(RiskSeverity), nullable=False)
    
    # Action details
    action_type = Column(String(100), nullable=False, index=True)
    action_description = Column(Text, nullable=False)
    
    # Financial impact
    positions_closed = Column(Integer, nullable=True)
    total_pnl_impact = Column(Float, nullable=True)
    portfolio_value_before = Column(Float, nullable=True)
    portfolio_value_after = Column(Float, nullable=True)
    
    # Execution details
    execution_status = Column(String(50), default="PENDING", nullable=False, index=True)
    execution_started_at = Column(DateTime, nullable=True)
    execution_completed_at = Column(DateTime, nullable=True)
    execution_error = Column(Text, nullable=True)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "trigger_event_id": self.trigger_event_id,
            "trigger_reason": self.trigger_reason,
            "trigger_severity": self.trigger_severity.value,
            "action_type": self.action_type,
            "action_description": self.action_description,
            "positions_closed": self.positions_closed,
            "total_pnl_impact": self.total_pnl_impact,
            "portfolio_value_before": self.portfolio_value_before,
            "portfolio_value_after": self.portfolio_value_after,
            "execution_status": self.execution_status,
            "execution_started_at": self.execution_started_at.isoformat() if self.execution_started_at else None,
            "execution_completed_at": self.execution_completed_at.isoformat() if self.execution_completed_at else None,
            "execution_error": self.execution_error
        }
