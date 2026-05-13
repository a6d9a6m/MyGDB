from __future__ import annotations

import json

from MyGK_DB.knowledge_contract import json_dump, validate_index_contract
from MyGK_DB.scripts.migrate_articles import migrate_articles


def test_migrate_articles_converts_without_recycling(tmp_path):
    articles_dir = tmp_path / "articles"
    raw_dir = tmp_path / "raw"
    json_dump(
        articles_dir / "github-20260503-001.json",
        {
            "id": "github-20260503-001",
            "title": "langgenius/dify",
            "source": "github",
            "source_url": "https://github.com/langgenius/dify",
            "summary": "Dify 是一个面向生产环境的 Agentic Workflow 开发平台，适合快速构建 AI Agent、业务自动化流程或多步骤 LLM 应用。",
            "score": 8,
            "tags": ["agent", "llm"],
            "status": "review",
            "collected_at": "2026-05-03T03:56:07.219267+00:00",
            "updated_at": "2026-05-03T04:00:43.936939+00:00",
        },
    )

    result = migrate_articles(articles_dir=articles_dir, raw_dir=raw_dir)

    assert result["found"] == 1
    assert result["migrated"] == 1
    assert result["skipped"] == 0
    assert not (articles_dir / "github-20260503-001.json").exists()

    files = [path for path in articles_dir.glob("*.json") if path.name != "index.json"]
    assert len(files) == 1
    article = json.loads(files[0].read_text(encoding="utf-8"))
    assert article["source_id"] == "github-20260503-001"
    assert article["status"] == "published"

    index = json.loads((articles_dir / "index.json").read_text(encoding="utf-8"))
    assert validate_index_contract(index, articles_dir) == []
