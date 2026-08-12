"""Reviewed BOT authority network used for baseline setup and identity checks."""

from .models import AuthorityNode


BOT_AUTHORITY_NODES = (
    AuthorityNode("bot", "2085838061347217408", "Grok Bot", "official_product", "https://x.com/bot"),
    AuthorityNode("grok", "1720665183188922368", "Grok", "official_product", "https://x.com/grok"),
    AuthorityNode("X", "783214", "X", "official_platform", "https://x.com/X"),
    AuthorityNode("SpaceXAI", "1661523610111193088", "SpaceXAI", "official_company", "https://x.com/SpaceXAI"),
    AuthorityNode("xai", "2074186776130859008", "xAI", "migrated_official_identity", "https://x.com/xai"),
    AuthorityNode("elonmusk", "44196397", "Elon Musk", "founder_and_platform_owner", "https://x.com/elonmusk"),
    AuthorityNode("SpaceX", "34743251", "SpaceX", "official_company", "https://x.com/SpaceX"),
)

BOT_RELATION_TARGET_IDS = frozenset(node.user_id for node in BOT_AUTHORITY_NODES)
