from __future__ import annotations

import json

from MyGK_DB.knowledge_contract import json_dump, validate_index_contract
from MyGK_DB.pipeline import graph
from MyGK_DB.pipeline import reviewer


def raw_item(item_id: str, title: str, url: str):
    return {
        "id": item_id,
        "title": title,
        "description": "A practical LLM agent workflow framework.",
        "url": url,
        "source": "github-trending",
        "collected_at": "2026-05-01T08:00:00Z",
    }


def analyzed_item(item_id: str, title: str, url: str):
    return {
        **raw_item(item_id, title, url),
        "summary": f"{title} 提供面向 LLM agent 的工程实践能力，覆盖工作流编排、工具调用和部署集成，适合用于构建可靠的多步骤 AI 应用。",
        "tags": ["agent", "llm", "tool-use"],
        "relevance_score": 0.82,
        "score_breakdown": {
            "tech_depth": 0.8,
            "practical_value": 0.85,
            "timeliness": 0.8,
            "community_heat": 0.75,
            "domain_match": 0.9,
        },
        "analyzed_at": "2026-05-01T08:30:00Z",
    }


def test_build_graph_compiles():
    compiled = graph.build_graph(checkpoint="none")
    assert compiled is not None


def test_graph_dry_run_routes_sources_and_analyzes(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(graph, "RAW_DIR", tmp_path / "raw")

    def fake_collect_source(source_config, limit):
        calls.append(source_config.id)
        return {
            "source": source_config.id,
            "collected_at": "2026-05-01T08:00:00Z",
            "count": 1,
            "items": [raw_item(source_config.id, source_config.name, f"https://example.com/{source_config.id}")],
        }

    monkeypatch.setattr(graph, "collect_source", fake_collect_source)
    monkeypatch.setattr(
        graph,
        "analyze_item",
        lambda item, model=None, fallback_on_failure=False: analyzed_item(item["id"], item["title"], item["url"]),
    )

    stats = graph.run_graph_pipeline(
        sources=["github"],
        limit=1,
        dry_run=True,
        auto_review=False,
        checkpoint="none",
    )

    assert calls == ["github-trending"]
    assert stats["engine"] == "graph"
    assert stats["collected"] == 1
    assert stats["analyzed"] == 1
    assert stats["saved"] == 1


def test_graph_publish_non_dry_run_uses_contract(monkeypatch, tmp_path):
    monkeypatch.setattr(graph, "RAW_DIR", tmp_path / "raw")
    import MyGK_DB.knowledge_contract as contract
    import MyGK_DB.pipeline.organizer as organizer

    articles_dir = tmp_path / "articles"
    raw_dir = tmp_path / "raw"
    monkeypatch.setattr(contract, "ARTICLES_DIR", articles_dir)
    monkeypatch.setattr(contract, "RAW_DIR", raw_dir)
    monkeypatch.setattr(organizer, "publish_items", lambda items, dry_run=False: contract.publish_analyzed_items(items, articles_dir=articles_dir, raw_dir=raw_dir, dry_run=dry_run, now="2026-05-01T09:00:00Z"))
    monkeypatch.setattr(graph, "publish_items", organizer.publish_items)
    monkeypatch.setattr(
        graph,
        "collect_source",
        lambda source_config, limit: {
            "source": source_config.id,
            "collected_at": "2026-05-01T08:00:00Z",
            "count": 1,
            "items": [raw_item("item-1", "Graph Agent", "https://example.com/graph-agent")],
        },
    )
    monkeypatch.setattr(
        graph,
        "analyze_item",
        lambda item, model=None, fallback_on_failure=False: analyzed_item(item["id"], item["title"], item["url"]),
    )

    stats = graph.run_graph_pipeline(
        sources=["github"],
        limit=1,
        dry_run=False,
        auto_review=False,
        checkpoint="none",
    )

    assert stats["saved"] == 1
    files = [path for path in articles_dir.glob("*.json") if path.name != "index.json"]
    assert len(files) == 1
    index = json.loads((articles_dir / "index.json").read_text(encoding="utf-8"))
    assert validate_index_contract(index, articles_dir) == []


def test_graph_analysis_failure_does_not_publish(monkeypatch, tmp_path):
    monkeypatch.setattr(graph, "RAW_DIR", tmp_path / "raw")
    monkeypatch.setattr(
        graph,
        "collect_source",
        lambda source_config, limit: {
            "source": source_config.id,
            "collected_at": "2026-05-01T08:00:00Z",
            "count": 1,
            "items": [raw_item("bad", "Bad", "https://example.com/bad")],
        },
    )
    monkeypatch.setattr(
        graph,
        "analyze_item",
        lambda item, model=None, fallback_on_failure=False: {
            **item,
            "analysis_failed": True,
            "analysis_error": "boom",
        },
    )

    stats = graph.run_graph_pipeline(
        sources=["github"],
        limit=1,
        dry_run=True,
        auto_review=False,
        checkpoint="none",
    )

    assert stats["analyzed"] == 0
    assert stats["saved"] == 0
    assert stats["errors_count"] == 1


def test_graph_empty_collection_still_finalizes(monkeypatch, tmp_path):
    monkeypatch.setattr(graph, "RAW_DIR", tmp_path / "raw")
    monkeypatch.setattr(
        graph,
        "collect_source",
        lambda source_config, limit: {
            "source": source_config.id,
            "collected_at": "2026-05-01T08:00:00Z",
            "count": 0,
            "items": [],
        },
    )

    stats = graph.run_graph_pipeline(
        sources=["github"],
        limit=0,
        dry_run=True,
        auto_review=False,
        checkpoint="none",
    )

    assert stats["engine"] == "graph"
    assert stats["collected"] == 0
    assert stats["saved"] == 0


def test_graph_sqlite_checkpoint_runs(monkeypatch, tmp_path):
    monkeypatch.setattr(graph, "RAW_DIR", tmp_path / "raw")
    monkeypatch.setattr(
        graph,
        "collect_source",
        lambda source_config, limit: {
            "source": source_config.id,
            "collected_at": "2026-05-01T08:00:00Z",
            "count": 0,
            "items": [],
        },
    )

    stats = graph.run_graph_pipeline(
        sources=["github"],
        limit=0,
        dry_run=True,
        auto_review=False,
        checkpoint="sqlite",
        checkpoint_db=tmp_path / "checkpoints.sqlite",
    )

    assert stats["engine"] == "graph"
    assert stats["saved"] == 0


def test_reviewer_writes_manual_review_queue(monkeypatch, tmp_path):
    articles_dir = tmp_path / "articles"
    raw_dir = tmp_path / "raw"
    article_path = articles_dir / "2026-05-01-manual.json"
    json_dump(
        article_path,
        {
            "id": "kb-2026-05-01-001",
            "title": "Manual Review Candidate",
            "source": "rss:low",
            "source_id": "manual",
            "url": "https://example.com/manual",
            "summary": "这是一段很短的摘要，但分数很高。",
            "tags": ["agent", "llm"],
            "relevance_score": 0.9,
            "collected_at": "2026-05-01T08:00:00Z",
            "analyzed_at": "2026-05-01T08:30:00Z",
            "organized_at": "2026-05-01T09:00:00Z",
            "status": "published",
        },
    )

    class Report:
        grade = "B"
        total_score = 65.0

    monkeypatch.setattr(reviewer, "RAW_DIR", raw_dir)
    monkeypatch.setattr(reviewer, "_run_hook_command", lambda script_path, filepaths: None)
    monkeypatch.setattr(
        reviewer,
        "_load_hook_module",
        lambda name, path: type(
            "Hook",
            (),
            {
                "validate_article": staticmethod(lambda data: []),
                "evaluate_quality": staticmethod(lambda filepath, data: Report()),
            },
        ),
    )
    monkeypatch.setattr(
        reviewer,
        "load_source_registry",
        lambda: [type("Source", (), {"id": "rss:low", "name": "Low", "type": "rss", "trust_tier": "low"})()],
    )

    passed, rejected = reviewer.review_saved_articles(
        [article_path],
        write_manual_review_log=True,
        now="2026-05-01T10:00:00Z",
    )

    assert passed == []
    assert rejected[0]["reason"] == "needs-manual-review"
    review_log = json.loads((raw_dir / "review-required-2026-05-01.json").read_text(encoding="utf-8"))
    assert review_log["items"][0]["reason"] == "low trust source with high score"
