"""
Application Configuration
Follows 12-factor app principles for environment-based configuration
"""
from typing import List, Optional
from pydantic import Field, validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings with environment variable support"""

    # Application
    APP_NAME: str = "Adaptive Deployment Orchestrator"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "production"

    # API Configuration
    API_V1_PREFIX: str = "/api/v1"
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Security
    SECRET_KEY: str = Field(..., min_length=32)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    ALGORITHM: str = "HS256"
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173"]

    # Database
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://ado_user:ado_pass@localhost/ado_db",
        description="Database connection URL"
    )
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 40

    # Prometheus Metrics
    PROMETHEUS_URL: str = "http://localhost:9090"
    PROMETHEUS_ENABLED: bool = True

    # Kubernetes Integration
    K8S_ENABLED: bool = False
    K8S_CONFIG_PATH: Optional[str] = None
    K8S_NAMESPACE: str = "default"

    # Deployment Defaults
    DEFAULT_HEALTH_CHECK_INTERVAL: int = 30
    DEFAULT_METRIC_CHECK_INTERVAL: int = 15
    DEFAULT_ROLLBACK_TIMEOUT: int = 300
    DEFAULT_CANARY_STEPS: List[int] = [10, 25, 50, 100]

    # Anomaly Detection
    ANOMALY_DETECTION_ENABLED: bool = True
    ANOMALY_WINDOW_SIZE: int = 50
    ANOMALY_THRESHOLD: float = 2.5  # Standard deviations

    # Observability
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"
    OTEL_ENABLED: bool = True
    OTEL_ENDPOINT: str = "http://localhost:4318"

    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_PER_MINUTE: int = 100

    # WebSocket
    WS_HEARTBEAT_INTERVAL: int = 30
    WS_MESSAGE_QUEUE_SIZE: int = 1000

    @validator("CORS_ORIGINS", pre=True)
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings()
