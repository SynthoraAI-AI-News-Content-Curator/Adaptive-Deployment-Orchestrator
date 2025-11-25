"""
WebSocket Handler for Real-Time Updates
Provides live deployment status and metric updates to dashboard
"""
import asyncio
import json
import logging
from typing import Dict, Set
from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.security import decode_access_token, AuthenticationError
from app.models.database import Deployment, DeploymentEvent
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


class ConnectionManager:
    """
    Manages WebSocket connections and broadcasting
    Thread-safe connection management for multiple clients
    """

    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, deployment_id: str = "global"):
        """Accept and register a new WebSocket connection"""
        await websocket.accept()
        async with self._lock:
            if deployment_id not in self.active_connections:
                self.active_connections[deployment_id] = set()
            self.active_connections[deployment_id].add(websocket)
        logger.info(f"WebSocket connected to {deployment_id}. Total connections: {self.get_connection_count()}")

    async def disconnect(self, websocket: WebSocket, deployment_id: str = "global"):
        """Unregister a WebSocket connection"""
        async with self._lock:
            if deployment_id in self.active_connections:
                self.active_connections[deployment_id].discard(websocket)
                if not self.active_connections[deployment_id]:
                    del self.active_connections[deployment_id]
        logger.info(f"WebSocket disconnected from {deployment_id}. Total connections: {self.get_connection_count()}")

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """Send message to specific connection"""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Error sending personal message: {str(e)}")

    async def broadcast_to_deployment(self, message: dict, deployment_id: str):
        """Broadcast message to all connections watching a specific deployment"""
        async with self._lock:
            connections = self.active_connections.get(deployment_id, set()).copy()

        disconnected = set()
        for connection in connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting to deployment {deployment_id}: {str(e)}")
                disconnected.add(connection)

        # Clean up disconnected connections
        if disconnected:
            async with self._lock:
                if deployment_id in self.active_connections:
                    self.active_connections[deployment_id] -= disconnected

    async def broadcast_global(self, message: dict):
        """Broadcast message to all connections"""
        await self.broadcast_to_deployment(message, "global")

        # Also send to all deployment-specific connections
        async with self._lock:
            deployment_ids = list(self.active_connections.keys())

        for deployment_id in deployment_ids:
            if deployment_id != "global":
                await self.broadcast_to_deployment(message, deployment_id)

    def get_connection_count(self) -> int:
        """Get total number of active connections"""
        return sum(len(conns) for conns in self.active_connections.values())


# Global connection manager
manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(...),
    deployment_id: str = Query(None)
):
    """
    WebSocket endpoint for real-time updates

    Query Parameters:
    - token: JWT authentication token
    - deployment_id: Optional specific deployment to watch (or "global" for all)

    Message Types Sent:
    - deployment_update: Deployment status changed
    - metric_update: New metric data available
    - event: New deployment event
    - heartbeat: Keep-alive ping
    """
    # Authenticate
    try:
        token_data = decode_access_token(token)
        if not token_data.username:
            await websocket.close(code=4001, reason="Authentication failed")
            return
    except AuthenticationError as e:
        await websocket.close(code=4001, reason=str(e))
        return

    # Connect
    watch_id = deployment_id if deployment_id else "global"
    await manager.connect(websocket, watch_id)

    try:
        # Send welcome message
        await manager.send_personal_message({
            "type": "connected",
            "message": f"Connected to deployment updates: {watch_id}",
            "timestamp": datetime.utcnow().isoformat()
        }, websocket)

        # Start heartbeat task
        heartbeat_task = asyncio.create_task(send_heartbeat(websocket))

        # Main message loop
        while True:
            # Receive messages from client
            data = await websocket.receive_text()
            message = json.loads(data)

            # Handle different message types
            message_type = message.get("type")

            if message_type == "subscribe":
                # Subscribe to specific deployment
                sub_deployment_id = message.get("deployment_id")
                if sub_deployment_id:
                    await manager.connect(websocket, sub_deployment_id)
                    await manager.send_personal_message({
                        "type": "subscribed",
                        "deployment_id": sub_deployment_id,
                        "timestamp": datetime.utcnow().isoformat()
                    }, websocket)

            elif message_type == "unsubscribe":
                # Unsubscribe from deployment
                unsub_deployment_id = message.get("deployment_id")
                if unsub_deployment_id:
                    await manager.disconnect(websocket, unsub_deployment_id)
                    await manager.send_personal_message({
                        "type": "unsubscribed",
                        "deployment_id": unsub_deployment_id,
                        "timestamp": datetime.utcnow().isoformat()
                    }, websocket)

            elif message_type == "ping":
                # Respond to ping
                await manager.send_personal_message({
                    "type": "pong",
                    "timestamp": datetime.utcnow().isoformat()
                }, websocket)

            elif message_type == "get_status":
                # Send current deployment status
                req_deployment_id = message.get("deployment_id")
                if req_deployment_id:
                    status_data = await get_deployment_status(req_deployment_id)
                    await manager.send_personal_message({
                        "type": "deployment_status",
                        "data": status_data,
                        "timestamp": datetime.utcnow().isoformat()
                    }, websocket)

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected normally for {watch_id}")
    except Exception as e:
        logger.error(f"WebSocket error for {watch_id}: {str(e)}")
    finally:
        heartbeat_task.cancel()
        await manager.disconnect(websocket, watch_id)


async def send_heartbeat(websocket: WebSocket):
    """Send periodic heartbeat to keep connection alive"""
    try:
        while True:
            await asyncio.sleep(settings.WS_HEARTBEAT_INTERVAL)
            await websocket.send_json({
                "type": "heartbeat",
                "timestamp": datetime.utcnow().isoformat()
            })
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"Heartbeat error: {str(e)}")


async def get_deployment_status(deployment_id: str) -> dict:
    """Get current deployment status from database"""
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Deployment).where(Deployment.deployment_id == deployment_id)
            )
            deployment = result.scalar_one_or_none()

            if not deployment:
                return {"error": "Deployment not found"}

            return {
                "deployment_id": deployment.deployment_id,
                "service_name": deployment.service_name,
                "status": deployment.status.value,
                "strategy": deployment.strategy.value,
                "current_traffic_percentage": deployment.current_traffic_percentage,
                "current_step": deployment.current_step,
                "target_version": deployment.target_version,
                "error_message": deployment.error_message
            }
    except Exception as e:
        logger.error(f"Error getting deployment status: {str(e)}")
        return {"error": str(e)}


# Utility functions for broadcasting updates (called from orchestrator)

async def broadcast_deployment_update(deployment_id: str, status: str, data: dict):
    """Broadcast deployment status update"""
    message = {
        "type": "deployment_update",
        "deployment_id": deployment_id,
        "status": status,
        "data": data,
        "timestamp": datetime.utcnow().isoformat()
    }
    await manager.broadcast_to_deployment(message, deployment_id)
    await manager.broadcast_global(message)


async def broadcast_metric_update(deployment_id: str, metrics: dict):
    """Broadcast metric update"""
    message = {
        "type": "metric_update",
        "deployment_id": deployment_id,
        "metrics": metrics,
        "timestamp": datetime.utcnow().isoformat()
    }
    await manager.broadcast_to_deployment(message, deployment_id)


async def broadcast_event(deployment_id: str, event_type: str, event_message: str, severity: str = "info"):
    """Broadcast deployment event"""
    message = {
        "type": "event",
        "deployment_id": deployment_id,
        "event_type": event_type,
        "message": event_message,
        "severity": severity,
        "timestamp": datetime.utcnow().isoformat()
    }
    await manager.broadcast_to_deployment(message, deployment_id)
    await manager.broadcast_global(message)
