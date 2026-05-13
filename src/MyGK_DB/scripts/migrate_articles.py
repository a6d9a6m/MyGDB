"""Migrate legacy article JSON files to the current knowledge-base contract."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from MyGK_DB.knowledge_contract import (
    ARTICLES_DIR,
    RAW_DIR,
    ARTICLE_ID_PATTERN,
    convert_legacy_article,
    date_from_timestamp,
    json_dump,
    rebuild_index,
    slugify,
    utc_now,
    validate_article_contract,
)


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _unique_id(article: dict[str, Any], used_ids: set[str]) -> str:
    article_id = article["id"]
    if ARTICLE_ID_PATTERN.match(article_id) and article_id not in used_ids:
        used_ids.add(article_id)
        return article_id

    date = date_from_timestamp(article["collected_at"])
    sequence = 1
    while True:
        candidate = f"kb-{date}-{sequence:03d}"
        if candidate not in used_ids:
            used_ids.add(candidate)
            return candidate
        sequence += 1


def _unique_path(articles_dir: Path, article: dict[str, Any], used_paths: set[Path]) -> Path:
    date = date_from_timestamp(article["collected_at"])
    slug = slugify(article["title"])
    sequence = 1
    while True:
        suffix = "" if sequence == 1 else f"-{sequence}"
        candidate = articles_dir / f"{date}-{slug}{suffix}.json"
        if candidate not in used_paths:
            used_paths.add(candidate)
            return candidate
        sequence += 1


def migrate_articles(
    *,
    articles_dir: Path = ARTICLES_DIR,
    raw_dir: Path = RAW_DIR,
    dry_run: bool = False,
) -> dict[str, Any]:
    articles_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)

    source_files = [
        path
        for path in sorted(articles_dir.glob("*.json"))
        if path.name != "index.json"
    ]
    now = utc_now()
    used_ids: set[str] = set()
    used_paths: set[Path] = set()
    migrated: list[tuple[Path, Path, dict[str, Any]]] = []
    skipped: list[dict[str, str]] = []

    for path in source_files:
        raw_data = _load_json(path)
        if raw_data is None:
            skipped.append({
                "source_id": path.name,
                "title": path.stem,
                "reason": "invalid-json",
            })
            continue

        article = convert_legacy_article(raw_data, fallback_now=now)
        article["id"] = _unique_id(article, used_ids)
        target_path = _unique_path(articles_dir, article, used_paths)

        errors = validate_article_contract(article)
        if errors:
            skipped.append({
                "source_id": str(raw_data.get("id") or path.name),
                "title": str(raw_data.get("title") or path.stem),
                "reason": "; ".join(errors),
            })
            continue

        migrated.append((path, target_path, article))

    if not dry_run:
        for source_path, target_path, article in migrated:
            if source_path != target_path and source_path.exists():
                source_path.unlink()
            json_dump(target_path, article)
        rebuild_index(articles_dir, now=now)
        json_dump(
            raw_dir / f"filtered-{date_from_timestamp(now)}.json",
            {
                "date": date_from_timestamp(now),
                "filtered_at": now,
                "items": skipped,
            },
        )

    return {
        "found": len(source_files),
        "migrated": len(migrated),
        "skipped": len(skipped),
        "dry_run": dry_run,
        "skipped_items": skipped,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate knowledge/articles to the current contract.")
    parser.add_argument("--dry-run", action="store_true", help="Preview migration without writing files.")
    args = parser.parse_args()
    result = migrate_articles(dry_run=args.dry_run)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
