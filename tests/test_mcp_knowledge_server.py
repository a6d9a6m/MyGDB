from __future__ import annotations

import json

from MyGK_DB import mcp_knowledge_server as server
from MyGK_DB.knowledge_contract import json_dump


def article(article_id: str, title: str, score: float):
    return {
        "id": article_id,
        "title": title,
        "source": "github-trending",
        "source_id": f"source-{article_id}",
        "url": f"https://example.com/{article_id}",
        "summary": f"{title} 提供面向 LLM agent 的工程实践内容，适合用于测试检索和统计。",
        "tags": ["agent", "llm"],
        "relevance_score": score,
        "collected_at": "2026-05-01T08:00:00Z",
        "analyzed_at": "2026-05-01T08:30:00Z",
        "organized_at": "2026-05-01T09:00:00Z",
        "status": "published",
    }


def test_mcp_search_and_stats_use_published_articles(tmp_path, monkeypatch):
    articles_dir = tmp_path / "articles"
    json_dump(articles_dir / "2026-05-01-alpha.json", article("kb-2026-05-01-001", "Alpha Agent", 0.7))
    json_dump(articles_dir / "2026-05-01-beta.json", article("kb-2026-05-01-002", "Beta Agent", 0.9))
    json_dump(articles_dir / "index.json", {"entries": []})
    json_dump(
        articles_dir / "2026-05-01-draft.json",
        {**article("kb-2026-05-01-003", "Draft Agent", 1.0), "status": "draft"},
    )
    monkeypatch.setattr(server, "ARTICLES_DIR", articles_dir)

    results = server.search_articles("agent", limit=5)
    assert [item["id"] for item in results] == ["kb-2026-05-01-002", "kb-2026-05-01-001"]
    assert "relevance_score" in results[0]
    assert server.get_article("kb-2026-05-01-001")["title"] == "Alpha Agent"

    stats = server.knowledge_stats()
    assert stats["total_articles"] == 2
    assert stats["sources"] == {"github-trending": 2}


def test_mcp_handle_tools_call(tmp_path, monkeypatch):
    articles_dir = tmp_path / "articles"
    json_dump(articles_dir / "2026-05-01-alpha.json", article("kb-2026-05-01-001", "Alpha Agent", 0.7))
    monkeypatch.setattr(server, "ARTICLES_DIR", articles_dir)

    response = server.handle_request({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "search_articles",
            "arguments": {"keyword": "alpha", "limit": 1},
        },
    })

    payload = json.loads(response["result"]["content"][0]["text"])
    assert payload[0]["id"] == "kb-2026-05-01-001"
