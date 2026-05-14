from __future__ import annotations

import json

import pytest

from MyGK_DB.pipeline import analyzer
from MyGK_DB.pipeline.collector import collect_source
from MyGK_DB.pipeline.source_registry import SourceConfig, load_source_registry, select_sources


def test_extract_json_object_variants():
    assert analyzer._extract_json_object('{"summary":"ok"}') == {"summary": "ok"}
    assert analyzer._extract_json_object('```json\n{"summary":"ok"}\n```') == {"summary": "ok"}
    assert analyzer._extract_json_object('final answer:\n{"summary":"ok"}') == {"summary": "ok"}


def test_collect_source_wraps_rss_batch(monkeypatch):
    source = SourceConfig(
        id="rss:test",
        type="rss",
        name="Test RSS",
        url="https://example.com/feed.xml",
    )

    monkeypatch.setattr(
        "MyGK_DB.pipeline.collector.collect_rss",
        lambda limit, sources=None: [
            {
                "id": "https://example.com/a",
                "title": "Agent article",
                "url": "https://example.com/a",
                "source": "rss:test",
                "description": "A useful agent article.",
                "collected_at": "2026-05-01T08:00:00Z",
            }
        ],
    )

    batch = collect_source(source, 3)

    assert batch["source"] == "rss:test"
    assert batch["count"] == 1
    assert batch["items"][0]["title"] == "Agent article"
    assert batch["items"][0]["url"] == "https://example.com/a"


def test_collect_source_wraps_github_batch(monkeypatch):
    monkeypatch.setattr(
        "MyGK_DB.pipeline.collector.collect_github",
        lambda limit, source, token="", include_readme=True: [
            {
                "id": "openai/agents-sdk",
                "title": "openai/agents-sdk",
                "url": "https://github.com/openai/agents-sdk",
                "description": "Agent SDK",
                "source": "github-trending",
                "collected_at": "2026-05-01T08:00:00Z",
            }
        ],
    )

    batch = collect_source("github", 1)

    assert batch["source"] == "github-trending"
    assert batch["count"] == 1
    assert batch["items"][0]["id"] == "openai/agents-sdk"


def test_source_registry_loads_rss_metadata(tmp_path):
    config = tmp_path / "sources.yaml"
    config.write_text(
        """
sources:
  - id: "rss:test"
    type: "rss"
    name: "Test"
    url: "https://example.com/feed.xml"
    enabled: true
    category: "framework"
    trust_tier: "high"
    limit: 7
    keywords: ["agent"]
    quality_weight: 1.2
    parser: "rss"
    fetch_timeout_seconds: 12
  - id: "rss:disabled"
    type: "rss"
    name: "Disabled"
    url: "https://example.com/disabled.xml"
    enabled: false
""",
        encoding="utf-8",
    )

    registry = load_source_registry(config)
    selected = select_sources(["rss"], registry=registry)

    assert any(source.id == "github-trending" for source in registry)
    assert [source.id for source in selected] == ["rss:test"]
    assert selected[0].trust_tier == "high"
    assert selected[0].quality_weight == 1.2
    assert selected[0].limit == 7
