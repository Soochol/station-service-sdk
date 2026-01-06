"""Protocol adapters for custom output formats.

Provides base classes for implementing custom output protocols
beyond the default JSON Lines format.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any, Callable

from station_service_sdk.sdk_types import MessageType


class ProtocolAdapter(ABC):
    """Abstract base class for protocol adapters.

    Implement this class to create custom output protocols
    for sequence communication (e.g., MQTT, WebSocket, gRPC).

    Example:
        >>> class MQTTAdapter(ProtocolAdapter):
        ...     async def connect(self):
        ...         self.client = await aiomqtt.connect(self.broker)
        ...
        ...     async def send_message(self, msg_type, data):
        ...         topic = f"sequences/{msg_type.value}"
        ...         await self.client.publish(topic, json.dumps(data))
    """

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to the output destination.

        Should be called before sending any messages.
        """
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to the output destination.

        Should be called when sequence execution completes.
        """
        ...

    @abstractmethod
    async def send_message(
        self,
        msg_type: MessageType,
        data: dict[str, Any],
    ) -> None:
        """Send a message to the output destination.

        Args:
            msg_type: Type of message (LOG, STEP_START, etc.)
            data: Message data to send
        """
        ...

    async def on_error(self, error: Exception) -> None:
        """Handle errors in the protocol adapter.

        Override to implement custom error handling.

        Args:
            error: The exception that occurred
        """
        pass


class JsonLinesAdapter(ProtocolAdapter):
    """JSON Lines protocol adapter (default).

    Outputs messages as JSON Lines to stdout or a file.
    """

    def __init__(
        self,
        output: Any = None,
        execution_id: str = "",
    ):
        """Initialize JSON Lines adapter.

        Args:
            output: Output stream (default: stdout)
            execution_id: Execution identifier for messages
        """
        import sys

        self.output = output or sys.stdout
        self.execution_id = execution_id
        self._connected = False

    async def connect(self) -> None:
        """Mark as connected."""
        self._connected = True

    async def disconnect(self) -> None:
        """Flush and mark as disconnected."""
        if hasattr(self.output, "flush"):
            self.output.flush()
        self._connected = False

    async def send_message(
        self,
        msg_type: MessageType,
        data: dict[str, Any],
    ) -> None:
        """Send message as JSON line.

        Args:
            msg_type: Message type
            data: Message data
        """
        from datetime import datetime

        message = {
            "type": msg_type.value if hasattr(msg_type, "value") else str(msg_type),
            "timestamp": datetime.now().isoformat(),
            "execution_id": self.execution_id,
            "data": data,
        }

        line = json.dumps(message, default=str)
        self.output.write(line + "\n")

        if hasattr(self.output, "flush"):
            self.output.flush()


class WebSocketAdapter(ProtocolAdapter):
    """WebSocket protocol adapter.

    Sends messages over WebSocket connection.
    Requires websockets package.
    """

    def __init__(
        self,
        url: str,
        execution_id: str = "",
        reconnect: bool = True,
        reconnect_delay: float = 1.0,
    ):
        """Initialize WebSocket adapter.

        Args:
            url: WebSocket URL (ws:// or wss://)
            execution_id: Execution identifier
            reconnect: Whether to auto-reconnect on disconnect
            reconnect_delay: Delay between reconnection attempts
        """
        self.url = url
        self.execution_id = execution_id
        self.reconnect = reconnect
        self.reconnect_delay = reconnect_delay
        self._ws: Any = None

    async def connect(self) -> None:
        """Establish WebSocket connection."""
        try:
            import websockets

            self._ws = await websockets.connect(self.url)
        except ImportError:
            raise ImportError(
                "websockets package required. Install with: pip install websockets"
            )

    async def disconnect(self) -> None:
        """Close WebSocket connection."""
        if self._ws:
            await self._ws.close()
            self._ws = None

    async def send_message(
        self,
        msg_type: MessageType,
        data: dict[str, Any],
    ) -> None:
        """Send message over WebSocket.

        Args:
            msg_type: Message type
            data: Message data
        """
        from datetime import datetime

        if self._ws is None:
            if self.reconnect:
                await self.connect()
            else:
                raise RuntimeError("WebSocket not connected")

        message = {
            "type": msg_type.value if hasattr(msg_type, "value") else str(msg_type),
            "timestamp": datetime.now().isoformat(),
            "execution_id": self.execution_id,
            "data": data,
        }

        try:
            await self._ws.send(json.dumps(message, default=str))
        except Exception as e:
            if self.reconnect:
                import asyncio

                await asyncio.sleep(self.reconnect_delay)
                await self.connect()
                await self._ws.send(json.dumps(message, default=str))
            else:
                raise e


class CallbackAdapter(ProtocolAdapter):
    """Callback-based protocol adapter.

    Calls a user-provided function for each message.
    Useful for testing or custom integrations.
    """

    def __init__(
        self,
        callback: Callable[[MessageType, dict[str, Any]], None],
        async_callback: Callable[[MessageType, dict[str, Any]], Any] | None = None,
    ):
        """Initialize callback adapter.

        Args:
            callback: Sync callback function
            async_callback: Optional async callback function
        """
        self.callback = callback
        self.async_callback = async_callback

    async def connect(self) -> None:
        """No-op for callback adapter."""
        pass

    async def disconnect(self) -> None:
        """No-op for callback adapter."""
        pass

    async def send_message(
        self,
        msg_type: MessageType,
        data: dict[str, Any],
    ) -> None:
        """Call the callback with message.

        Args:
            msg_type: Message type
            data: Message data
        """
        if self.async_callback:
            await self.async_callback(msg_type, data)
        else:
            self.callback(msg_type, data)


class BufferedAdapter(ProtocolAdapter):
    """Buffered protocol adapter.

    Buffers messages and flushes them periodically or on demand.
    Wraps another adapter to add buffering capability.
    """

    def __init__(
        self,
        inner: ProtocolAdapter,
        buffer_size: int = 100,
        flush_interval: float = 5.0,
    ):
        """Initialize buffered adapter.

        Args:
            inner: Inner protocol adapter
            buffer_size: Max buffer size before auto-flush
            flush_interval: Auto-flush interval in seconds
        """
        self.inner = inner
        self.buffer_size = buffer_size
        self.flush_interval = flush_interval
        self._buffer: list[tuple[MessageType, dict[str, Any]]] = []
        self._flush_task: Any = None

    async def connect(self) -> None:
        """Connect inner adapter and start flush timer."""
        await self.inner.connect()

        if self.flush_interval > 0:
            import asyncio

            async def flush_loop() -> None:
                while True:
                    await asyncio.sleep(self.flush_interval)
                    await self.flush()

            self._flush_task = asyncio.create_task(flush_loop())

    async def disconnect(self) -> None:
        """Flush buffer and disconnect inner adapter."""
        if self._flush_task:
            self._flush_task.cancel()
            self._flush_task = None

        await self.flush()
        await self.inner.disconnect()

    async def send_message(
        self,
        msg_type: MessageType,
        data: dict[str, Any],
    ) -> None:
        """Buffer message for later sending.

        Args:
            msg_type: Message type
            data: Message data
        """
        self._buffer.append((msg_type, data))

        if len(self._buffer) >= self.buffer_size:
            await self.flush()

    async def flush(self) -> None:
        """Flush buffered messages to inner adapter."""
        if not self._buffer:
            return

        messages = self._buffer.copy()
        self._buffer.clear()

        for msg_type, data in messages:
            try:
                await self.inner.send_message(msg_type, data)
            except Exception:
                # Re-buffer failed messages
                self._buffer.append((msg_type, data))


class AdapterFactory:
    """Factory for creating protocol adapters.

    Provides a registry of adapter types and factory methods.

    Example:
        >>> factory = AdapterFactory()
        >>> factory.register("mqtt", MQTTAdapter)
        >>> adapter = factory.create("mqtt", broker="localhost:1883")
    """

    def __init__(self) -> None:
        """Initialize factory with default adapters."""
        self._adapters: dict[str, type[ProtocolAdapter]] = {
            "jsonlines": JsonLinesAdapter,
            "websocket": WebSocketAdapter,
            "callback": CallbackAdapter,
        }

    def register(
        self,
        name: str,
        adapter_class: type[ProtocolAdapter],
    ) -> None:
        """Register an adapter type.

        Args:
            name: Adapter name
            adapter_class: Adapter class
        """
        self._adapters[name] = adapter_class

    def create(
        self,
        name: str,
        **kwargs: Any,
    ) -> ProtocolAdapter:
        """Create an adapter instance.

        Args:
            name: Adapter name
            **kwargs: Adapter constructor arguments

        Returns:
            Configured adapter instance

        Raises:
            ValueError: If adapter not found
        """
        if name not in self._adapters:
            available = list(self._adapters.keys())
            raise ValueError(f"Unknown adapter '{name}'. Available: {available}")

        return self._adapters[name](**kwargs)

    def list_adapters(self) -> list[str]:
        """List available adapter types.

        Returns:
            List of adapter names
        """
        return list(self._adapters.keys())
