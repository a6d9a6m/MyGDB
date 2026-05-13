"""Shared contract helpers for the MyGK_DB knowledge base."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "knowledge" / "raw"
ARTICLES_DIR = PROJECT_ROOT / "knowledge" / "articles"

SCORE_BREAKDOWN_KEYS = (
    "tech_depth",
    "practical_value",
    "timeliness",
    "community_heat",
    "domain_match",
)

SCORE_BREAKDOWN_WEIGHTS = {
    "tech_depth": 0.25,
    "practical_value": 0.30,
    "timeliness": 0.20,
    "community_heat": 0.15,
    "domain_match": 0.10,
}

ARTICLE_REQUIRED_FIELDS: dict[str, type] = {
    "id": str,
    "title": str,
    "source": str,
    "source_id": str,
    "url": str,
    "summary": str,
    "tags": list,
    "relevance_score": (int, float),  # type: ignore[assignment]
    "collected_at": str,
    "analyzed_at": str,
    "organized_at": str,
    "status": str,
}

ARTICLE_ID_PATTERN = re.compile(r"^kb-\d{4}-\d{2}-\d{2}-\d{3}$")
TAG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
URL_PATTERN = re.compile(r"^https?://\S+$")
ISO_UTC_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


@dataclass
class PublishResult:
    """Result of publishing analyzed items into the article store."""

    saved_files: list[Path]
    published_articles: list[dict[str, Any]]
    filtered_items: list[dict[str, Any]]
    index_file: Path | None = None
    filtered_log_file: Path | None = None


def utc_now() -> str:
    """Return a compact ISO 8601 UTC timestamp accepted by the contract."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize_timestamp(value: Any, fallback: str | None = None) -> str:
    """Normalize common timestamp values to `YYYY-MM-DDTHH:mm:ssZ`."""
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str) and value.strip():
        raw = value.strip()
        try:
            if raw.endswith("Z"):
                dt = datetime.fromisoformat(raw[:-1] + "+00:00")
            elif re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
                dt = datetime.fromisoformat(raw + "T00:00:00+00:00")
            else:
                dt = datetime.fromisoformat(raw)
        except ValueError:
            return fallback or utc_now()
    else:
        return fallback or utc_now()

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc).replace(microsecond=0)
    return dt.isoformat().replace("+00:00", "Z")


def date_from_timestamp(value: str) -> str:
    return normalize_timestamp(value).split("T", 1)[0]


def json_dump(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def clamp_score(value: Any, default: float = 0.0) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        score = default
    return round(max(0.0, min(1.0, score)), 2)


def relevance_from_legacy_score(value: Any, default: float = 0.6) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return default
    if numeric > 1:
        numeric = numeric / 10
    return clamp_score(numeric, default=default)


def sanitize_tags(tags: Any, *, min_count: int = 0) -> list[str]:
    if not isinstance(tags, list):
        tags = [tags] if tags else []

    normalized: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        if not isinstance(tag, str):
            continue
        candidate = re.sub(r"[^a-z0-9]+", "-", tag.strip().lower()).strip("-")
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        normalized.append(candidate)

    defaults = ("llm", "ai")
    for tag in defaults:
        if len(normalized) >= min_count:
            break
        if tag not in seen:
            seen.add(tag)
            normalized.append(tag)

    return normalized


def slugify(title: str, fallback: str = "article") -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    return slug[:80].strip("-") or fallback


def normalize_score_breakdown(value: Any, relevance_score: float) -> dict[str, float]:
    if isinstance(value, dict):
        breakdown = {
            key: clamp_score(value.get(key), default=relevance_score)
            for key in SCORE_BREAKDOWN_KEYS
        }
    else:
        breakdown = {key: relevance_score for key in SCORE_BREAKDOWN_KEYS}
    return breakdown


def weighted_relevance(breakdown: dict[str, float]) -> float:
    total = sum(breakdown[key] * SCORE_BREAKDOWN_WEIGHTS[key] for key in SCORE_BREAKDOWN_KEYS)
    return clamp_score(total)


def normalize_raw_item(item: dict[str, Any], source: str) -> dict[str, Any]:
    now = utc_now()
    url = item.get("url") or item.get("source_url") or item.get("html_url") or ""
    description = item.get("description") or item.get("raw_description") or ""
    source_id = item.get("source_id") or item.get("id") or url

    normalized = {
        **item,
        "id": str(source_id),
        "title": str(item.get("title") or source_id or url),
        "description": str(description or ""),
        "url": str(url),
        "source": str(item.get("source") or source),
        "collected_at": normalize_timestamp(item.get("collected_at"), fallback=now),
    }
    normalized.pop("source_url", None)
    normalized.pop("raw_description", None)
    return normalized


def make_raw_batch(
    *,
    source: str,
    items: list[dict[str, Any]],
    query: str = "",
    collected_at: str | None = None,
    errors: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    timestamp = normalize_timestamp(collected_at, fallback=utc_now())
    normalized_items = [normalize_raw_item(item, source) for item in items]
    batch: dict[str, Any] = {
        "source": source,
        "collected_at": timestamp,
        "count": len(normalized_items),
        "items": normalized_items,
    }
    if query:
        batch["query"] = query
    if errors:
        batch["errors"] = errors
    return batch


def normalize_analyzed_item(item: dict[str, Any]) -> dict[str, Any]:
    now = utc_now()
    url = item.get("url") or item.get("source_url") or ""
    description = item.get("description") or item.get("raw_description") or ""
    relevance = item.get("relevance_score")
    if relevance is None:
        relevance = relevance_from_legacy_score(item.get("score"), default=0.6)
    relevance_score = clamp_score(relevance, default=0.6)
    breakdown = normalize_score_breakdown(item.get("score_breakdown"), relevance_score)
    if "score_breakdown" in item and item.get("relevance_score") is None:
        relevance_score = weighted_relevance(breakdown)

    normalized = {
        **item,
        "id": str(item.get("id") or item.get("source_id") or url),
        "title": str(item.get("title") or item.get("id") or url),
        "description": str(description or ""),
        "url": str(url),
        "source": str(item.get("source") or "unknown"),
        "summary": str(item.get("summary") or description or ""),
        "tags": sanitize_tags(item.get("tags"), min_count=0),
        "relevance_score": relevance_score,
        "score_breakdown": breakdown,
        "collected_at": normalize_timestamp(item.get("collected_at"), fallback=now),
        "analyzed_at": normalize_timestamp(item.get("analyzed_at"), fallback=now),
    }
    normalized.pop("source_url", None)
    normalized.pop("raw_description", None)
    return normalized


def validate_analyzed_item(item: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in ("id", "title", "url", "summary", "relevance_score", "tags", "analyzed_at"):
        if field not in item:
            errors.append(f"missing field: {field}")

    if item.get("url") and not URL_PATTERN.match(str(item["url"])):
        errors.append("invalid url")
    if not isinstance(item.get("tags"), list) or not item.get("tags"):
        errors.append("tags must be a non-empty list")
    if len(str(item.get("summary", "")).strip()) < 20:
        errors.append("summary is too short")

    score = item.get("relevance_score")
    if not isinstance(score, (int, float)) or not (0 <= float(score) <= 1):
        errors.append("relevance_score must be between 0 and 1")

    return errors


def _existing_article_files(articles_dir: Path) -> list[Path]:
    return [
        path
        for path in sorted(articles_dir.glob("*.json"))
        if path.name != "index.json"
    ]


def load_article_files(articles_dir: Path = ARTICLES_DIR) -> list[tuple[Path, dict[str, Any]]]:
    articles: list[tuple[Path, dict[str, Any]]] = []
    if not articles_dir.exists():
        return articles
    for path in _existing_article_files(articles_dir):
        try:
            articles.append((path, json.loads(path.read_text(encoding="utf-8"))))
        except (json.JSONDecodeError, OSError):
            continue
    return articles


def next_article_id(existing_articles: list[dict[str, Any]], date: str, used_ids: set[str]) -> str:
    max_sequence = 0
    prefix = f"kb-{date}-"
    for article in existing_articles:
        article_id = str(article.get("id", ""))
        if not article_id.startswith(prefix):
            continue
        try:
            max_sequence = max(max_sequence, int(article_id.rsplit("-", 1)[1]))
        except (IndexError, ValueError):
            continue
    sequence = max_sequence + 1
    while True:
        candidate = f"{prefix}{sequence:03d}"
        if candidate not in used_ids:
            used_ids.add(candidate)
            return candidate
        sequence += 1


def unique_article_path(articles_dir: Path, date: str, slug: str, used_paths: set[Path]) -> Path:
    candidate = articles_dir / f"{date}-{slug}.json"
    if candidate not in used_paths and not candidate.exists():
        used_paths.add(candidate)
        return candidate

    sequence = 2
    while True:
        candidate = articles_dir / f"{date}-{slug}-{sequence}.json"
        if candidate not in used_paths and not candidate.exists():
            used_paths.add(candidate)
            return candidate
        sequence += 1


def build_article(item: dict[str, Any], article_id: str, organized_at: str) -> dict[str, Any]:
    return {
        "id": article_id,
        "title": item["title"],
        "source": item.get("source", "unknown"),
        "source_id": item["id"],
        "url": item["url"],
        "summary": item["summary"],
        "tags": sanitize_tags(item.get("tags"), min_count=2),
        "relevance_score": clamp_score(item.get("relevance_score"), default=0.0),
        "collected_at": normalize_timestamp(item.get("collected_at"), fallback=organized_at),
        "analyzed_at": normalize_timestamp(item.get("analyzed_at"), fallback=organized_at),
        "organized_at": normalize_timestamp(organized_at),
        "status": "published",
    }


def validate_article_contract(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field_name, field_type in ARTICLE_REQUIRED_FIELDS.items():
        if field_name not in data:
            errors.append(f"缺少必填字段: {field_name}")
            continue
        expected = field_type
        if not isinstance(data[field_name], expected):
            if field_name == "relevance_score" and isinstance(data[field_name], int):
                continue
            errors.append(f"字段类型错误: {field_name}")

    if errors:
        return errors

    if not ARTICLE_ID_PATTERN.match(data["id"]):
        errors.append(f"ID 格式错误: {data['id']}")
    if not data["title"].strip():
        errors.append("标题不能为空")
    if not URL_PATTERN.match(data["url"]):
        errors.append(f"URL 格式错误: {data['url']}")
    if len(data["summary"].strip()) < 20:
        errors.append("摘要太短")
    if not (0 <= float(data["relevance_score"]) <= 1):
        errors.append("relevance_score 超出范围")
    if data["status"] != "published":
        errors.append("status 必须为 published")

    for field in ("collected_at", "analyzed_at", "organized_at"):
        if not ISO_UTC_PATTERN.match(data[field]):
            errors.append(f"时间格式错误: {field}")

    if not data["tags"]:
        errors.append("至少需要 1 个标签")
    for tag in data["tags"]:
        if not isinstance(tag, str) or not TAG_PATTERN.match(tag):
            errors.append(f"标签格式错误: {tag!r}")

    return errors


def article_index_entry(path: Path, article: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": article["id"],
        "title": article["title"],
        "file": path.name,
        "tags": article["tags"],
        "relevance_score": article["relevance_score"],
        "organized_at": article["organized_at"],
    }


def rebuild_index(articles_dir: Path = ARTICLES_DIR, *, now: str | None = None) -> dict[str, Any]:
    entries = [
        article_index_entry(path, article)
        for path, article in load_article_files(articles_dir)
        if not validate_article_contract(article)
    ]
    entries.sort(key=lambda entry: entry["organized_at"], reverse=True)
    index = {
        "last_updated": normalize_timestamp(now, fallback=utc_now()),
        "total_count": len(entries),
        "entries": entries,
    }
    json_dump(articles_dir / "index.json", index)
    return index


def validate_index_contract(index: dict[str, Any], articles_dir: Path = ARTICLES_DIR) -> list[str]:
    errors: list[str] = []
    if not isinstance(index.get("last_updated"), str) or not ISO_UTC_PATTERN.match(index["last_updated"]):
        errors.append("index.last_updated 时间格式错误")
    if not isinstance(index.get("total_count"), int):
        errors.append("index.total_count 必须为整数")
    if not isinstance(index.get("entries"), list):
        errors.append("index.entries 必须为数组")
        return errors

    article_files = {
        path.name
        for path, article in load_article_files(articles_dir)
        if not validate_article_contract(article)
    }
    if index.get("total_count") != len(article_files):
        errors.append("index.total_count 与已发布文章数不一致")

    seen_ids: set[str] = set()
    seen_files: set[str] = set()
    organized_values: list[str] = []
    for entry in index["entries"]:
        if not isinstance(entry, dict):
            errors.append("index.entries 包含非对象条目")
            continue
        for field in ("id", "title", "file", "tags", "relevance_score", "organized_at"):
            if field not in entry:
                errors.append(f"index entry 缺少字段: {field}")
        if entry.get("id") in seen_ids:
            errors.append(f"index entry 重复 id: {entry.get('id')}")
        seen_ids.add(str(entry.get("id")))
        if entry.get("file") in seen_files:
            errors.append(f"index entry 重复 file: {entry.get('file')}")
        seen_files.add(str(entry.get("file")))
        if entry.get("file") not in article_files:
            errors.append(f"index entry 指向不存在文章: {entry.get('file')}")
        if isinstance(entry.get("organized_at"), str):
            organized_values.append(entry["organized_at"])

    if organized_values != sorted(organized_values, reverse=True):
        errors.append("index.entries 未按 organized_at 降序排列")

    return errors


def publish_analyzed_items(
    items: list[dict[str, Any]],
    *,
    articles_dir: Path = ARTICLES_DIR,
    raw_dir: Path = RAW_DIR,
    min_relevance: float = 0.60,
    dry_run: bool = False,
    now: str | None = None,
) -> PublishResult:
    organized_at = normalize_timestamp(now, fallback=utc_now())
    publish_date = date_from_timestamp(organized_at)
    articles_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)

    existing_pairs = load_article_files(articles_dir)
    existing_articles = [article for _, article in existing_pairs]
    existing_urls = {str(article.get("url") or article.get("source_url")) for article in existing_articles}
    used_ids = {str(article.get("id")) for article in existing_articles}
    used_paths = {path for path, _ in existing_pairs}

    saved_files: list[Path] = []
    published_articles: list[dict[str, Any]] = []
    filtered_items: list[dict[str, Any]] = []
    seen_urls = set(existing_urls)

    for raw_item in items:
        item = normalize_analyzed_item(raw_item)
        errors = validate_analyzed_item(item)
        if errors:
            filtered_items.append({
                "source_id": item.get("id", raw_item.get("id", "")),
                "title": item.get("title", raw_item.get("title", "")),
                "reason": "incomplete: " + "; ".join(errors),
            })
            continue

        if item["relevance_score"] < min_relevance:
            filtered_items.append({
                "source_id": item["id"],
                "title": item["title"],
                "reason": f"relevance_score below {min_relevance:.2f}",
            })
            continue

        if len(item["tags"]) < 2:
            filtered_items.append({
                "source_id": item["id"],
                "title": item["title"],
                "reason": "fewer than 2 tags",
            })
            continue

        url = item["url"]
        if url in seen_urls:
            filtered_items.append({
                "source_id": item["id"],
                "title": item["title"],
                "reason": "duplicate url",
            })
            continue
        seen_urls.add(url)

        article_date = date_from_timestamp(item["collected_at"])
        article_id = next_article_id(existing_articles + published_articles, article_date, used_ids)
        article = build_article(item, article_id, organized_at)
        path = unique_article_path(articles_dir, article_date, slugify(article["title"]), used_paths)

        if not dry_run:
            json_dump(path, article)
        saved_files.append(path)
        published_articles.append(article)

    filtered_log_file = raw_dir / f"filtered-{publish_date}.json"
    filtered_log = {
        "date": publish_date,
        "filtered_at": organized_at,
        "items": filtered_items,
    }
    index_file: Path | None = None
    if not dry_run:
        json_dump(filtered_log_file, filtered_log)
        rebuild_index(articles_dir, now=organized_at)
        index_file = articles_dir / "index.json"

    return PublishResult(
        saved_files=saved_files,
        published_articles=published_articles,
        filtered_items=filtered_items,
        index_file=index_file,
        filtered_log_file=None if dry_run else filtered_log_file,
    )


def convert_legacy_article(data: dict[str, Any], *, fallback_now: str | None = None) -> dict[str, Any]:
    now = normalize_timestamp(fallback_now, fallback=utc_now())
    collected_at = normalize_timestamp(data.get("collected_at"), fallback=now)
    analyzed_at = normalize_timestamp(data.get("analyzed_at") or data.get("updated_at"), fallback=collected_at)
    organized_at = normalize_timestamp(data.get("organized_at") or data.get("updated_at"), fallback=analyzed_at)
    url = str(data.get("url") or data.get("source_url") or "")
    relevance = data.get("relevance_score")
    if relevance is None:
        relevance = relevance_from_legacy_score(data.get("score"), default=0.6)

    source_id = str(data.get("source_id") or data.get("id") or url)
    article_date = date_from_timestamp(collected_at)
    sequence_match = re.search(r"-(\d{3})$", source_id)
    sequence = sequence_match.group(1) if sequence_match else "001"

    return {
        "id": str(data.get("id")) if ARTICLE_ID_PATTERN.match(str(data.get("id", ""))) else f"kb-{article_date}-{sequence}",
        "title": str(data.get("title") or source_id),
        "source": str(data.get("source") or "unknown"),
        "source_id": source_id,
        "url": url,
        "summary": str(data.get("summary") or data.get("description") or data.get("raw_description") or ""),
        "tags": sanitize_tags(data.get("tags"), min_count=2),
        "relevance_score": clamp_score(relevance, default=0.6),
        "collected_at": collected_at,
        "analyzed_at": analyzed_at,
        "organized_at": organized_at,
        "status": "published",
    }
