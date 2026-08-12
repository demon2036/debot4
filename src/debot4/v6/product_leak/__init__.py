"""Product, website, documentation, and code-diff monitoring."""

from .client import PublicResourceClient, PublicResourceError, PublicResourceTarget
from .monitor import PublicResourceMonitor
from .rules import PublicResourceSnapshot, product_diff_events
from .store import JsonPublicResourceSnapshotStore
from .targets import BOT_PUBLIC_RESOURCES

__all__ = [
    "BOT_PUBLIC_RESOURCES",
    "JsonPublicResourceSnapshotStore",
    "PublicResourceClient",
    "PublicResourceError",
    "PublicResourceMonitor",
    "PublicResourceSnapshot",
    "PublicResourceTarget",
    "product_diff_events",
]
