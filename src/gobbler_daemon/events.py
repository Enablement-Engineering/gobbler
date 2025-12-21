"""Event bus for pub/sub messaging within the daemon.

Provides an asyncio-based event bus for distributing events like:
- Conversion started, completed, failed
- Service health changes
- Plugin loaded/unloaded
- Configuration reloaded
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class EventType(Enum):
    """Event types for the event bus."""

    # Conversion events
    CONVERSION_STARTED = "conversion.started"
    CONVERSION_PROGRESS = "conversion.progress"
    CONVERSION_COMPLETED = "conversion.completed"
    CONVERSION_FAILED = "conversion.failed"

    # Service events
    SERVICE_HEALTH_CHANGED = "service.health_changed"
    SERVICE_STARTED = "service.started"
    SERVICE_STOPPED = "service.stopped"

    # Plugin events
    PLUGIN_LOADED = "plugin.loaded"
    PLUGIN_UNLOADED = "plugin.unloaded"
    PLUGIN_ERROR = "plugin.error"

    # Configuration events
    CONFIG_RELOADED = "config.reloaded"

    # Daemon events
    DAEMON_STARTED = "daemon.started"
    DAEMON_STOPPING = "daemon.stopping"
    DAEMON_STOPPED = "daemon.stopped"


@dataclass
class Event:
    """Event data structure."""

    type: EventType
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    source: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary."""
        return {
            "type": self.type.value,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
        }


class EventBus:
    """
    Event bus for pub/sub messaging within the daemon.

    Uses asyncio queues for in-process event distribution.
    Subscribers receive events asynchronously via queues.
    """

    def __init__(self, max_queue_size: int = 100) -> None:
        """
        Initialize event bus.

        Args:
            max_queue_size: Maximum size of subscriber queues
        """
        self.max_queue_size = max_queue_size
        self._subscribers: Dict[EventType, List[asyncio.Queue]] = {}
        self._global_subscribers: List[asyncio.Queue] = []
        self._lock = asyncio.Lock()
        self._running = False

    async def start(self) -> None:
        """Start the event bus."""
        async with self._lock:
            if self._running:
                logger.warning("Event bus already running")
                return

            self._running = True
            logger.info("Event bus started")

    async def stop(self) -> None:
        """Stop the event bus and clear all subscribers."""
        async with self._lock:
            if not self._running:
                return

            self._running = False

            # Clear all subscriber queues
            for queues in self._subscribers.values():
                for queue in queues:
                    # Drain the queue
                    while not queue.empty():
                        try:
                            queue.get_nowait()
                        except asyncio.QueueEmpty:
                            break

            for queue in self._global_subscribers:
                while not queue.empty():
                    try:
                        queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break

            self._subscribers.clear()
            self._global_subscribers.clear()

            logger.info("Event bus stopped")

    async def publish(self, event: Event) -> None:
        """
        Publish an event to all subscribers.

        Args:
            event: Event to publish
        """
        if not self._running:
            logger.warning("Event bus not running, ignoring publish")
            return

        logger.debug(f"Publishing event: {event.type.value} from {event.source}")

        # Publish to type-specific subscribers
        async with self._lock:
            type_subscribers = self._subscribers.get(event.type, [])

            for queue in type_subscribers:
                try:
                    # Non-blocking put, drop event if queue is full
                    queue.put_nowait(event)
                except asyncio.QueueFull:
                    logger.warning(
                        f"Subscriber queue full for {event.type.value}, "
                        "dropping event"
                    )

            # Publish to global subscribers
            for queue in self._global_subscribers:
                try:
                    queue.put_nowait(event)
                except asyncio.QueueFull:
                    logger.warning("Global subscriber queue full, dropping event")

    async def subscribe(
        self, event_type: Optional[EventType] = None
    ) -> asyncio.Queue:
        """
        Subscribe to events.

        Args:
            event_type: Specific event type to subscribe to.
                       If None, subscribes to all events.

        Returns:
            Queue that will receive events
        """
        queue = asyncio.Queue(maxsize=self.max_queue_size)

        async with self._lock:
            if event_type is None:
                # Global subscription
                self._global_subscribers.append(queue)
                logger.debug("Added global event subscriber")
            else:
                # Type-specific subscription
                if event_type not in self._subscribers:
                    self._subscribers[event_type] = []
                self._subscribers[event_type].append(queue)
                logger.debug(f"Added subscriber for {event_type.value}")

        return queue

    async def unsubscribe(
        self, queue: asyncio.Queue, event_type: Optional[EventType] = None
    ) -> None:
        """
        Unsubscribe from events.

        Args:
            queue: Queue to remove
            event_type: Event type to unsubscribe from.
                       If None, removes from global subscribers.
        """
        async with self._lock:
            if event_type is None:
                # Remove from global subscribers
                if queue in self._global_subscribers:
                    self._global_subscribers.remove(queue)
                    logger.debug("Removed global event subscriber")
            else:
                # Remove from type-specific subscribers
                if event_type in self._subscribers:
                    if queue in self._subscribers[event_type]:
                        self._subscribers[event_type].remove(queue)
                        logger.debug(f"Removed subscriber for {event_type.value}")

                    # Clean up empty lists
                    if not self._subscribers[event_type]:
                        del self._subscribers[event_type]

    def create_listener(
        self,
        event_type: Optional[EventType] = None,
        callback: Optional[Callable[[Event], Any]] = None,
    ) -> "EventListener":
        """
        Create an event listener.

        Args:
            event_type: Event type to listen for (None for all events)
            callback: Optional callback to invoke for each event

        Returns:
            EventListener instance
        """
        return EventListener(self, event_type, callback)

    async def emit_conversion_started(
        self, job_id: str, converter: str, source: str = "daemon"
    ) -> None:
        """
        Emit conversion started event.

        Args:
            job_id: Job ID
            converter: Converter type (youtube, audio, etc.)
            source: Event source
        """
        await self.publish(
            Event(
                type=EventType.CONVERSION_STARTED,
                data={"job_id": job_id, "converter": converter},
                source=source,
            )
        )

    async def emit_conversion_completed(
        self, job_id: str, converter: str, result: Any, source: str = "daemon"
    ) -> None:
        """
        Emit conversion completed event.

        Args:
            job_id: Job ID
            converter: Converter type
            result: Conversion result
            source: Event source
        """
        await self.publish(
            Event(
                type=EventType.CONVERSION_COMPLETED,
                data={"job_id": job_id, "converter": converter, "result": result},
                source=source,
            )
        )

    async def emit_conversion_failed(
        self, job_id: str, converter: str, error: str, source: str = "daemon"
    ) -> None:
        """
        Emit conversion failed event.

        Args:
            job_id: Job ID
            converter: Converter type
            error: Error message
            source: Event source
        """
        await self.publish(
            Event(
                type=EventType.CONVERSION_FAILED,
                data={"job_id": job_id, "converter": converter, "error": error},
                source=source,
            )
        )


class EventListener:
    """
    Event listener for consuming events from the bus.

    Can be used as an async context manager or manually started/stopped.
    """

    def __init__(
        self,
        event_bus: EventBus,
        event_type: Optional[EventType] = None,
        callback: Optional[Callable[[Event], Any]] = None,
    ) -> None:
        """
        Initialize event listener.

        Args:
            event_bus: Event bus to listen to
            event_type: Event type to listen for (None for all)
            callback: Optional callback to invoke for each event
        """
        self.event_bus = event_bus
        self.event_type = event_type
        self.callback = callback
        self._queue: Optional[asyncio.Queue] = None
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start listening for events."""
        if self._task:
            logger.warning("Event listener already running")
            return

        self._queue = await self.event_bus.subscribe(self.event_type)
        self._task = asyncio.create_task(self._listen())
        logger.debug(f"Event listener started for {self.event_type}")

    async def stop(self) -> None:
        """Stop listening for events."""
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        if self._queue:
            await self.event_bus.unsubscribe(self._queue, self.event_type)
            self._queue = None

        logger.debug(f"Event listener stopped for {self.event_type}")

    async def _listen(self) -> None:
        """Listen for events and invoke callback."""
        while True:
            try:
                event = await self._queue.get()
                if self.callback:
                    try:
                        result = self.callback(event)
                        # Handle both sync and async callbacks
                        if asyncio.iscoroutine(result):
                            await result
                    except Exception as e:
                        logger.error(
                            f"Error in event listener callback: {e}", exc_info=True
                        )
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in event listener: {e}", exc_info=True)

    async def __aenter__(self) -> "EventListener":
        """Enter async context manager."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit async context manager."""
        await self.stop()
