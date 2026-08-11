"""Aggregate of reviewed Asia-region monitoring targets."""

from .actor_catalog_asia_other import OTHER_ASIA_ACTORS
from .actor_catalog_china import CHINA_ACTORS
from .actor_catalog_japan import JAPAN_ACTORS
from .actor_catalog_korea import KOREA_ACTORS


ASIA_ACTORS = CHINA_ACTORS + KOREA_ACTORS + JAPAN_ACTORS + OTHER_ASIA_ACTORS
