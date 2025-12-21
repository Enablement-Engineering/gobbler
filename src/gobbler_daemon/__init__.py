"""Gobbler Daemon - Core daemon process for managing Gobbler services.

This package provides the main daemon that manages all Gobbler services,
including converters, job queues, health monitoring, and event distribution.
"""

from .daemon import GobblerDaemon, main_sync as main
from .config import DaemonConfig
from .events import EventBus, Event
from .health import HealthMonitor
from .plugins import PluginManager
from .storage import JobStorage

__all__ = [
    "GobblerDaemon",
    "DaemonConfig",
    "EventBus",
    "Event",
    "HealthMonitor",
    "PluginManager",
    "JobStorage",
    "main",
]

__version__ = "0.1.0"
