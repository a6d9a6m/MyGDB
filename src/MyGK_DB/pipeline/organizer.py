"""Organizer and publisher helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from MyGK_DB.knowledge_contract import ARTICLES_DIR, PublishResult, normalize_analyzed_item, publish_analyzed_items


def organize_items(items: list[dict[str, Any]], *, articles_dir: Path = ARTICLES_DIR) -> list[dict[str, Any]]:
    """Deduplicate against current articles and normalize analyzed items."""
    seen_urls: set[str] = set()
    if articles_dir.exists():
        for path in articles_dir.glob("*.json"):
            if path.name == "index.json":
                continue
            try:
                existing = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            url = existing.get("url") or existing.get("source_url")
            if url:
                seen_urls.add(str(url))

    unique: list[dict[str, Any]] = []
    for item in items:
        if item.get("analysis_failed"):
            continue
        url = item.get("url") or item.get("source_url") or ""
        if url in seen_urls:
            continue
        seen_urls.add(str(url))
        unique.append(normalize_analyzed_item(item))
    return unique


def publish_items(items: list[dict[str, Any]], *, dry_run: bool = False) -> PublishResult:
    return publish_analyzed_items(items, dry_run=dry_run)
