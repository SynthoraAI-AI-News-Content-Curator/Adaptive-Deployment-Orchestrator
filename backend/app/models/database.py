"""
Database Models
Production-grade SQLAlchemy models with proper indexing and relationships
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum as PyEnum

from sqlalchemy import (
    Column, Integer, String, DateTime, Boolean, JSON, Float,
    ForeignKey, Enum, Text, Index, UniqueConstraint
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

Base = declarative_base()


class DeploymentStrategy(str, PyEnum):
    """Deployment strategy types"""
    BLUE_GREEN = "blue_green"
    CANARY = "canary"


class DeploymentStatus(str, PyEnum):
    """Deployment status states"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class Environment(str, PyEnum):
    """Environment types"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class DeploymentPhase(str, PyEnum):
    """Canary deployment phases"""
    INITIAL = "initial"
    CANARY_10 = "canary_10"
    CANARY_25 = "canary_25"
    CANARY_50 = "canary_50"
    CANARY_100 = "canary_100"
    VERIFICATION = "verification"


class Deployment(Base):
    """Main deployment entity"""
    __tablename__ = "deployments"

    id = Column(Integer, primary_key=True, index=True)
    deployment_id = Column(String(100), unique=True, index=True, nullable=False)

    # Service Information
    service_name = Column(String(200), nullable=False, index=True)
    environment = Column(Enum(Environment), nullable=False, index=True)
    namespace = Column(String(100), default="default")

    # Deployment Configuration
    strategy = Column(Enum(DeploymentStrategy), nullable=False)
    status = Column(Enum(DeploymentStatus), default=DeploymentStatus.PENDING, index=True)

    # Version Information
    current_version = Column(String(100))
    target_version = Column(String(100), nullable=False)

    # Canary Configuration
    canary_steps = Column(JSON, default=[10, 25, 50, 100])  # Traffic percentage steps
    current_step = Column(Integer, default=0)
    current_traffic_percentage = Column(Float, default=0.0)

    # Blue-Green Configuration
    active_slot = Column(String(10), default="blue")  # "blue" or "green"

    # Metrics Configuration
    metrics_config = Column(JSON, default={})  # {"error_rate": {"threshold": 0.05}, ...}

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Status Tracking
    error_message = Column(Text)
    rollback_reason = Column(Text)

    # Metadata
    created_by = Column(String(100), nullable=False)
    metadata = Column(JSON, default={})

    # Relationships
    history = relationship("DeploymentHistory", back_populates="deployment", cascade="all, delete-orphan")
    metrics = relationship("DeploymentMetric", back_populates="deployment", cascade="all, delete-orphan")
    events = relationship("DeploymentEvent", back_populates="deployment", cascade="all, delete-orphan")

    __table_args__ = (
        Index('idx_service_env_status', 'service_name', 'environment', 'status'),
        Index('idx_created_at', 'created_at'),
    )


class DeploymentHistory(Base):
    """Deployment state change history for audit trail"""
    __tablename__ = "deployment_history"

    id = Column(Integer, primary_key=True, index=True)
    deployment_id = Column(Integer, ForeignKey("deployments.id"), nullable=False, index=True)

    # State Change
    from_status = Column(Enum(DeploymentStatus))
    to_status = Column(Enum(DeploymentStatus), nullable=False)
    from_traffic_percentage = Column(Float)
    to_traffic_percentage = Column(Float)

    # Context
    changed_by = Column(String(100), nullable=False)
    reason = Column(Text)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Additional Data
    metadata = Column(JSON, default={})

    deployment = relationship("Deployment", back_populates="history")

    __table_args__ = (
        Index('idx_deployment_timestamp', 'deployment_id', 'timestamp'),
    )


class DeploymentMetric(Base):
    """Time-series metrics for deployments"""
    __tablename__ = "deployment_metrics"

    id = Column(Integer, primary_key=True, index=True)
    deployment_id = Column(Integer, ForeignKey("deployments.id"), nullable=False, index=True)

    # Metric Data
    metric_name = Column(String(100), nullable=False, index=True)
    metric_value = Column(Float, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Metadata
    labels = Column(JSON, default={})
    source = Column(String(50), default="prometheus")  # prometheus, datadog, custom

    deployment = relationship("Deployment", back_populates="metrics")

    __table_args__ = (
        Index('idx_deployment_metric_time', 'deployment_id', 'metric_name', 'timestamp'),
    )


class DeploymentEvent(Base):
    """Event log for deployment actions"""
    __tablename__ = "deployment_events"

    id = Column(Integer, primary_key=True, index=True)
    deployment_id = Column(Integer, ForeignKey("deployments.id"), nullable=False, index=True)

    # Event Information
    event_type = Column(String(50), nullable=False)  # started, paused, resumed, rolled_back, etc.
    severity = Column(String(20), default="info")  # info, warning, error, critical
    message = Column(Text, nullable=False)

    # Context
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    actor = Column(String(100))  # user or system

    # Additional Data
    details = Column(JSON, default={})

    deployment = relationship("Deployment", back_populates="events")

    __table_args__ = (
        Index('idx_deployment_event_time', 'deployment_id', 'timestamp'),
        Index('idx_event_type', 'event_type'),
    )


class User(Base):
    """User entity for authentication and RBAC"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, index=True, nullable=False)
    email = Column(String(200), unique=True, index=True, nullable=False)
    hashed_password = Column(String(200), nullable=False)

    # RBAC
    role = Column(String(50), default="operator")  # admin, operator, viewer
    permissions = Column(JSON, default=[])

    # Status
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login = Column(DateTime(timezone=True))

    # Metadata
    metadata = Column(JSON, default={})


class AuditLog(Base):
    """Audit trail for all system actions"""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)

    # Action Information
    action = Column(String(100), nullable=False, index=True)
    resource_type = Column(String(50), nullable=False)
    resource_id = Column(String(100))

    # Actor Information
    user_id = Column(Integer, ForeignKey("users.id"))
    username = Column(String(100), nullable=False)
    ip_address = Column(String(50))
    user_agent = Column(String(500))

    # Context
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    success = Column(Boolean, default=True)
    error_message = Column(Text)

    # Data
    request_data = Column(JSON)
    response_data = Column(JSON)

    __table_args__ = (
        Index('idx_audit_user_time', 'user_id', 'timestamp'),
        Index('idx_audit_action', 'action', 'timestamp'),
    )
