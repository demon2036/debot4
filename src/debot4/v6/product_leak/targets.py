"""Reviewed public xAI resources relevant to the BOT authority network."""

from .client import PublicResourceTarget


BOT_PUBLIC_RESOURCES = (
    PublicResourceTarget(
        "xai-sitemap", "x:spacexai", "official_company",
        "https://x.ai/sitemap.xml", ("grok bot", "/bot"),
        "https://r.jina.ai/https://x.ai/sitemap.xml",
    ),
    PublicResourceTarget(
        "xai-bot-page", "x:spacexai", "official_company",
        "https://x.ai/bot", ("grok bot", "early beta", "ai teammates"),
        "https://r.jina.ai/https://x.ai/bot",
    ),
    PublicResourceTarget(
        "xai-docs-overview", "x:spacexai", "official_company",
        "https://docs.x.ai/overview", ("grok bot", "bot"),
    ),
    PublicResourceTarget(
        "xai-github-repositories", "x:spacexai", "official_company",
        "https://api.github.com/orgs/xai-org/repos?per_page=100", ("grok", "bot"),
    ),
)
