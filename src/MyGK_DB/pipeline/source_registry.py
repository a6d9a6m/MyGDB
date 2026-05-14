"""Source registry for collector configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


RSS_CONFIG = Path(__file__).parent / "rss" / "rss_sources.yaml"


AI_KEYWORDS = [
    "AI",
    "LLM",
    "agent",
    "large language model",
    "RAG",
    "MCP",
    "model context protocol",
    "agentic",
]


@dataclass(frozen=True)
class SourceConfig:
    """Normalized source registry entry."""

    id: str
    type: str
    name: str
    enabled: bool = True
    category: str = "general"
    trust_tier: str = "medium"
    limit: int | None = None
    keywords: list[str] = field(default_factory=list)
    quality_weight: float = 1.0
    url: str = ""
    parser: str = "rss"
    fetch_timeout_seconds: float = 20.0
    query_keywords: list[str] = field(default_factory=list)
    min_stars: int = 100
    pushed_within_days: int = 7
    include_readme_top_n: int = 5


DEFAULT_GITHUB_SOURCE = SourceConfig(
    id="github-trending",
    type="github",
    name="GitHub Trending",
    category="open-source",
    trust_tier="medium",
    keywords=AI_KEYWORDS,
    query_keywords=AI_KEYWORDS,
    quality_weight=1.0,
    min_stars=100,
    pushed_within_days=7,
    include_readme_top_n=5,
)


def _source_id(name: str) -> str:
    return "rss:" + "-".join(
        part for part in "".join(ch.lower() if ch.isalnum() else "-" for ch in name).split("-") if part
    )


def _load_rss_config(path: Path = RSS_CONFIG) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    sources = data.get("sources", [])
    return sources if isinstance(sources, list) else []


def load_source_registry(path: Path = RSS_CONFIG) -> list[SourceConfig]:
    """Load the configured GitHub and RSS sources."""
    registry = [DEFAULT_GITHUB_SOURCE]
    for entry in _load_rss_config(path):
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name") or entry.get("id") or "rss-source")
        registry.append(
            SourceConfig(
                id=str(entry.get("id") or _source_id(name)),
                type=str(entry.get("type") or "rss"),
                name=name,
                enabled=bool(entry.get("enabled", True)),
                category=str(entry.get("category") or "general"),
                trust_tier=str(entry.get("trust_tier") or "medium"),
                limit=entry.get("limit"),
                keywords=list(entry.get("keywords") or AI_KEYWORDS),
                quality_weight=float(entry.get("quality_weight", 1.0)),
                url=str(entry.get("url") or ""),
                parser=str(entry.get("parser") or "rss"),
                fetch_timeout_seconds=float(entry.get("fetch_timeout_seconds", 20.0)),
            )
        )
    return registry


def select_sources(sources: list[str] | None, *, registry: list[SourceConfig] | None = None) -> list[SourceConfig]:
    """Resolve CLI source aliases into enabled registry entries."""
    entries = registry or load_source_registry()
    requested = [source.strip() for source in (sources or ["github", "rss"]) if source.strip()]
    selected: list[SourceConfig] = []

    for entry in entries:
        if not entry.enabled:
            continue
        for source in requested:
            if source == "github" and entry.type == "github":
                selected.append(entry)
                break
            if source == "rss" and entry.type == "rss":
                selected.append(entry)
                break
            if source in {entry.id, entry.type, entry.name}:
                selected.append(entry)
                break

    seen: set[str] = set()
    unique: list[SourceConfig] = []
    for entry in selected:
        if entry.id in seen:
            continue
        seen.add(entry.id)
        unique.append(entry)
    return unique
