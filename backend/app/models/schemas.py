"""
Pydantic Schemas for API Request/Response Validation
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator
from enum import Enum


# Enums
class DeploymentStrategyEnum(str, Enum):
    BLUE_GREEN = "blue_green"
    CANARY = "canary"


class DeploymentStatusEnum(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class EnvironmentEnum(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class RoleEnum(str, Enum):
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


# Metric Configuration Schemas
class MetricThreshold(BaseModel):
    """Metric threshold configuration"""
    threshold: float = Field(..., description="Threshold value")
    comparison: str = Field(default="less_than", description="Comparison operator")
    window: int = Field(default=60, description="Time window in seconds")

    @validator('comparison')
    def validate_comparison(cls, v):
        valid = ['less_than', 'greater_than', 'equal', 'not_equal']
        if v not in valid:
            raise ValueError(f'comparison must be one of {valid}')
        return v


class MetricsConfig(BaseModel):
    """Metrics configuration for deployment"""
    error_rate: Optional[MetricThreshold] = None
    latency_p99: Optional[MetricThreshold] = None
    latency_p95: Optional[MetricThreshold] = None
    success_rate: Optional[MetricThreshold] = None
    custom_metrics: Dict[str, MetricThreshold] = Field(default_factory=dict)


# Deployment Request/Response Schemas
class DeploymentCreate(BaseModel):
    """Create deployment request"""
    service_name: str = Field(..., min_length=1, max_length=200)
    environment: EnvironmentEnum
    strategy: DeploymentStrategyEnum
    target_version: str = Field(..., min_length=1)
    namespace: str = Field(default="default")

    # Canary specific
    canary_steps: Optional[List[int]] = Field(default=[10, 25, 50, 100])

    # Metrics configuration
    metrics_config: Optional[MetricsConfig] = None

    # Additional metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @validator('canary_steps')
    def validate_canary_steps(cls, v, values):
        if values.get('strategy') == DeploymentStrategyEnum.CANARY and v:
            if not all(0 < step <= 100 for step in v):
                raise ValueError('Canary steps must be between 0 and 100')
            if sorted(v) != v:
                raise ValueError('Canary steps must be in ascending order')
        return v


class DeploymentUpdate(BaseModel):
    """Update deployment configuration"""
    status: Optional[DeploymentStatusEnum] = None
    metrics_config: Optional[MetricsConfig] = None
    metadata: Optional[Dict[str, Any]] = None


class DeploymentControl(BaseModel):
    """Control action for deployment"""
    action: str = Field(..., description="Control action")
    reason: Optional[str] = Field(None, description="Reason for action")

    @validator('action')
    def validate_action(cls, v):
        valid = ['pause', 'resume', 'rollback', 'promote', 'switch']
        if v not in valid:
            raise ValueError(f'action must be one of {valid}')
        return v


class DeploymentResponse(BaseModel):
    """Deployment response"""
    id: int
    deployment_id: str
    service_name: str
    environment: EnvironmentEnum
    strategy: DeploymentStrategyEnum
    status: DeploymentStatusEnum

    current_version: Optional[str]
    target_version: str

    # Progress
    current_step: int
    current_traffic_percentage: float
    canary_steps: List[int]

    # Blue-Green specific
    active_slot: Optional[str]

    # Timestamps
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    updated_at: Optional[datetime]

    # Status
    error_message: Optional[str]
    rollback_reason: Optional[str]

    # Metadata
    created_by: str
    metadata: Dict[str, Any]

    class Config:
        from_attributes = True


class DeploymentList(BaseModel):
    """List of deployments with pagination"""
    total: int
    page: int
    page_size: int
    deployments: List[DeploymentResponse]


# Metric Schemas
class MetricData(BaseModel):
    """Metric data point"""
    metric_name: str
    metric_value: float
    timestamp: datetime
    labels: Dict[str, str] = Field(default_factory=dict)


class MetricResponse(BaseModel):
    """Metric response"""
    deployment_id: str
    metrics: List[MetricData]


# Event Schemas
class DeploymentEventCreate(BaseModel):
    """Create deployment event"""
    event_type: str
    severity: str = Field(default="info")
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)


class DeploymentEventResponse(BaseModel):
    """Deployment event response"""
    id: int
    deployment_id: int
    event_type: str
    severity: str
    message: str
    timestamp: datetime
    actor: Optional[str]
    details: Dict[str, Any]

    class Config:
        from_attributes = True


# User & Auth Schemas
class UserCreate(BaseModel):
    """Create user request"""
    username: str = Field(..., min_length=3, max_length=100)
    email: str = Field(..., max_length=200)
    password: str = Field(..., min_length=8)
    role: RoleEnum = Field(default=RoleEnum.OPERATOR)


class UserResponse(BaseModel):
    """User response"""
    id: int
    username: str
    email: str
    role: str
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime]

    class Config:
        from_attributes = True


class Token(BaseModel):
    """JWT token response"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenData(BaseModel):
    """JWT token payload data"""
    username: Optional[str] = None
    role: Optional[str] = None


class LoginRequest(BaseModel):
    """Login request"""
    username: str
    password: str


# WebSocket Messages
class WSMessage(BaseModel):
    """WebSocket message format"""
    type: str
    deployment_id: Optional[str] = None
    data: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# Health Check
class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    version: str
    timestamp: datetime
    checks: Dict[str, bool]
