"""
Unit Tests for Orchestration Engine
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from app.core.orchestrator import OrchestrationEngine
from app.core.metrics_analyzer import MetricsAnalyzer
from app.models.database import Deployment, DeploymentStrategy, DeploymentStatus


@pytest.mark.asyncio
async def test_create_deployment():
    """Test deployment creation"""
    db_mock = AsyncMock()
    metrics_analyzer = MetricsAnalyzer()
    orchestrator = OrchestrationEngine(db_mock, metrics_analyzer)

    # Mock database operations
    db_mock.add = Mock()
    db_mock.commit = AsyncMock()
    db_mock.refresh = AsyncMock()

    deployment = await orchestrator.create_deployment(
        service_name="test-service",
        target_version="v1.0.0",
        strategy=DeploymentStrategy.CANARY,
        environment="staging",
        created_by="test-user",
        canary_steps=[10, 50, 100]
    )

    assert deployment.service_name == "test-service"
    assert deployment.target_version == "v1.0.0"
    assert deployment.strategy == DeploymentStrategy.CANARY
    assert deployment.status == DeploymentStatus.PENDING


@pytest.mark.asyncio
async def test_canary_deployment_execution():
    """Test canary deployment execution logic"""
    db_mock = AsyncMock()
    metrics_analyzer_mock = Mock(spec=MetricsAnalyzer)
    metrics_analyzer_mock.analyze_deployment_health = AsyncMock(
        return_value={"healthy": True}
    )

    orchestrator = OrchestrationEngine(db_mock, metrics_analyzer_mock)

    # Create mock deployment
    deployment = Deployment(
        id=1,
        deployment_id="test-deployment-001",
        service_name="test-service",
        target_version="v1.0.0",
        strategy=DeploymentStrategy.CANARY,
        status=DeploymentStatus.IN_PROGRESS,
        canary_steps=[10, 50, 100],
        current_step=0,
        current_traffic_percentage=0.0,
        environment="staging",
        created_by="test-user",
        metrics_config={
            "error_rate": {"threshold": 0.05}
        }
    )

    # Mock database refresh
    async def mock_refresh(obj):
        pass

    db_mock.refresh = mock_refresh
    db_mock.commit = AsyncMock()

    # Execute canary deployment
    with patch('asyncio.sleep', return_value=None):
        await orchestrator._execute_canary_deployment(deployment)

    # Verify deployment completed
    assert deployment.status == DeploymentStatus.COMPLETED
    assert deployment.current_traffic_percentage == 100.0


@pytest.mark.asyncio
async def test_rollback_on_metrics_failure():
    """Test automatic rollback when metrics fail"""
    db_mock = AsyncMock()
    metrics_analyzer_mock = Mock(spec=MetricsAnalyzer)

    # First check passes, second fails
    metrics_analyzer_mock.analyze_deployment_health = AsyncMock(
        side_effect=[
            {"healthy": True},
            {"healthy": False, "threshold_violations": [{"metric": "error_rate"}]}
        ]
    )

    orchestrator = OrchestrationEngine(db_mock, metrics_analyzer_mock)

    deployment = Deployment(
        id=1,
        deployment_id="test-deployment-002",
        service_name="test-service",
        target_version="v1.0.0",
        strategy=DeploymentStrategy.CANARY,
        status=DeploymentStatus.IN_PROGRESS,
        canary_steps=[10, 50],
        current_step=0,
        current_traffic_percentage=0.0,
        environment="staging",
        created_by="test-user",
        metrics_config={"error_rate": {"threshold": 0.05}}
    )

    async def mock_refresh(obj):
        pass

    db_mock.refresh = mock_refresh
    db_mock.commit = AsyncMock()

    with patch('asyncio.sleep', return_value=None):
        await orchestrator._execute_canary_deployment(deployment)

    # Verify rollback occurred
    assert deployment.status == DeploymentStatus.ROLLED_BACK
    assert deployment.current_traffic_percentage == 0.0


@pytest.mark.asyncio
async def test_pause_and_resume_deployment():
    """Test pause and resume functionality"""
    db_mock = AsyncMock()
    metrics_analyzer = MetricsAnalyzer()
    orchestrator = OrchestrationEngine(db_mock, metrics_analyzer)

    deployment = Deployment(
        id=1,
        deployment_id="test-deployment-003",
        service_name="test-service",
        strategy=DeploymentStrategy.CANARY,
        status=DeploymentStatus.IN_PROGRESS,
        canary_steps=[10, 50, 100],
        current_step=1,
        current_traffic_percentage=10.0,
        environment="staging",
        created_by="test-user"
    )

    db_mock.commit = AsyncMock()

    # Test pause
    success = await orchestrator._pause_deployment(deployment, "test-user", "Testing pause")
    assert success
    assert deployment.status == DeploymentStatus.PAUSED

    # Test resume
    deployment.status = DeploymentStatus.PAUSED
    success = await orchestrator._resume_deployment(deployment, "test-user")
    assert success
    assert deployment.status == DeploymentStatus.IN_PROGRESS


def test_deployment_status_transitions():
    """Test valid deployment status transitions"""
    deployment = Deployment(
        id=1,
        deployment_id="test-deployment-004",
        service_name="test-service",
        strategy=DeploymentStrategy.CANARY,
        status=DeploymentStatus.PENDING,
        environment="staging",
        created_by="test-user"
    )

    # Valid transition: PENDING -> IN_PROGRESS
    deployment.status = DeploymentStatus.IN_PROGRESS
    assert deployment.status == DeploymentStatus.IN_PROGRESS

    # Valid transition: IN_PROGRESS -> PAUSED
    deployment.status = DeploymentStatus.PAUSED
    assert deployment.status == DeploymentStatus.PAUSED

    # Valid transition: PAUSED -> IN_PROGRESS
    deployment.status = DeploymentStatus.IN_PROGRESS
    assert deployment.status == DeploymentStatus.IN_PROGRESS

    # Valid transition: IN_PROGRESS -> COMPLETED
    deployment.status = DeploymentStatus.COMPLETED
    assert deployment.status == DeploymentStatus.COMPLETED
