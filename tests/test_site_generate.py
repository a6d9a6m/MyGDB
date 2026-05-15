from __future__ import annotations

import json
import subprocess
import sys

from MyGK_DB.knowledge_contract import json_dump
from MyGK_DB.site.generate import build_site, render_markdown


def article(article_id: str, title: str, **overrides):
    data = {
        "id": article_id,
        "title": title,
        "source": "github-trending",
        "source_id": f"source-{article_id}",
        "url": f"https://example.com/{article_id}",
        "summary": f"{title} 提供面向 LLM agent 的工程实践内容，适合用于测试静态站点展示。",
        "tags": ["agent", "llm"],
        "relevance_score": 0.82,
        "collected_at": "2026-05-01T08:00:00Z",
        "analyzed_at": "2026-05-01T08:30:00Z",
        "organized_at": "2026-05-01T09:00:00Z",
        "status": "published",
    }
    data.update(overrides)
    return data


def write_articles(articles_dir, articles):
    articles_dir.mkdir(parents=True, exist_ok=True)
    entries = []
    for index, item in enumerate(articles, 1):
        filename = f"2026-05-01-{index}.json"
        json_dump(articles_dir / filename, item)
        entries.append(
            {
                "id": item["id"],
                "title": item["title"],
                "file": filename,
                "tags": item["tags"],
                "relevance_score": item["relevance_score"],
                "organized_at": item["organized_at"],
            }
        )
    json_dump(
        articles_dir / "index.json",
        {
            "last_updated": "2026-05-01T10:00:00Z",
            "total_count": len(entries),
            "entries": entries,
        },
    )


def test_build_site_generates_index_article_assets_and_search_data(tmp_path):
    articles_dir = tmp_path / "articles"
    output_dir = tmp_path / "site"
    write_articles(
        articles_dir,
        [
            article("kb-2026-05-01-001", "Alpha Agent"),
            article(
                "kb-2026-05-01-002",
                "Beta Long Read",
                content_markdown="## Context\n\nA **useful** [link](https://example.com).\n\n- one\n- two\n\n```python\nprint('ok')\n```",
                content_fetched_at="2026-05-01T11:00:00Z",
            ),
        ],
    )

    result = build_site(articles_dir=articles_dir, output_dir=output_dir)

    assert result.article_count == 2
    assert (output_dir / "index.html").exists()
    assert (output_dir / "library.html").exists()
    assert (output_dir / "assets" / "styles.css").exists()
    assert (output_dir / "assets" / "app.js").exists()
    assert (output_dir / "search-data.js").exists()
    article_pages = list((output_dir / "articles").glob("*.html"))
    assert len(article_pages) == 2
    index_html = (output_dir / "index.html").read_text(encoding="utf-8")
    assert "一座为长期阅读整理的 AI 知识库" in index_html
    assert "data-search" not in index_html
    assert "Alpha Agent" in index_html
    library_html = (output_dir / "library.html").read_text(encoding="utf-8")
    assert "搜索、筛选和回看全部条目" in library_html
    assert "data-search" in library_html
    assert "data-tag-filter" in library_html
    assert "data-source-filter" in library_html
    assert "Alpha Agent" in library_html
    search_data = (output_dir / "search-data.js").read_text(encoding="utf-8")
    assert '"href": "articles/' in search_data
    long_page = next(path for path in article_pages if "beta-long-read" in path.name)
    long_html = long_page.read_text(encoding="utf-8")
    assert "<h2 id=\"context\">Context</h2>" in long_html
    assert "<strong>useful</strong>" in long_html
    assert "<pre><code>" in long_html
    assert "文章目录" in long_html


def test_build_site_without_markdown_shows_summary_and_pending_state(tmp_path):
    articles_dir = tmp_path / "articles"
    output_dir = tmp_path / "site"
    write_articles(articles_dir, [article("kb-2026-05-01-001", "Summary Only")])

    build_site(articles_dir=articles_dir, output_dir=output_dir)

    page = next((output_dir / "articles").glob("*.html")).read_text(encoding="utf-8")
    assert "正文尚未入库" in page
    assert "Summary Only 提供面向 LLM agent" in page


def test_markdown_renderer_escapes_html_and_keeps_safe_links():
    content_html, toc_html = render_markdown(
        "## <Bad>\n\n<script>alert(1)</script> [ok](javascript:bad)\n\n1. first\n2. second\n\n| A | B |\n| --- | --- |\n| x | y |"
    )

    assert "&lt;Bad&gt;" in content_html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in content_html
    assert 'href="#"' in content_html
    assert "<ol><li>first</li><li>second</li></ol>" in content_html
    assert "<table>" in content_html
    assert "<th>A</th>" in content_html
    assert "<td>y</td>" in content_html
    assert "文章目录" in toc_html


def test_build_site_cli(tmp_path):
    articles_dir = tmp_path / "articles"
    output_dir = tmp_path / "site"
    write_articles(articles_dir, [article("kb-2026-05-01-001", "CLI Article")])

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "MyGK_DB.site.generate",
            "--articles-dir",
            str(articles_dir),
            "--output",
            str(output_dir),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "Built 1 articles" in result.stdout
    assert (output_dir / "index.html").exists()
    assert (output_dir / "library.html").exists()
