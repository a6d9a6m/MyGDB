from __future__ import annotations

import json

from MyGK_DB.knowledge_contract import (
    convert_legacy_article,
    publish_analyzed_items,
    rebuild_index,
    validate_article_contract,
    validate_index_contract,
)


def analyzed_item(**overrides):
    item = {
        "id": "openai/agents-sdk",
        "title": "OpenAI Agents SDK",
        "description": "SDK for building agentic AI applications.",
        "url": "https://github.com/openai/agents-sdk",
        "source": "github-trending",
        "summary": "OpenAI Agents SDK 提供构建 agent workflow 的工程组件，覆盖工具调用、任务交接和运行控制，适合需要快速搭建可维护 LLM 应用的团队。",
        "tags": ["agent", "llm", "tool-use"],
        "relevance_score": 0.82,
        "score_breakdown": {
            "tech_depth": 0.8,
            "practical_value": 0.9,
            "timeliness": 0.7,
            "community_heat": 0.8,
            "domain_match": 0.9,
        },
        "collected_at": "2026-05-01T08:00:00Z",
        "analyzed_at": "2026-05-01T08:30:00Z",
    }
    item.update(overrides)
    return item


def test_publish_filters_duplicates_and_rebuilds_index(tmp_path):
    articles_dir = tmp_path / "articles"
    raw_dir = tmp_path / "raw"
    result = publish_analyzed_items(
        [
            analyzed_item(),
            analyzed_item(id="duplicate", title="Duplicate"),
            analyzed_item(
                id="low-score",
                title="Low Score",
                url="https://example.com/low",
                relevance_score=0.3,
            ),
        ],
        articles_dir=articles_dir,
        raw_dir=raw_dir,
        now="2026-05-01T09:00:00Z",
    )

    assert len(result.saved_files) == 1
    assert len(result.filtered_items) == 2
    assert {item["reason"] for item in result.filtered_items} == {
        "duplicate url",
        "relevance_score below 0.60",
    }

    article = json.loads(result.saved_files[0].read_text(encoding="utf-8"))
    assert validate_article_contract(article) == []
    assert article["id"] == "kb-2026-05-01-001"
    assert article["source_id"] == "openai/agents-sdk"
    assert article["status"] == "published"

    index = json.loads((articles_dir / "index.json").read_text(encoding="utf-8"))
    assert index["total_count"] == 1
    assert validate_index_contract(index, articles_dir) == []

    filtered = json.loads((raw_dir / "filtered-2026-05-01.json").read_text(encoding="utf-8"))
    assert filtered["date"] == "2026-05-01"
    assert len(filtered["items"]) == 2


def test_convert_legacy_article_to_contract():
    legacy = {
        "id": "github-20260503-001",
        "title": "langgenius/dify",
        "source": "github",
        "source_url": "https://github.com/langgenius/dify",
        "summary": "Dify 是一个面向生产环境的 Agentic Workflow 开发平台，适合快速构建 AI Agent、业务自动化流程或多步骤 LLM 应用。",
        "score": 8,
        "tags": ["agent", "LLM", "tool use"],
        "collected_at": "2026-05-03T03:56:07.219267+00:00",
        "updated_at": "2026-05-03T04:00:43.936939+00:00",
    }

    article = convert_legacy_article(legacy, fallback_now="2026-05-04T00:00:00Z")

    assert article["id"] == "kb-2026-05-03-001"
    assert article["source_id"] == "github-20260503-001"
    assert article["url"] == "https://github.com/langgenius/dify"
    assert article["relevance_score"] == 0.8
    assert article["tags"] == ["agent", "llm", "tool-use"]
    assert validate_article_contract(article) == []


def test_rebuild_index_sorts_by_organized_at(tmp_path):
    articles_dir = tmp_path / "articles"
    raw_dir = tmp_path / "raw"
    publish_analyzed_items(
        [analyzed_item(url="https://example.com/older", id="older", title="Older")],
        articles_dir=articles_dir,
        raw_dir=raw_dir,
        now="2026-05-01T09:00:00Z",
    )
    publish_analyzed_items(
        [analyzed_item(url="https://example.com/newer", id="newer", title="Newer")],
        articles_dir=articles_dir,
        raw_dir=raw_dir,
        now="2026-05-02T09:00:00Z",
    )

    index = rebuild_index(articles_dir, now="2026-05-03T09:00:00Z")

    assert index["total_count"] == 2
    assert [entry["title"] for entry in index["entries"]] == ["Newer", "Older"]
