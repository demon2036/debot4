"""Aggregate of reviewed monitoring targets, split by responsibility."""

from .actor_catalog_asia import ASIA_ACTORS
from .actor_catalog_authorities import AUTHORITY_ACTORS
from .actor_catalog_global import GLOBAL_KOL_ACTORS
from .actor_catalog_types import CatalogActor


DEFAULT_ACTOR_CATALOG = AUTHORITY_ACTORS + ASIA_ACTORS + GLOBAL_KOL_ACTORS

__all__ = ["CatalogActor", "DEFAULT_ACTOR_CATALOG"]
