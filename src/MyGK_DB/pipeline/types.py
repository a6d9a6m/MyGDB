"""Internal pipeline type contracts.

These types describe in-process state only. They do not change the JSON
knowledge-base contract under `.codex/contracts/knowledge-base.md`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, TypedDict


class RawItem(TypedDict, total=False):
    id: str
    title: str
    description: str
    url: str
    source: str
    collected_at: str


class RawBatch(TypedDict, total=False):
    source: str
    collected_at: str
    query: str
    count: int
    items: list[dict[str, Any]]
    errors: list[dict[str, Any]]


class AnalyzedItem(TypedDict, total=False):
    id: str
    title: str
    description: str
    url: str
    source: str
    summary: str
    relevance_score: float
    score_breakdown: dict[str, float]
    tags: list[str]
    collected_at: str
    analyzed_at: str


class ReviewDecision(TypedDict, total=False):
    passed: list[Path]
    rejected: list[dict[str, Any]]
    needs_manual_review: list[dict[str, Any]]


class PipelineStats(TypedDict, total=False):
    collected: int
    analyzed: int
    organized: int
    saved: int
    review_passed: int
    review_failed: int
    repair_rounds: int
    elapsed_seconds: float
    dry_run: bool
    engine: str
    run_id: str
    errors_count: int
