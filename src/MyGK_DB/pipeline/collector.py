"""Collector agents and source normalization."""

from __future__ import annotations

import base64
import html
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any

import feedparser
import httpx

from MyGK_DB.knowledge_contract import make_raw_batch, normalize_timestamp, utc_now

from .source_registry import DEFAULT_GITHUB_SOURCE, SourceConfig, load_source_registry, select_sources

logger = logging.getLogger(__name__)


def _headers(token: str = "") -> dict[str, str]:
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"token {token}"
    return headers


def _is_ai_related(repo: dict[str, Any], keywords: list[str]) -> bool:
    text = " ".join(
        [
            str(repo.get("full_name", "")),
            str(repo.get("description", "")),
            " ".join(str(topic) for topic in repo.get("topics", []) or []),
        ]
    ).lower()
    return any(keyword.lower() in text for keyword in keywords)


def _readme_excerpt(client: httpx.Client, repo_full_name: str, headers: dict[str, str]) -> str:
    url = f"https://api.github.com/repos/{repo_full_name}/readme"
    try:
        response = client.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        content = data.get("content", "")
        if not content:
            return ""
        decoded = base64.b64decode(content).decode("utf-8", errors="ignore")
    except (httpx.HTTPError, ValueError, TypeError):
        return ""

    text = re.sub(r"<[^>]+>", " ", decoded)
    text = re.sub(r"[#*_`>\[\]()]|\s+", " ", text).strip()
    return text[:500]


def collect_github(
    limit: int = 10,
    *,
    source: SourceConfig = DEFAULT_GITHUB_SOURCE,
    token: str = "",
    include_readme: bool = True,
) -> list[dict[str, Any]]:
    """Collect AI-related repositories from GitHub Search."""
    if limit <= 0:
        return []
    headers = _headers(token)
    one_week_ago = (
        datetime.now(timezone.utc) - timedelta(days=source.pushed_within_days)
    ).strftime("%Y-%m-%d")
    keyword_query = " OR ".join(
        f'"{keyword}"' if " " in keyword else keyword
        for keyword in (source.query_keywords or source.keywords or ["ai", "agent", "llm"])
    )
    query = f"{keyword_query} stars:>{source.min_stars} pushed:>{one_week_ago}"
    params = {
        "q": query,
        "sort": "stars",
        "order": "desc",
        "per_page": min(max(limit * 2, limit), 30),
    }

    results: list[dict[str, Any]] = []
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get("https://api.github.com/search/repositories", params=params, headers=headers)
            response.raise_for_status()
            data = response.json()
            for repo in data.get("items", []):
                if len(results) >= limit:
                    break
                if repo.get("fork"):
                    continue
                description = repo.get("description") or ""
                if not description.strip():
                    continue
                if not _is_ai_related(repo, source.query_keywords or source.keywords):
                    continue

                now = utc_now()
                item = {
                    "id": repo["full_name"],
                    "title": repo["full_name"],
                    "source": "github-trending",
                    "description": description,
                    "url": repo["html_url"],
                    "author": repo["owner"]["login"],
                    "stars": repo.get("stargazers_count", 0),
                    "language": repo.get("language", ""),
                    "topics": repo.get("topics", []),
                    "created_at": normalize_timestamp(repo.get("created_at"), fallback=now),
                    "updated_at": normalize_timestamp(repo.get("updated_at") or repo.get("pushed_at"), fallback=now),
                    "collected_at": now,
                    "source_trust_tier": source.trust_tier,
                    "source_quality_weight": source.quality_weight,
                }
                if include_readme and len(results) < source.include_readme_top_n:
                    excerpt = _readme_excerpt(client, repo["full_name"], headers)
                    if excerpt:
                        item["context_excerpt"] = excerpt
                results.append(item)

        logger.info("GitHub collected %d items", len(results))
    except httpx.HTTPError as exc:
        logger.error("GitHub API failed: %s", exc)

    return results


def collect_rss(limit: int = 10, *, sources: list[SourceConfig] | None = None) -> list[dict[str, Any]]:
    """Collect items from enabled RSS/Atom sources."""
    if limit <= 0:
        return []
    selected_sources = sources or [entry for entry in load_source_registry() if entry.type == "rss" and entry.enabled]
    results: list[dict[str, Any]] = []

    with httpx.Client(timeout=20.0, follow_redirects=True) as client:
        for source in selected_sources:
            if len(results) >= limit:
                break
            source_limit = min(limit - len(results), source.limit or limit)
            if source_limit <= 0:
                continue
            try:
                response = client.get(source.url, timeout=source.fetch_timeout_seconds)
                response.raise_for_status()
            except httpx.HTTPError as exc:
                logger.warning("RSS source [%s] failed: %s", source.name, exc)
                continue

            parsed = feedparser.parse(response.content)
            count = 0
            for entry in parsed.entries:
                if count >= source_limit or len(results) >= limit:
                    break
                title = html.unescape(str(entry.get("title", "")).strip())
                link = str(entry.get("link", "")).strip()
                if not title or not link:
                    continue
                summary = html.unescape(str(entry.get("summary") or entry.get("description") or ""))
                summary = re.sub(r"<[^>]+>", " ", summary)
                summary = re.sub(r"\s+", " ", summary).strip()
                published = entry.get("published") or entry.get("updated")
                now = utc_now()
                results.append(
                    {
                        "id": link,
                        "title": title,
                        "source": source.id,
                        "url": link,
                        "author": str(entry.get("author") or source.name),
                        "description": summary,
                        "category": source.category,
                        "published_at": normalize_timestamp(published, fallback=now),
                        "collected_at": normalize_timestamp(now),
                        "source_name": source.name,
                        "source_trust_tier": source.trust_tier,
                        "source_quality_weight": source.quality_weight,
                    }
                )
                count += 1
            logger.info("RSS [%s] collected %d items", source.name, count)

    logger.info("RSS collected %d items", len(results))
    return results


def collect_source(source: str | SourceConfig, limit: int = 10) -> dict[str, Any]:
    """Collect one logical source and return a contract raw batch."""
    if isinstance(source, SourceConfig):
        source_config = source
    else:
        matches = select_sources([source])
        source_config = matches[0] if matches else DEFAULT_GITHUB_SOURCE

    errors: list[dict[str, Any]] = []
    if source_config.type == "github":
        items = collect_github(limit, source=source_config)
    elif source_config.type == "rss":
        items = collect_rss(limit, sources=[source_config])
    else:
        items = []
        errors.append({"source": source_config.id, "reason": f"unsupported source type: {source_config.type}"})

    return make_raw_batch(
        source=source_config.id,
        items=items,
        query=f"source={source_config.id} limit={limit}",
        errors=errors or None,
    )


def collect_sources(sources: list[str], limit: int) -> list[dict[str, Any]]:
    """Collect all requested sources into raw batches."""
    return [collect_source(source, limit) for source in select_sources(sources)]
