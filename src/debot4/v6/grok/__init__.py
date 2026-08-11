"""Direct Grok2API search client for narrative discovery."""

from .client import Grok2ApiClient
from .briefs import (
    CaCarrierStatus,
    CaReference,
    CatalystType,
    EventRole,
    GrokBriefError,
    GrokNarrativeBrief,
    NarrativePhase,
    parse_narrative_brief,
)
from .leads import GrokXLead, extract_x_status_leads
from .models import GrokCitation, GrokSearchAnswer, GrokSearchSource
from .request import (
    DISCOVERY_SEARCH,
    FORMAT_ONLY,
    REALTIME_SEARCH,
    GrokRequestPolicy,
)
from .response import parse_responses_answer
from .prompts import passive_investigation_prompt, proactive_investigation_prompt
from .structured import StructuredNarrativeSearch, search_narrative_brief
from .transport import GrokApiError, UrlLibTransport

__all__ = [
    "CaCarrierStatus",
    "CaReference",
    "CatalystType",
    "EventRole",
    "Grok2ApiClient",
    "GrokApiError",
    "GrokBriefError",
    "GrokCitation",
    "GrokNarrativeBrief",
    "GrokRequestPolicy",
    "GrokSearchAnswer",
    "GrokSearchSource",
    "GrokXLead",
    "NarrativePhase",
    "DISCOVERY_SEARCH",
    "FORMAT_ONLY",
    "REALTIME_SEARCH",
    "StructuredNarrativeSearch",
    "UrlLibTransport",
    "extract_x_status_leads",
    "passive_investigation_prompt",
    "parse_narrative_brief",
    "parse_responses_answer",
    "proactive_investigation_prompt",
    "search_narrative_brief",
]
