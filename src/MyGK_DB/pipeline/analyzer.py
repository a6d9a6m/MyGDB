"""Analyzer agent adapter backed by Codex CLI."""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from MyGK_DB.knowledge_contract import PROJECT_ROOT, normalize_analyzed_item, utc_now, validate_analyzed_item

logger = logging.getLogger(__name__)

load_dotenv(PROJECT_ROOT / ".env.local")
load_dotenv(PROJECT_ROOT / ".env")
if os.getenv("CODEX_API_KEY") and not os.getenv("OPENAI_API_KEY"):
    os.environ["OPENAI_API_KEY"] = os.environ["CODEX_API_KEY"]


ANALYZE_PROMPT_TEMPLATE = """请分析以下 AI 技术内容，返回 JSON 格式的分析结果。

内容信息：
- 标题：{title}
- 来源：{source}
- 来源可信层级：{source_trust_tier}
- 描述：{description}
- URL：{url}
- 上下文摘录：{context_excerpt}

请返回以下格式的 JSON（不要包含 markdown 代码块标记）：
{{
  "summary": "100-200 字中文技术摘要，说明核心内容、工程价值和适用场景",
  "relevance_score": 0.72,
  "score_breakdown": {{
    "tech_depth": 0.70,
    "practical_value": 0.80,
    "timeliness": 0.65,
    "community_heat": 0.75,
    "domain_match": 0.70
  }},
  "tags": ["agent", "llm", "deployment"]
}}

评分范围均为 0.00-1.00：
- tech_depth: 技术深度，权重 0.25
- practical_value: 实用价值，权重 0.30
- timeliness: 时效性，权重 0.20
- community_heat: 社区热度，权重 0.15
- domain_match: AI/LLM/Agent 领域匹配度，权重 0.10

要求：
- 摘要使用中文，直接说明事实、用途和适用场景。
- 标签必须英文小写，多词使用连字符。
- 不要因为来源权威或热度高就自动给高分。
- 信息不足时保守表述，不要编造事实。"""


def _extract_json_object(text: str) -> dict[str, Any]:
    """Extract the first JSON object from a Codex CLI response."""
    content = text.strip()
    content = re.sub(r"^```json\s*", "", content)
    content = re.sub(r"\s*```$", "", content)

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def analyze_with_codex_cli(prompt: str, model: str | None = None) -> dict[str, Any]:
    """Run Codex CLI and parse the final message as JSON."""
    codex_bin = os.getenv("CODEX_BIN", "codex")
    command = [
        codex_bin,
        "exec",
        "--sandbox",
        "read-only",
        "--cd",
        str(PROJECT_ROOT),
        "--color",
        "never",
    ]
    if model:
        command.extend(["--model", model])

    tmp_parent = PROJECT_ROOT / ".tmp"
    tmp_parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=tmp_parent) as tmp_dir:
        output_file = Path(tmp_dir) / "codex-analysis.json"
        command.extend(["--output-last-message", str(output_file), "-"])
        subprocess.run(
            command,
            input=prompt,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            cwd=PROJECT_ROOT,
        )
        return _extract_json_object(output_file.read_text(encoding="utf-8"))


def build_analysis_prompt(item: dict[str, Any]) -> str:
    return ANALYZE_PROMPT_TEMPLATE.format(
        title=item["title"],
        source=item.get("source", "unknown"),
        source_trust_tier=item.get("source_trust_tier", "unknown"),
        description=item.get("description") or item.get("raw_description", "无描述"),
        url=item.get("url") or item.get("source_url", ""),
        context_excerpt=item.get("context_excerpt", ""),
    )


def analyze_item(
    item: dict[str, Any],
    *,
    model: str | None = None,
    fallback_on_failure: bool = True,
) -> dict[str, Any]:
    """Analyze one raw item.

    `fallback_on_failure=True` preserves legacy behavior. Graph mode passes
    `False` so failed analysis can be filtered instead of published.
    """
    prompt = build_analysis_prompt(item)
    try:
        analysis = analyze_with_codex_cli(prompt, model=model)
        enriched = normalize_analyzed_item({**item, **analysis, "analyzed_at": utc_now()})
        errors = validate_analyzed_item(enriched)
        if errors:
            raise ValueError("; ".join(errors))
        return enriched
    except (subprocess.CalledProcessError, json.JSONDecodeError, KeyError, ValueError) as exc:
        logger.warning("Codex CLI analysis failed: %s - %s", item.get("title", item.get("id")), exc)
        if not fallback_on_failure:
            return {
                **item,
                "analysis_failed": True,
                "analysis_error": str(exc),
                "analyzed_at": utc_now(),
            }
        return normalize_analyzed_item(
            {
                **item,
                "summary": (item.get("description") or item.get("raw_description", ""))[:200],
                "relevance_score": 0.5,
                "score_breakdown": {
                    "tech_depth": 0.5,
                    "practical_value": 0.5,
                    "timeliness": 0.5,
                    "community_heat": 0.5,
                    "domain_match": 0.5,
                },
                "tags": ["llm", "ai"],
                "analyzed_at": utc_now(),
            }
        )


def analyze_items(
    items: list[dict[str, Any]],
    *,
    model: str | None = None,
    fallback_on_failure: bool = True,
) -> list[dict[str, Any]]:
    return [analyze_item(item, model=model, fallback_on_failure=fallback_on_failure) for item in items]
