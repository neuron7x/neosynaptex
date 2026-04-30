"""
WebSocket connection manager for MyceliumFractalNet.

Manages WebSocket connections, subscriptions, and streaming with:
- Connection lifecycle management
- Heartbeat and keepalive
- Backpressure handling (drop oldest/compress)
- Authentication and authorization
- Audit logging

Reference: docs/MFN_BACKLOG.md#MFN-API-STREAMING
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import hmac
import os
import time
import uuid
from collections import deque
from enum import Enum
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from .api_config import get_api_config
from .logging_config import get_logger
from .ws_schemas import (
    WSMessageType,
    WSStreamType,
)

logger = get_logger("ws_manager")


class BackpressureStrategy(str, Enum):
    """Backpressure handling strategies."""

    DROP_OLDEST = "drop_oldest"
    DROP_NEWEST = "drop_newest"
    COMPRESS = "compress"


class WSConnectionState:
    """
    State management for a single WebSocket connection.

    Tracks connection lifecycle, authentication, subscriptions, and message queues.

    Attributes:
        connection_id: Unique connection identifier.
        websocket: FastAPI WebSocket instance.
        authenticated: Whether connection is authenticated.
        subscriptions: Set of active stream IDs.
        last_heartbeat: Timestamp of last heartbeat.
        created_at: Connection creation timestamp.
        message_queue: Deque for outbound messages with backpressure.
        client_info: Optional client identification info.
    """

    def __init__(
        self,
        connection_id: str,
        websocket: WebSocket,
        max_queue_size: int = 1000,
    ):
        self.connection_id = connection_id
        self.websocket = websocket
        self.authenticated = False
        self.subscriptions: set[str] = set()
        self.last_heartbeat = time.time()
        self.created_at = time.time()
        self.message_queue: deque[dict[str, Any]] = deque(maxlen=max_queue_size)
        self.client_info: str | None = None
        self.api_key_used: str | None = None

    def is_alive(self, timeout: float = 60.0) -> bool:
        """Check if connection is alive based on heartbeat timeout."""
        return (time.time() - self.last_heartbeat) < timeout

    def update_heartbeat(self) -> None:
        """Update last heartbeat timestamp."""
        self.last_heartbeat = time.time()

    def add_subscription(self, stream_id: str) -> None:
        """Add a stream subscription."""
        self.subscriptions.add(stream_id)
        logger.info(
            f"Connection {self.connection_id} subscribed to {stream_id}",
            extra={
                "connection_id": self.connection_id,
                "stream_id": stream_id,
                "total_subscriptions": len(self.subscriptions),
            },
        )

    def remove_subscription(self, stream_id: str) -> None:
        """Remove a stream subscription."""
        self.subscriptions.discard(stream_id)
        logger.info(
            f"Connection {self.connection_id} unsubscribed from {stream_id}",
            extra={
                "connection_id": self.connection_id,
                "stream_id": stream_id,
                "total_subscriptions": len(self.subscriptions),
            },
        )


class WSConnectionManager:
    """
    WebSocket connection manager.

    Manages multiple WebSocket connections with authentication, subscriptions,
    heartbeat monitoring, and backpressure handling.

    Attributes:
        connections: Dictionary of active connections by connection_id.
        stream_subscriptions: Dictionary mapping stream_id to set of connection_ids.
        backpressure_strategy: Strategy for handling message queue overflow.
        max_queue_size: Maximum messages in queue per connection.
        heartbeat_interval: Interval for heartbeat checks (seconds).
        heartbeat_timeout: Timeout for considering connection dead (seconds).
    """

    def __init__(
        self,
        backpressure_strategy: str = BackpressureStrategy.DROP_OLDEST,
        max_queue_size: int = 1000,
        heartbeat_interval: float = 30.0,
        heartbeat_timeout: float = 60.0,
    ):
        self.connections: dict[str, WSConnectionState] = {}
        self.stream_subscriptions: dict[str, set[str]] = {}
        self.backpressure_strategy = backpressure_strategy
        self.max_queue_size = max_queue_size
        self.heartbeat_interval = heartbeat_interval
        self.heartbeat_timeout = heartbeat_timeout
        self._heartbeat_task: asyncio.Task[Any] | None = None

    async def connect(self, websocket: WebSocket) -> str:
        """
        Accept WebSocket connection and create connection state.

        Args:
            websocket: FastAPI WebSocket instance.

        Returns:
            Connection ID.
        """
        await websocket.accept()
        connection_id = str(uuid.uuid4())
        connection = WSConnectionState(
            connection_id=connection_id,
            websocket=websocket,
            max_queue_size=self.max_queue_size,
        )
        self.connections[connection_id] = connection

        logger.info(
            f"WebSocket connection accepted: {connection_id}",
            extra={
                "connection_id": connection_id,
                "total_connections": len(self.connections),
            },
        )

        return connection_id

    async def disconnect(self, connection_id: str) -> None:
        """
        Disconnect and clean up connection.

        Args:
            connection_id: Connection identifier.
        """
        if connection_id not in self.connections:
            return

        connection = self.connections[connection_id]

        # Remove from all stream subscriptions
        for stream_id in list(connection.subscriptions):
            await self._remove_from_stream(connection_id, stream_id)

        # Close the underlying WebSocket to release transport resources
        try:
            await connection.websocket.close()
        except Exception as exc:  # pragma: no cover - defensive cleanup
            logger.warning(
                "WebSocket close failed during disconnect",
                extra={
                    "connection_id": connection_id,
                    "error": str(exc),
                },
            )

        # Remove connection
        del self.connections[connection_id]

        logger.info(
            f"WebSocket connection closed: {connection_id}",
            extra={
                "connection_id": connection_id,
                "total_connections": len(self.connections),
                "duration_seconds": time.time() - connection.created_at,
            },
        )

    def authenticate(self, connection_id: str, api_key: str | None, timestamp: float) -> bool:
        """
        Authenticate a WebSocket connection.

        Args:
            connection_id: Connection identifier.
            api_key: API key for authentication.
            timestamp: Request timestamp for replay attack prevention.

        Returns:
            bool: True if authentication successful.
        """
        if connection_id not in self.connections:
            return False

        connection = self.connections[connection_id]

        # Check timestamp (allow 5 minute window). Some clients send seconds
        # instead of milliseconds despite the schema specification, so we
        # normalize both formats to milliseconds to avoid rejecting otherwise
        # valid authentication attempts.
        try:
            ts_ms = float(timestamp)
        except (TypeError, ValueError):
            logger.warning(
                "Authentication failed: invalid timestamp format",
                extra={
                    "connection_id": connection_id,
                    "timestamp": timestamp,
                },
            )
            return False

        if ts_ms < 1e12:  # Likely seconds-since-epoch
            ts_ms *= 1000

        current_time = time.time() * 1000  # Convert to milliseconds
        time_diff = abs(current_time - ts_ms)
        if time_diff > 5 * 60 * 1000:  # 5 minutes
            logger.warning(
                "Authentication failed: timestamp out of range",
                extra={
                    "connection_id": connection_id,
                    "time_diff_ms": time_diff,
                },
            )
            return False

        # Validate API key
        api_config = get_api_config()
        if api_config.auth.api_key_required and not self._validate_api_key(api_key):
            logger.warning(
                "Authentication failed: invalid API key",
                extra={"connection_id": connection_id},
            )
            return False

        # Optional authentication should not break on missing or malformed keys
        if not api_config.auth.api_key_required and api_key is not None:
            if not isinstance(api_key, str):
                logger.warning(
                    "Authentication provided non-string API key; ignoring for optional auth",
                    extra={
                        "connection_id": connection_id,
                        "api_key_type": type(api_key).__name__,
                    },
                )
                api_key = None

        connection.authenticated = True
        connection.api_key_used = self._mask_api_key(api_key)
        connection.update_heartbeat()

        logger.info(
            f"WebSocket authenticated: {connection_id}",
            extra={
                "connection_id": connection_id,
                "api_key_partial": connection.api_key_used,
            },
        )

        return True

    @staticmethod
    def _mask_api_key(api_key: str | None) -> str | None:
        """Return a non-reversible audit fingerprint of an API key.

        HMAC-SHA256 keyed by the ``MFN_AUDIT_PEPPER`` env-pepper so leaked
        audit logs cannot be brute-forced into the originating key, even
        for low-entropy keys. Recognised by CodeQL as a non-weak primitive
        (py/weak-sensitive-data-hashing) when used with HMAC.
        """
        if not api_key or not isinstance(api_key, str):
            return None
        pepper = os.environ.get(
            "MFN_AUDIT_PEPPER", "mfn-default-pepper-set-MFN_AUDIT_PEPPER-in-prod"
        ).encode("utf-8")
        digest = hmac.new(pepper, api_key.encode("utf-8"), hashlib.sha256).hexdigest()
        return f"hmac:{digest[:12]}"

    def _validate_api_key(self, api_key: str | None) -> bool:
        """Validate API key against configured keys."""
        if not api_key or not isinstance(api_key, str):
            return False

        api_config = get_api_config()
        if not api_config.auth.api_key_required:
            return True

        # Use constant-time comparison
        valid = False
        for valid_key in api_config.auth.api_keys:
            if hmac.compare_digest(api_key, valid_key):
                valid = True
                break
        return valid

    async def subscribe(
        self,
        connection_id: str,
        stream_id: str,
        stream_type: WSStreamType,
        params: dict[str, Any] | None = None,
    ) -> bool:
        """
        Subscribe connection to a stream.

        Args:
            connection_id: Connection identifier.
            stream_id: Unique stream identifier.
            stream_type: Type of stream to subscribe to.
            params: Stream-specific parameters.

        Returns:
            bool: True if subscription successful.
        """
        if connection_id not in self.connections:
            return False

        connection = self.connections[connection_id]

        if not connection.authenticated:
            logger.warning(
                "Subscription failed: not authenticated",
                extra={"connection_id": connection_id, "stream_id": stream_id},
            )
            return False

        # Add subscription to connection
        connection.add_subscription(stream_id)

        # Add to stream subscription mapping
        if stream_id not in self.stream_subscriptions:
            self.stream_subscriptions[stream_id] = set()
        self.stream_subscriptions[stream_id].add(connection_id)

        logger.info(
            "Stream subscription created",
            extra={
                "connection_id": connection_id,
                "stream_id": stream_id,
                "stream_type": stream_type.value,
                "params": params,
                "stream_subscribers": len(self.stream_subscriptions[stream_id]),
            },
        )

        return True

    async def unsubscribe(self, connection_id: str, stream_id: str) -> bool:
        """
        Unsubscribe connection from a stream.

        Args:
            connection_id: Connection identifier.
            stream_id: Stream identifier.

        Returns:
            bool: True if unsubscription successful.
        """
        if connection_id not in self.connections:
            return False

        connection = self.connections[connection_id]
        connection.remove_subscription(stream_id)

        await self._remove_from_stream(connection_id, stream_id)

        return True

    async def _remove_from_stream(self, connection_id: str, stream_id: str) -> None:
        """Remove connection from stream subscription mapping."""
        if stream_id in self.stream_subscriptions:
            self.stream_subscriptions[stream_id].discard(connection_id)
            if not self.stream_subscriptions[stream_id]:
                # No more subscribers, remove stream
                del self.stream_subscriptions[stream_id]

    async def send_message(
        self,
        connection_id: str,
        message: dict[str, Any],
        apply_backpressure: bool = True,
    ) -> bool:
        """
        Send message to a specific connection.

        Args:
            connection_id: Connection identifier.
            message: Message dictionary to send.
            apply_backpressure: Whether to apply backpressure strategy.

        Returns:
            bool: True if message sent successfully.
        """
        if connection_id not in self.connections:
            return False

        connection = self.connections[connection_id]

        try:
            # Handle backpressure if queue is full
            if apply_backpressure and len(connection.message_queue) >= self.max_queue_size:
                await self._handle_backpressure(connection, message)
            else:
                connection.message_queue.append(message)

            # Try to send immediately if queue was empty
            if len(connection.message_queue) == 1:
                await self._flush_queue(connection)

            return True

        except WebSocketDisconnect:
            await self.disconnect(connection_id)
            return False
        except Exception as e:
            logger.error(
                f"Error sending message: {e}",
                exc_info=True,
                extra={"connection_id": connection_id},
            )
            return False

    async def _handle_backpressure(
        self,
        connection: WSConnectionState,
        message: dict[str, Any],
    ) -> None:
        """Handle backpressure when queue is full."""
        if self.backpressure_strategy == BackpressureStrategy.DROP_OLDEST:
            # Remove oldest message
            connection.message_queue.popleft()
            connection.message_queue.append(message)
            logger.debug(
                "Backpressure: dropped oldest message",
                extra={
                    "connection_id": connection.connection_id,
                    "queue_size": len(connection.message_queue),
                },
            )
        elif self.backpressure_strategy == BackpressureStrategy.DROP_NEWEST:
            # Don't add new message
            logger.debug(
                "Backpressure: dropped newest message",
                extra={
                    "connection_id": connection.connection_id,
                    "queue_size": len(connection.message_queue),
                },
            )
        elif self.backpressure_strategy == BackpressureStrategy.COMPRESS:
            # Compress by sampling (keep every Nth message)
            compressed = list(connection.message_queue)[::2]  # Keep every 2nd
            connection.message_queue.clear()
            connection.message_queue.extend(compressed)
            connection.message_queue.append(message)
            logger.debug(
                "Backpressure: compressed queue",
                extra={
                    "connection_id": connection.connection_id,
                    "queue_size": len(connection.message_queue),
                },
            )

    async def _flush_queue(self, connection: WSConnectionState) -> None:
        """Flush message queue for a connection."""
        while connection.message_queue:
            message = connection.message_queue.popleft()
            try:
                await connection.websocket.send_json(message)
            except WebSocketDisconnect:
                await self.disconnect(connection.connection_id)
                break
            except Exception as e:
                logger.error(
                    f"Error flushing queue: {e}",
                    exc_info=True,
                    extra={"connection_id": connection.connection_id},
                )
                break

    async def broadcast_to_stream(
        self,
        stream_id: str,
        message: dict[str, Any],
    ) -> int:
        """
        Broadcast message to all subscribers of a stream.

        Args:
            stream_id: Stream identifier.
            message: Message dictionary to broadcast.

        Returns:
            Number of connections message was sent to.
        """
        if stream_id not in self.stream_subscriptions:
            return 0

        sent_count = 0
        for connection_id in list(self.stream_subscriptions[stream_id]):
            if await self.send_message(connection_id, message):
                sent_count += 1

        return sent_count

    async def send_heartbeat(self, connection_id: str) -> bool:
        """
        Send heartbeat to connection.

        Args:
            connection_id: Connection identifier.

        Returns:
            bool: True if heartbeat sent successfully.
        """
        if connection_id not in self.connections:
            return False

        connection = self.connections[connection_id]
        heartbeat_msg = {
            "type": WSMessageType.HEARTBEAT.value,
            "timestamp": time.time() * 1000,
        }

        try:
            await connection.websocket.send_json(heartbeat_msg)
            return True
        except WebSocketDisconnect:
            await self.disconnect(connection_id)
            return False
        except Exception as e:
            logger.error(
                f"Error sending heartbeat: {e}",
                exc_info=True,
                extra={"connection_id": connection_id},
            )
            return False

    async def handle_pong(self, connection_id: str) -> None:
        """
        Handle pong response from client.

        Args:
            connection_id: Connection identifier.
        """
        if connection_id not in self.connections:
            return

        connection = self.connections[connection_id]
        connection.update_heartbeat()

    async def start_heartbeat_monitor(self) -> None:
        """Start background task for heartbeat monitoring."""
        if self._heartbeat_task is not None:
            return

        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        logger.info("Heartbeat monitor started")

    async def stop_heartbeat_monitor(self) -> None:
        """Stop heartbeat monitoring."""
        if self._heartbeat_task is not None:
            self._heartbeat_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._heartbeat_task
            self._heartbeat_task = None
            logger.info("Heartbeat monitor stopped")

    async def _heartbeat_loop(self) -> None:
        """Background loop for heartbeat monitoring."""
        while True:
            try:
                await asyncio.sleep(self.heartbeat_interval)

                # Send heartbeats and check timeouts
                for connection_id in list(self.connections.keys()):
                    connection = self.connections.get(connection_id)
                    if connection is None:
                        continue

                    if not connection.is_alive(self.heartbeat_timeout):
                        logger.warning(
                            "Connection timeout, disconnecting",
                            extra={
                                "connection_id": connection_id,
                                "last_heartbeat": connection.last_heartbeat,
                            },
                        )
                        await self.disconnect(connection_id)
                    else:
                        await self.send_heartbeat(connection_id)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in heartbeat loop: {e}", exc_info=True)

    def get_connection_count(self) -> int:
        """Get total number of active connections."""
        return len(self.connections)

    def get_stream_subscriber_count(self, stream_id: str) -> int:
        """Get number of subscribers for a stream."""
        return len(self.stream_subscriptions.get(stream_id, set()))

    def get_stats(self) -> dict[str, Any]:
        """Get connection manager statistics."""
        total_subscriptions = sum(len(subs) for subs in self.stream_subscriptions.values())
        return {
            "total_connections": len(self.connections),
            "authenticated_connections": sum(
                1 for c in self.connections.values() if c.authenticated
            ),
            "total_streams": len(self.stream_subscriptions),
            "total_subscriptions": total_subscriptions,
            "backpressure_strategy": self.backpressure_strategy,
            "max_queue_size": self.max_queue_size,
        }
