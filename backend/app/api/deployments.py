"""
Deployment API Endpoints
REST API for managing deployments
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import get_current_user, require_operator_or_admin, log_audit_event
from app.core.orchestrator import OrchestrationEngine
from app.core.metrics_analyzer import MetricsAnalyzer
from app.models.database import (
    Deployment, DeploymentHistory, DeploymentEvent, DeploymentMetric,
    User, DeploymentStatus, DeploymentStrategy
)
from app.models.schemas import (
    DeploymentCreate, DeploymentResponse, DeploymentList,
    DeploymentControl, DeploymentEventResponse, MetricResponse
)

router = APIRouter(prefix="/deployments", tags=["deployments"])


@router.post(
    "",
    response_model=DeploymentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new deployment"
)
async def create_deployment(
    deployment_data: DeploymentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator_or_admin)
):
    """
    Create a new deployment with specified strategy.

    - **service_name**: Name of the service to deploy
    - **environment**: Target environment (development, staging, production)
    - **strategy**: Deployment strategy (blue_green or canary)
    - **target_version**: Version to deploy
    - **canary_steps**: Traffic percentage steps for canary (optional)
    - **metrics_config**: Metrics thresholds for health checks (optional)
    """
    # Initialize orchestrator
    metrics_analyzer = MetricsAnalyzer()
    orchestrator = OrchestrationEngine(db, metrics_analyzer)

    # Create deployment
    deployment = await orchestrator.create_deployment(
        service_name=deployment_data.service_name,
        target_version=deployment_data.target_version,
        strategy=DeploymentStrategy(deployment_data.strategy),
        environment=deployment_data.environment.value,
        created_by=current_user.username,
        canary_steps=deployment_data.canary_steps,
        metrics_config=deployment_data.metrics_config.dict() if deployment_data.metrics_config else None,
        namespace=deployment_data.namespace,
        metadata=deployment_data.metadata
    )

    # Log audit event
    await log_audit_event(
        db=db,
        action="deployment_created",
        resource_type="deployment",
        resource_id=deployment.deployment_id,
        user=current_user,
        request_data=deployment_data.dict()
    )

    return deployment


@router.get(
    "",
    response_model=DeploymentList,
    summary="List deployments"
)
async def list_deployments(
    service_name: Optional[str] = Query(None),
    environment: Optional[str] = Query(None),
    status: Optional[DeploymentStatus] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List deployments with optional filtering and pagination.
    """
    query = select(Deployment)

    # Apply filters
    if service_name:
        query = query.where(Deployment.service_name == service_name)
    if environment:
        query = query.where(Deployment.environment == environment)
    if status:
        query = query.where(Deployment.status == status)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Apply pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size).order_by(Deployment.created_at.desc())

    result = await db.execute(query)
    deployments = result.scalars().all()

    return DeploymentList(
        total=total,
        page=page,
        page_size=page_size,
        deployments=deployments
    )


@router.get(
    "/{deployment_id}",
    response_model=DeploymentResponse,
    summary="Get deployment details"
)
async def get_deployment(
    deployment_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get detailed information about a specific deployment.
    """
    result = await db.execute(
        select(Deployment).where(Deployment.deployment_id == deployment_id)
    )
    deployment = result.scalar_one_or_none()

    if not deployment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deployment {deployment_id} not found"
        )

    return deployment


@router.post(
    "/{deployment_id}/start",
    response_model=DeploymentResponse,
    summary="Start deployment execution"
)
async def start_deployment(
    deployment_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator_or_admin)
):
    """
    Start the deployment execution process.
    """
    metrics_analyzer = MetricsAnalyzer()
    orchestrator = OrchestrationEngine(db, metrics_analyzer)

    success = await orchestrator.start_deployment(deployment_id, current_user.username)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to start deployment"
        )

    # Get updated deployment
    result = await db.execute(
        select(Deployment).where(Deployment.deployment_id == deployment_id)
    )
    deployment = result.scalar_one_or_none()

    # Log audit event
    await log_audit_event(
        db=db,
        action="deployment_started",
        resource_type="deployment",
        resource_id=deployment_id,
        user=current_user
    )

    return deployment


@router.post(
    "/{deployment_id}/control",
    response_model=DeploymentResponse,
    summary="Control deployment (pause, resume, rollback)"
)
async def control_deployment(
    deployment_id: str,
    control: DeploymentControl,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator_or_admin)
):
    """
    Control a deployment with actions:
    - **pause**: Pause the deployment at current step
    - **resume**: Resume a paused deployment
    - **rollback**: Rollback the deployment
    - **promote**: Promote to 100% immediately
    - **switch**: Switch blue/green slots
    """
    metrics_analyzer = MetricsAnalyzer()
    orchestrator = OrchestrationEngine(db, metrics_analyzer)

    success = await orchestrator.control_deployment(
        deployment_id,
        control,
        current_user.username
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to {control.action} deployment"
        )

    # Get updated deployment
    result = await db.execute(
        select(Deployment).where(Deployment.deployment_id == deployment_id)
    )
    deployment = result.scalar_one_or_none()

    # Log audit event
    await log_audit_event(
        db=db,
        action=f"deployment_{control.action}",
        resource_type="deployment",
        resource_id=deployment_id,
        user=current_user,
        request_data={"action": control.action, "reason": control.reason}
    )

    return deployment


@router.get(
    "/{deployment_id}/history",
    response_model=List[dict],
    summary="Get deployment history"
)
async def get_deployment_history(
    deployment_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get state change history for a deployment.
    """
    # Get deployment
    result = await db.execute(
        select(Deployment).where(Deployment.deployment_id == deployment_id)
    )
    deployment = result.scalar_one_or_none()

    if not deployment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deployment {deployment_id} not found"
        )

    # Get history
    history_result = await db.execute(
        select(DeploymentHistory)
        .where(DeploymentHistory.deployment_id == deployment.id)
        .order_by(DeploymentHistory.timestamp.desc())
    )
    history = history_result.scalars().all()

    return [
        {
            "id": h.id,
            "from_status": h.from_status.value if h.from_status else None,
            "to_status": h.to_status.value,
            "from_traffic_percentage": h.from_traffic_percentage,
            "to_traffic_percentage": h.to_traffic_percentage,
            "changed_by": h.changed_by,
            "reason": h.reason,
            "timestamp": h.timestamp.isoformat(),
            "metadata": h.metadata
        }
        for h in history
    ]


@router.get(
    "/{deployment_id}/events",
    response_model=List[DeploymentEventResponse],
    summary="Get deployment events"
)
async def get_deployment_events(
    deployment_id: str,
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get event log for a deployment.
    """
    # Get deployment
    result = await db.execute(
        select(Deployment).where(Deployment.deployment_id == deployment_id)
    )
    deployment = result.scalar_one_or_none()

    if not deployment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deployment {deployment_id} not found"
        )

    # Get events
    events_result = await db.execute(
        select(DeploymentEvent)
        .where(DeploymentEvent.deployment_id == deployment.id)
        .order_by(DeploymentEvent.timestamp.desc())
        .limit(limit)
    )
    events = events_result.scalars().all()

    return events


@router.get(
    "/{deployment_id}/metrics",
    response_model=MetricResponse,
    summary="Get deployment metrics"
)
async def get_deployment_metrics(
    deployment_id: str,
    metric_names: Optional[str] = Query(None, description="Comma-separated metric names"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get metrics data for a deployment.
    """
    # Get deployment
    result = await db.execute(
        select(Deployment).where(Deployment.deployment_id == deployment_id)
    )
    deployment = result.scalar_one_or_none()

    if not deployment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deployment {deployment_id} not found"
        )

    # Build query
    query = select(DeploymentMetric).where(DeploymentMetric.deployment_id == deployment.id)

    if metric_names:
        names = [n.strip() for n in metric_names.split(",")]
        query = query.where(DeploymentMetric.metric_name.in_(names))

    query = query.order_by(DeploymentMetric.timestamp.desc()).limit(1000)

    # Get metrics
    metrics_result = await db.execute(query)
    metrics = metrics_result.scalars().all()

    return MetricResponse(
        deployment_id=deployment_id,
        metrics=[
            {
                "metric_name": m.metric_name,
                "metric_value": m.metric_value,
                "timestamp": m.timestamp,
                "labels": m.labels
            }
            for m in metrics
        ]
    )


@router.delete(
    "/{deployment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete deployment"
)
async def delete_deployment(
    deployment_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator_or_admin)
):
    """
    Delete a deployment (only if not in progress).
    """
    result = await db.execute(
        select(Deployment).where(Deployment.deployment_id == deployment_id)
    )
    deployment = result.scalar_one_or_none()

    if not deployment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deployment {deployment_id} not found"
        )

    if deployment.status == DeploymentStatus.IN_PROGRESS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete deployment in progress"
        )

    await db.delete(deployment)
    await db.commit()

    # Log audit event
    await log_audit_event(
        db=db,
        action="deployment_deleted",
        resource_type="deployment",
        resource_id=deployment_id,
        user=current_user
    )
