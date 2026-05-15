"""Generate a static magazine-style site for MyGK_DB articles."""

from __future__ import annotations

import argparse
import html
import json
import logging
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from MyGK_DB.knowledge_contract import ARTICLES_DIR, PROJECT_ROOT, slugify, validate_article_contract

from .assets import APP_JS, STYLES_CSS
from .templates import article_page, index_page, library_page, search_data_script

logger = logging.getLogger(__name__)


@dataclass
class SiteBuildResult:
    output_dir: Path
    article_count: int
    skipped_count: int


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_articles(articles_dir: Path) -> tuple[list[dict[str, Any]], list[str]]:
    index_path = articles_dir / "index.json"
    if not index_path.exists():
        raise FileNotFoundError(f"index.json not found: {index_path}")
    index = _read_json(index_path)
    entries = index.get("entries")
    if not isinstance(entries, list):
        raise ValueError("index.entries must be a list")

    articles: list[dict[str, Any]] = []
    warnings: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict) or not entry.get("file"):
            warnings.append("invalid index entry skipped")
            continue
        path = articles_dir / str(entry["file"])
        try:
            data = _read_json(path)
        except (OSError, json.JSONDecodeError) as exc:
            warnings.append(f"{path.name}: {exc}")
            continue
        errors = validate_article_contract(data)
        if errors:
            warnings.append(f"{path.name}: {'; '.join(errors)}")
            continue
        data["_source_file"] = path.name
        articles.append(data)

    articles.sort(key=lambda item: str(item.get("organized_at", "")), reverse=True)
    return articles, warnings


def _safe_url(value: str) -> str:
    if value.startswith(("http://", "https://", "../", "./", "#")):
        return value
    return "#"


def _inline_markup(text: str) -> str:
    escaped = html.escape(text, quote=True)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", escaped)

    def link(match: re.Match[str]) -> str:
        label = match.group(1)
        url = _safe_url(html.unescape(match.group(2)))
        return f'<a href="{html.escape(url, quote=True)}" target="_blank" rel="noopener noreferrer">{label}</a>'

    return re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link, escaped)


def render_markdown(markdown: str) -> tuple[str, str]:
    """Render a safe Markdown subset and return (html, toc_html)."""
    lines = markdown.splitlines()
    blocks: list[str] = []
    toc: list[tuple[int, str, str]] = []
    paragraph: list[str] = []
    list_items: list[str] = []
    list_tag = "ul"
    code_lines: list[str] = []
    in_code = False

    def flush_paragraph() -> None:
        nonlocal paragraph
        if paragraph:
            blocks.append(f"<p>{_inline_markup(' '.join(paragraph).strip())}</p>")
            paragraph = []

    def flush_list() -> None:
        nonlocal list_items, list_tag
        if list_items:
            blocks.append(
                f"<{list_tag}>"
                + "".join(f"<li>{_inline_markup(item)}</li>" for item in list_items)
                + f"</{list_tag}>"
            )
            list_items = []
            list_tag = "ul"

    def table_separator(value: str) -> bool:
        return bool(re.match(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$", value))

    def split_table_row(value: str) -> list[str]:
        stripped = value.strip().strip("|")
        return [cell.strip() for cell in stripped.split("|")]

    index = 0
    while index < len(lines):
        raw_line = lines[index]
        line = raw_line.rstrip()
        if line.strip().startswith("```"):
            if in_code:
                blocks.append("<pre><code>" + html.escape("\n".join(code_lines)) + "</code></pre>")
                code_lines = []
                in_code = False
            else:
                flush_paragraph()
                flush_list()
                in_code = True
            index += 1
            continue
        if in_code:
            code_lines.append(line)
            index += 1
            continue
        if not line.strip():
            flush_paragraph()
            flush_list()
            index += 1
            continue
        heading = re.match(r"^(#{2,4})\s+(.+)$", line)
        if heading:
            flush_paragraph()
            flush_list()
            level = len(heading.group(1))
            title = heading.group(2).strip()
            anchor = slugify(title, fallback="section")
            toc.append((level, title, anchor))
            blocks.append(f'<h{level} id="{html.escape(anchor, quote=True)}">{_inline_markup(title)}</h{level}>')
            index += 1
            continue
        if "|" in line and index + 1 < len(lines) and table_separator(lines[index + 1]):
            flush_paragraph()
            flush_list()
            headers = split_table_row(line)
            index += 2
            rows: list[list[str]] = []
            while index < len(lines) and "|" in lines[index] and lines[index].strip():
                rows.append(split_table_row(lines[index]))
                index += 1
            head_html = "".join(f"<th>{_inline_markup(cell)}</th>" for cell in headers)
            row_html = ""
            for row in rows:
                padded = row + [""] * max(0, len(headers) - len(row))
                row_html += "<tr>" + "".join(f"<td>{_inline_markup(cell)}</td>" for cell in padded[: len(headers)]) + "</tr>"
            blocks.append(f"<table><thead><tr>{head_html}</tr></thead><tbody>{row_html}</tbody></table>")
            continue
        if line.startswith(">"):
            flush_paragraph()
            flush_list()
            blocks.append(f"<blockquote>{_inline_markup(line.lstrip('> ').strip())}</blockquote>")
            index += 1
            continue
        bullet = re.match(r"^[-*]\s+(.+)$", line)
        if bullet:
            flush_paragraph()
            if list_items and list_tag != "ul":
                flush_list()
            list_tag = "ul"
            list_items.append(bullet.group(1).strip())
            index += 1
            continue
        ordered = re.match(r"^\d+\.\s+(.+)$", line)
        if ordered:
            flush_paragraph()
            if list_items and list_tag != "ol":
                flush_list()
            list_tag = "ol"
            list_items.append(ordered.group(1).strip())
            index += 1
            continue
        paragraph.append(line.strip())
        index += 1

    flush_paragraph()
    flush_list()
    if in_code:
        blocks.append("<pre><code>" + html.escape("\n".join(code_lines)) + "</code></pre>")

    if toc:
        items = "".join(
            f'<li><a href="#{html.escape(anchor, quote=True)}">{html.escape(title)}</a></li>'
            for _, title, anchor in toc
        )
        toc_html = f'<details class="toc"><summary>文章目录</summary><ol>{items}</ol></details>'
    else:
        toc_html = ""
    return "\n".join(blocks), toc_html


def _article_href(article: dict[str, Any], used: set[str]) -> str:
    slug = slugify(str(article.get("title") or article.get("id") or "article"))
    candidate = f"{slug}.html"
    sequence = 2
    while candidate in used:
        candidate = f"{slug}-{sequence}.html"
        sequence += 1
    used.add(candidate)
    return f"articles/{candidate}"


def _prepare_output(output_dir: Path) -> None:
    managed = [
        output_dir / "index.html",
        output_dir / "library.html",
        output_dir / "search-data.js",
        output_dir / "articles",
        output_dir / "assets",
    ]
    output_dir.mkdir(parents=True, exist_ok=True)
    for path in managed:
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()
    (output_dir / "articles").mkdir(parents=True, exist_ok=True)
    (output_dir / "assets").mkdir(parents=True, exist_ok=True)


def _related_articles(article: dict[str, Any], articles: list[dict[str, Any]], limit: int = 4) -> list[dict[str, Any]]:
    tags = set(article.get("tags", []))
    related = [
        item
        for item in articles
        if item.get("id") != article.get("id") and tags.intersection(set(item.get("tags", [])))
    ]
    return related[:limit]


def build_site(*, articles_dir: Path = ARTICLES_DIR, output_dir: Path = PROJECT_ROOT / "site") -> SiteBuildResult:
    articles, warnings = _load_articles(articles_dir)
    _prepare_output(output_dir)
    used_hrefs: set[str] = set()
    for article in articles:
        article["href"] = _article_href(article, used_hrefs)

    tags = sorted({tag for article in articles for tag in article.get("tags", [])})
    sources = sorted({str(article.get("source", "")) for article in articles if article.get("source")})

    search_script = search_data_script(articles)
    (output_dir / "search-data.js").write_text(search_script + "\n", encoding="utf-8")
    (output_dir / "assets" / "styles.css").write_text(STYLES_CSS.strip() + "\n", encoding="utf-8")
    (output_dir / "assets" / "app.js").write_text(APP_JS.strip() + "\n", encoding="utf-8")

    index = _read_json(articles_dir / "index.json")
    (output_dir / "index.html").write_text(
        index_page(
            articles=articles,
            tags=tags,
            sources=sources,
            last_updated=str(index.get("last_updated", "")),
        ),
        encoding="utf-8",
    )
    (output_dir / "library.html").write_text(
        library_page(
            articles=articles,
            tags=tags,
            sources=sources,
            last_updated=str(index.get("last_updated", "")),
        ),
        encoding="utf-8",
    )

    for index_num, article in enumerate(articles):
        markdown = str(article.get("content_markdown") or "").strip()
        if markdown:
            content_html, toc_html = render_markdown(markdown)
            has_body = True
        else:
            content_html = f"<p>{_inline_markup(str(article.get('summary', '')))}</p>"
            toc_html = ""
            has_body = False

        previous_article = articles[index_num + 1] if index_num + 1 < len(articles) else None
        next_article = articles[index_num - 1] if index_num > 0 else None
        page = article_page(
            article=article,
            content_html=content_html,
            toc_html=toc_html,
            related=_related_articles(article, articles),
            previous_article=previous_article,
            next_article=next_article,
            has_body=has_body,
        )
        (output_dir / article["href"]).write_text(page, encoding="utf-8")

    for warning in warnings:
        logger.warning("Skipped article: %s", warning)
    return SiteBuildResult(output_dir=output_dir, article_count=len(articles), skipped_count=len(warnings))


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the MyGK_DB static knowledge site.")
    parser.add_argument("--articles-dir", type=Path, default=ARTICLES_DIR, help="Article JSON directory.")
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "site", help="Output directory.")
    parser.add_argument("--verbose", action="store_true", help="Show warnings for skipped articles.")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING, format="%(levelname)s: %(message)s")
    result = build_site(articles_dir=args.articles_dir, output_dir=args.output)
    print(f"Built {result.article_count} articles into {result.output_dir}")
    if result.skipped_count:
        print(f"Skipped {result.skipped_count} invalid articles")


if __name__ == "__main__":
    main()
