"""
Deployment Orchestration Engine
Core logic for Blue-Green and Canary deployment strategies
"""
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.database import (
    Deployment, DeploymentHistory, DeploymentEvent,
    DeploymentStatus, DeploymentStrategy
)
from app.models.schemas import DeploymentControl
from app.core.metrics_analyzer import MetricsAnalyzer
from app.core.config import settings

logger = logging.getLogger(__name__)


class DeploymentAction(str, Enum):
    """Available deployment actions"""
    PAUSE = "pause"
    RESUME = "resume"
    ROLLBACK = "rollback"
    PROMOTE = "promote"
    SWITCH = "switch"


class OrchestrationEngine:
    """
    Core orchestration engine for managing deployments
    Implements deployment strategies with state machine logic
    """

    def __init__(self, db: AsyncSession, metrics_analyzer: MetricsAnalyzer):
        self.db = db
        self.metrics_analyzer = metrics_analyzer
        self._active_deployments: Dict[str, asyncio.Task] = {}

    async def create_deployment(
        self,
        service_name: str,
        target_version: str,
        strategy: DeploymentStrategy,
        environment: str,
        created_by: str,
        canary_steps: Optional[List[int]] = None,
        metrics_config: Optional[Dict] = None,
        namespace: str = "default",
        metadata: Optional[Dict] = None
    ) -> Deployment:
        """
        Create and initialize a new deployment
        """
        deployment_id = f"{service_name}-{strategy.value}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

        deployment = Deployment(
            deployment_id=deployment_id,
            service_name=service_name,
            environment=environment,
            namespace=namespace,
            strategy=strategy,
            status=DeploymentStatus.PENDING,
            target_version=target_version,
            canary_steps=canary_steps or settings.DEFAULT_CANARY_STEPS,
            metrics_config=metrics_config or {},
            created_by=created_by,
            metadata=metadata or {}
        )

        self.db.add(deployment)
        await self.db.commit()
        await self.db.refresh(deployment)

        # Log creation event
        await self._log_event(
            deployment.id,
            "deployment_created",
            f"Deployment created with {strategy.value} strategy",
            "info",
            created_by
        )

        logger.info(f"Created deployment {deployment_id}")
        return deployment

    async def start_deployment(self, deployment_id: str, actor: str) -> bool:
        """
        Start a deployment asynchronously
        """
        deployment = await self._get_deployment(deployment_id)
        if not deployment:
            logger.error(f"Deployment {deployment_id} not found")
            return False

        if deployment.status not in [DeploymentStatus.PENDING, DeploymentStatus.PAUSED]:
            logger.warning(f"Cannot start deployment {deployment_id} in status {deployment.status}")
            return False

        # Update status
        await self._update_deployment_status(
            deployment,
            DeploymentStatus.IN_PROGRESS,
            actor,
            "Deployment started"
        )
        deployment.started_at = datetime.utcnow()
        await self.db.commit()

        # Start orchestration task
        task = asyncio.create_task(self._orchestrate_deployment(deployment_id))
        self._active_deployments[deployment_id] = task

        await self._log_event(
            deployment.id,
            "deployment_started",
            "Deployment execution started",
            "info",
            actor
        )

        logger.info(f"Started deployment {deployment_id}")
        return True

    async def control_deployment(
        self,
        deployment_id: str,
        control: DeploymentControl,
        actor: str
    ) -> bool:
        """
        Control a running deployment (pause, resume, rollback, etc.)
        """
        deployment = await self._get_deployment(deployment_id)
        if not deployment:
            return False

        action = DeploymentAction(control.action)

        if action == DeploymentAction.PAUSE:
            return await self._pause_deployment(deployment, actor, control.reason)
        elif action == DeploymentAction.RESUME:
            return await self._resume_deployment(deployment, actor)
        elif action == DeploymentAction.ROLLBACK:
            return await self._rollback_deployment(deployment, actor, control.reason)
        elif action == DeploymentAction.PROMOTE:
            return await self._promote_deployment(deployment, actor)
        elif action == DeploymentAction.SWITCH and deployment.strategy == DeploymentStrategy.BLUE_GREEN:
            return await self._switch_blue_green(deployment, actor)

        return False

    async def _orchestrate_deployment(self, deployment_id: str):
        """
        Main orchestration loop for a deployment
        Implements strategy-specific logic
        """
        try:
            deployment = await self._get_deployment(deployment_id)
            if not deployment:
                return

            if deployment.strategy == DeploymentStrategy.CANARY:
                await self._execute_canary_deployment(deployment)
            elif deployment.strategy == DeploymentStrategy.BLUE_GREEN:
                await self._execute_blue_green_deployment(deployment)

        except Exception as e:
            logger.error(f"Orchestration error for {deployment_id}: {str(e)}")
            deployment = await self._get_deployment(deployment_id)
            if deployment:
                deployment.status = DeploymentStatus.FAILED
                deployment.error_message = str(e)
                await self.db.commit()
        finally:
            if deployment_id in self._active_deployments:
                del self._active_deployments[deployment_id]

    async def _execute_canary_deployment(self, deployment: Deployment):
        """
        Execute canary deployment strategy with progressive traffic shifting
        """
        logger.info(f"Executing canary deployment for {deployment.deployment_id}")

        steps = deployment.canary_steps
        for i, traffic_percentage in enumerate(steps):
            # Refresh deployment state
            await self.db.refresh(deployment)

            # Check if paused or should rollback
            if deployment.status == DeploymentStatus.PAUSED:
                logger.info(f"Deployment {deployment.deployment_id} paused at step {i}")
                return
            elif deployment.status == DeploymentStatus.ROLLED_BACK:
                logger.info(f"Deployment {deployment.deployment_id} rolled back")
                return

            # Update traffic
            logger.info(
                f"Canary deployment {deployment.deployment_id}: "
                f"Moving to step {i+1}/{len(steps)} ({traffic_percentage}%)"
            )

            old_percentage = deployment.current_traffic_percentage
            deployment.current_step = i
            deployment.current_traffic_percentage = traffic_percentage
            await self.db.commit()

            # Log traffic shift
            await self._log_history(
                deployment.id,
                DeploymentStatus.IN_PROGRESS,
                DeploymentStatus.IN_PROGRESS,
                "system",
                f"Traffic shifted to {traffic_percentage}%",
                old_percentage,
                traffic_percentage
            )

            # Wait for metrics stabilization
            stabilization_time = settings.DEFAULT_METRIC_CHECK_INTERVAL
            await asyncio.sleep(stabilization_time)

            # Check metrics
            metrics_ok = await self._check_metrics(deployment)
            if not metrics_ok:
                logger.warning(f"Metrics check failed for {deployment.deployment_id}")
                await self._rollback_deployment(
                    deployment,
                    "system",
                    f"Automated rollback: metrics failed at {traffic_percentage}% traffic"
                )
                return

            await self._log_event(
                deployment.id,
                "traffic_shifted",
                f"Traffic successfully shifted to {traffic_percentage}%",
                "info",
                "system"
            )

        # All steps completed successfully
        deployment.status = DeploymentStatus.COMPLETED
        deployment.completed_at = datetime.utcnow()
        deployment.current_version = deployment.target_version
        await self.db.commit()

        await self._log_event(
            deployment.id,
            "deployment_completed",
            "Canary deployment completed successfully",
            "info",
            "system"
        )

        logger.info(f"Canary deployment {deployment.deployment_id} completed successfully")

    async def _execute_blue_green_deployment(self, deployment: Deployment):
        """
        Execute blue-green deployment strategy with instant traffic switch
        """
        logger.info(f"Executing blue-green deployment for {deployment.deployment_id}")

        # Deploy to inactive slot
        inactive_slot = "green" if deployment.active_slot == "blue" else "blue"
        logger.info(f"Deploying {deployment.target_version} to {inactive_slot} slot")

        await self._log_event(
            deployment.id,
            "slot_deployment",
            f"Deploying to {inactive_slot} slot",
            "info",
            "system"
        )

        # Simulate deployment to inactive slot
        await asyncio.sleep(5)

        # Health check on inactive slot
        await self._log_event(
            deployment.id,
            "health_check",
            f"Running health checks on {inactive_slot} slot",
            "info",
            "system"
        )

        await asyncio.sleep(3)

        # Check metrics before switch
        deployment.current_traffic_percentage = 0
        await self.db.commit()

        # Wait for operator approval or auto-promote
        # In production, this would wait for manual approval
        await asyncio.sleep(settings.DEFAULT_HEALTH_CHECK_INTERVAL)

        # Refresh state
        await self.db.refresh(deployment)
        if deployment.status == DeploymentStatus.PAUSED:
            logger.info(f"Blue-green deployment {deployment.deployment_id} waiting for approval")
            return

        # Switch traffic
        await self._switch_blue_green(deployment, "system")

        # Monitor for a period
        await asyncio.sleep(settings.DEFAULT_METRIC_CHECK_INTERVAL)

        # Check post-switch metrics
        metrics_ok = await self._check_metrics(deployment)
        if not metrics_ok:
            logger.warning(f"Post-switch metrics failed for {deployment.deployment_id}")
            # Switch back
            await self._switch_blue_green(deployment, "system")
            await self._rollback_deployment(
                deployment,
                "system",
                "Automated rollback: post-switch metrics failed"
            )
            return

        # Complete deployment
        deployment.status = DeploymentStatus.COMPLETED
        deployment.completed_at = datetime.utcnow()
        deployment.current_version = deployment.target_version
        await self.db.commit()

        await self._log_event(
            deployment.id,
            "deployment_completed",
            "Blue-green deployment completed successfully",
            "info",
            "system"
        )

        logger.info(f"Blue-green deployment {deployment.deployment_id} completed successfully")

    async def _check_metrics(self, deployment: Deployment) -> bool:
        """
        Check deployment metrics against thresholds
        Returns True if metrics are healthy
        """
        try:
            result = await self.metrics_analyzer.analyze_deployment_health(
                deployment.deployment_id,
                deployment.metrics_config
            )
            return result.get("healthy", False)
        except Exception as e:
            logger.error(f"Metrics check error for {deployment.deployment_id}: {str(e)}")
            return False

    async def _pause_deployment(
        self,
        deployment: Deployment,
        actor: str,
        reason: Optional[str]
    ) -> bool:
        """Pause a running deployment"""
        if deployment.status != DeploymentStatus.IN_PROGRESS:
            return False

        await self._update_deployment_status(
            deployment,
            DeploymentStatus.PAUSED,
            actor,
            reason or "Deployment paused by operator"
        )
        await self.db.commit()

        await self._log_event(
            deployment.id,
            "deployment_paused",
            reason or "Deployment paused",
            "warning",
            actor
        )

        logger.info(f"Paused deployment {deployment.deployment_id}")
        return True

    async def _resume_deployment(self, deployment: Deployment, actor: str) -> bool:
        """Resume a paused deployment"""
        if deployment.status != DeploymentStatus.PAUSED:
            return False

        await self._update_deployment_status(
            deployment,
            DeploymentStatus.IN_PROGRESS,
            actor,
            "Deployment resumed"
        )
        await self.db.commit()

        # Restart orchestration
        if deployment.deployment_id not in self._active_deployments:
            task = asyncio.create_task(self._orchestrate_deployment(deployment.deployment_id))
            self._active_deployments[deployment.deployment_id] = task

        await self._log_event(
            deployment.id,
            "deployment_resumed",
            "Deployment resumed",
            "info",
            actor
        )

        logger.info(f"Resumed deployment {deployment.deployment_id}")
        return True

    async def _rollback_deployment(
        self,
        deployment: Deployment,
        actor: str,
        reason: Optional[str]
    ) -> bool:
        """Rollback a deployment"""
        logger.warning(f"Rolling back deployment {deployment.deployment_id}: {reason}")

        # Revert traffic to 0%
        old_percentage = deployment.current_traffic_percentage
        deployment.current_traffic_percentage = 0.0
        deployment.rollback_reason = reason
        deployment.status = DeploymentStatus.ROLLED_BACK
        deployment.completed_at = datetime.utcnow()

        await self._log_history(
            deployment.id,
            DeploymentStatus.IN_PROGRESS,
            DeploymentStatus.ROLLED_BACK,
            actor,
            reason or "Deployment rolled back",
            old_percentage,
            0.0
        )

        await self.db.commit()

        await self._log_event(
            deployment.id,
            "deployment_rolled_back",
            reason or "Deployment rolled back",
            "error",
            actor
        )

        return True

    async def _promote_deployment(self, deployment: Deployment, actor: str) -> bool:
        """Promote deployment to 100% immediately"""
        if deployment.status not in [DeploymentStatus.IN_PROGRESS, DeploymentStatus.PAUSED]:
            return False

        old_percentage = deployment.current_traffic_percentage
        deployment.current_traffic_percentage = 100.0
        deployment.current_step = len(deployment.canary_steps) - 1
        deployment.status = DeploymentStatus.COMPLETED
        deployment.completed_at = datetime.utcnow()
        deployment.current_version = deployment.target_version

        await self._log_history(
            deployment.id,
            DeploymentStatus.IN_PROGRESS,
            DeploymentStatus.COMPLETED,
            actor,
            "Deployment promoted to 100%",
            old_percentage,
            100.0
        )

        await self.db.commit()

        await self._log_event(
            deployment.id,
            "deployment_promoted",
            "Deployment promoted to 100%",
            "info",
            actor
        )

        logger.info(f"Promoted deployment {deployment.deployment_id} to 100%")
        return True

    async def _switch_blue_green(self, deployment: Deployment, actor: str) -> bool:
        """Switch active/inactive slots in blue-green deployment"""
        if deployment.strategy != DeploymentStrategy.BLUE_GREEN:
            return False

        old_slot = deployment.active_slot
        new_slot = "green" if old_slot == "blue" else "blue"

        deployment.active_slot = new_slot
        deployment.current_traffic_percentage = 100.0 if new_slot != old_slot else 0.0
        await self.db.commit()

        await self._log_event(
            deployment.id,
            "traffic_switched",
            f"Traffic switched from {old_slot} to {new_slot}",
            "info",
            actor
        )

        logger.info(f"Switched traffic from {old_slot} to {new_slot} for {deployment.deployment_id}")
        return True

    async def _update_deployment_status(
        self,
        deployment: Deployment,
        new_status: DeploymentStatus,
        actor: str,
        reason: str
    ):
        """Update deployment status with history tracking"""
        old_status = deployment.status
        deployment.status = new_status

        await self._log_history(
            deployment.id,
            old_status,
            new_status,
            actor,
            reason
        )

    async def _log_history(
        self,
        deployment_id: int,
        from_status: DeploymentStatus,
        to_status: DeploymentStatus,
        changed_by: str,
        reason: Optional[str] = None,
        from_traffic: Optional[float] = None,
        to_traffic: Optional[float] = None
    ):
        """Log deployment state change to history"""
        history = DeploymentHistory(
            deployment_id=deployment_id,
            from_status=from_status,
            to_status=to_status,
            from_traffic_percentage=from_traffic,
            to_traffic_percentage=to_traffic,
            changed_by=changed_by,
            reason=reason
        )
        self.db.add(history)

    async def _log_event(
        self,
        deployment_id: int,
        event_type: str,
        message: str,
        severity: str = "info",
        actor: Optional[str] = None
    ):
        """Log deployment event"""
        event = DeploymentEvent(
            deployment_id=deployment_id,
            event_type=event_type,
            severity=severity,
            message=message,
            actor=actor
        )
        self.db.add(event)
        await self.db.commit()

    async def _get_deployment(self, deployment_id: str) -> Optional[Deployment]:
        """Get deployment by ID"""
        result = await self.db.execute(
            select(Deployment).where(Deployment.deployment_id == deployment_id)
        )
        return result.scalar_one_or_none()
