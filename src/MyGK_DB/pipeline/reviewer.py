"""Reviewer agent helpers for generated articles."""

from __future__ import annotations

import importlib.util
import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from MyGK_DB.knowledge_contract import PROJECT_ROOT, RAW_DIR, date_from_timestamp, json_dump, utc_now

from .source_registry import load_source_registry

logger = logging.getLogger(__name__)

HOOKS_DIR = PROJECT_ROOT / ".codex" / "hooks"
VALIDATE_HOOK = HOOKS_DIR / "validate_json.py"
QUALITY_HOOK = HOOKS_DIR / "check_quality.py"
_HOOK_MODULE_CACHE: dict[str, Any] = {}


def _load_hook_module(name: str, path: Path) -> Any:
    if name in _HOOK_MODULE_CACHE:
        return _HOOK_MODULE_CACHE[name]
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load hook module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    _HOOK_MODULE_CACHE[name] = module
    return module


def _run_hook_command(script_path: Path, filepaths: list[Path]) -> None:
    if not filepaths:
        return
    command = [
        os.getenv("PYTHON_BIN", os.sys.executable),
        str(script_path),
        *[str(path) for path in filepaths],
    ]
    subprocess.run(command, check=False, cwd=PROJECT_ROOT, text=True, encoding="utf-8")


def _trust_tier_for_article(data: dict[str, Any]) -> str:
    if data.get("source_trust_tier") or data.get("trust_tier"):
        return str(data.get("source_trust_tier") or data.get("trust_tier"))
    source = str(data.get("source") or "")
    for entry in load_source_registry():
        if source in {entry.id, entry.name, entry.type}:
            return entry.trust_tier
    return "medium"


def _manual_review_reason(data: dict[str, Any], quality_grade: str, quality_score: float) -> str | None:
    trust_tier = _trust_tier_for_article(data)
    relevance = float(data.get("relevance_score") or 0)
    summary = str(data.get("summary") or "")
    tags = [str(tag) for tag in data.get("tags", []) if isinstance(tag, str)]
    title = str(data.get("title") or "").lower()
    tag_match = any(tag.replace("-", " ") in title for tag in tags)

    if trust_tier == "low" and relevance >= 0.85:
        return "low trust source with high score"
    if len(summary.strip()) < 60 and relevance >= 0.75:
        return "short summary with high score"
    if tags and not tag_match and relevance >= 0.80:
        return "tags do not clearly match title"
    if quality_grade == "B" and quality_score < 66:
        return "quality score close to C"
    return None


def review_saved_articles(
    filepaths: list[Path],
    *,
    write_manual_review_log: bool = False,
    now: str | None = None,
) -> tuple[list[Path], list[dict[str, Any]]]:
    """Run contract validation and quality review for saved article files."""
    if not filepaths:
        return [], []

    validate_module = _load_hook_module("mygk_validate_json", VALIDATE_HOOK)
    quality_module = _load_hook_module("mygk_check_quality", QUALITY_HOOK)

    _run_hook_command(VALIDATE_HOOK, filepaths)
    _run_hook_command(QUALITY_HOOK, filepaths)

    passed_files: list[Path] = []
    rejected_items: list[dict[str, Any]] = []
    manual_review_items: list[dict[str, Any]] = []

    for filepath in filepaths:
        try:
            data = json.loads(filepath.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            logger.warning("Article JSON parse failed: %s (%s)", filepath, exc)
            rejected_items.append({"filepath": filepath, "reason": "invalid-json"})
            continue

        errors = validate_module.validate_article(data)
        report = quality_module.evaluate_quality(str(filepath), data)
        manual_reason = _manual_review_reason(data, report.grade, report.total_score)
        if manual_reason:
            manual_review_items.append(
                {
                    "filepath": str(filepath),
                    "source_id": data.get("source_id") or data.get("id"),
                    "title": data.get("title", ""),
                    "reason": manual_reason,
                    "quality_grade": report.grade,
                    "quality_score": report.total_score,
                }
            )
            rejected_items.append({"filepath": filepath, "reason": "needs-manual-review", "data": data})
            continue

        if errors or report.grade == "C":
            logger.warning(
                "Article failed review: %s | validate_errors=%s | quality_grade=%s",
                filepath.name,
                errors,
                report.grade,
            )
            rejected_items.append(
                {
                    "filepath": filepath,
                    "reason": "validation-or-quality-failed",
                    "data": data,
                    "validate_errors": errors,
                    "quality_grade": report.grade,
                    "quality_score": report.total_score,
                }
            )
            continue

        passed_files.append(filepath)

    if write_manual_review_log and manual_review_items:
        timestamp = now or utc_now()
        review_file = RAW_DIR / f"review-required-{date_from_timestamp(timestamp)}.json"
        json_dump(
            review_file,
            {
                "date": date_from_timestamp(timestamp),
                "review_required_at": timestamp,
                "items": manual_review_items,
            },
        )

    return passed_files, rejected_items


def remove_rejected_files(rejected_items: list[dict[str, Any]]) -> None:
    """Remove files generated in the current run that did not pass review."""
    for item in rejected_items:
        filepath = item.get("filepath")
        if isinstance(filepath, str):
            filepath = Path(filepath)
        if not isinstance(filepath, Path) or not filepath.exists():
            continue
        filepath.unlink()
        logger.info("Removed rejected article: %s", filepath)
