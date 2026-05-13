"""
AI 知识库四步流水线：采集 → 分析 → 整理 → 保存

运行方式：
    python3 pipeline/pipeline.py --sources github,rss --limit 20
    python3 pipeline/pipeline.py --sources github --limit 5 --dry-run
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

from MyGK_DB.knowledge_contract import (
    ARTICLES_DIR,
    PROJECT_ROOT,
    RAW_DIR,
    make_raw_batch,
    normalize_analyzed_item,
    normalize_timestamp,
    publish_analyzed_items,
    utc_now,
)

from .rss import collect_rss  # noqa: F401 — 重导出供内部使用

# ── 项目路径 ─────────────────────────────────────────────────────────────

HOOKS_DIR = PROJECT_ROOT / ".codex" / "hooks"
VALIDATE_HOOK = HOOKS_DIR / "validate_json.py"
QUALITY_HOOK = HOOKS_DIR / "check_quality.py"

load_dotenv(PROJECT_ROOT / ".env.local")
load_dotenv(PROJECT_ROOT / ".env")
if os.getenv("CODEX_API_KEY") and not os.getenv("OPENAI_API_KEY"):
    os.environ["OPENAI_API_KEY"] = os.environ["CODEX_API_KEY"]
logger = logging.getLogger(__name__)
_HOOK_MODULE_CACHE: dict[str, Any] = {}


# ── Step 1: 采集（Collect） ──────────────────────────────────────────────

def collect_github(limit: int = 10) -> list[dict[str, Any]]:
    """
    从 GitHub 搜索 API 采集 AI 相关热门仓库。

    Args:
        limit: 最大采集数量

    Returns:
        原始数据列表
    """
    token = os.getenv("GITHUB_TOKEN", "")
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"token {token}"

    # 搜索最近一周更新的 AI 相关仓库，按 star 排序
    one_week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
    query = f"ai agent llm stars:>100 pushed:>{one_week_ago}"
    url = "https://api.github.com/search/repositories"
    params = {
        "q": query,
        "sort": "stars",
        "order": "desc",
        "per_page": min(limit, 30),
    }

    results: list[dict[str, Any]] = []
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(url, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()

            for i, repo in enumerate(data.get("items", [])[:limit]):
                now = utc_now()
                results.append({
                    "id": repo["full_name"],
                    "title": repo["full_name"],
                    "source": "github-trending",
                    "description": repo.get("description", "") or "",
                    "url": repo["html_url"],
                    "author": repo["owner"]["login"],
                    "stars": repo.get("stargazers_count", 0),
                    "language": repo.get("language", ""),
                    "topics": repo.get("topics", []),
                    "created_at": normalize_timestamp(repo.get("created_at"), fallback=now),
                    "updated_at": normalize_timestamp(repo.get("updated_at") or repo.get("pushed_at"), fallback=now),
                    "collected_at": now,
                })

        logger.info("GitHub 采集完成: %d 条", len(results))
    except httpx.HTTPError as e:
        logger.error("GitHub API 调用失败: %s", e)

    return results


# collect_rss 已抽取到 pipeline/rss_reader.py，此处通过顶部 import 重导出
# 保持向后兼容：旧代码调用 pipeline.pipeline.collect_rss 仍然可用


def step_collect(sources: list[str], limit: int) -> list[dict[str, Any]]:
    """
    Step 1: 按数据源采集原始数据。

    Args:
        sources: 数据源列表 ["github", "rss"]
        limit: 每个源的最大采集数

    Returns:
        合并后的原始数据列表
    """
    print(f"\n{'='*60}")
    print(f"[Collect] Step 1: 采集（sources={sources}, limit={limit}）")
    print(f"{'='*60}")

    all_items: list[dict[str, Any]] = []

    if "github" in sources:
        all_items.extend(collect_github(limit))
    if "rss" in sources:
        all_items.extend(collect_rss(limit))

    # 保存原始数据：兼容流水线内部的扁平列表，同时额外输出 contract raw batch。
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    raw_file = RAW_DIR / f"raw_{timestamp}.json"
    with open(raw_file, "w", encoding="utf-8") as f:
        json.dump(all_items, f, ensure_ascii=False, indent=2)

    batch = make_raw_batch(
        source=",".join(sources),
        items=all_items,
        query=f"sources={','.join(sources)} limit={limit}",
    )
    batch_file = RAW_DIR / f"raw-batch-{timestamp}.json"
    with open(batch_file, "w", encoding="utf-8") as f:
        json.dump(batch, f, ensure_ascii=False, indent=2)

    print(f"  采集到 {len(all_items)} 条原始数据")
    print(f"  保存到 {raw_file}")
    print(f"  Contract batch 保存到 {batch_file}")

    return all_items


# ── Step 2: 分析（Analyze） ──────────────────────────────────────────────

ANALYZE_PROMPT_TEMPLATE = """请分析以下 AI 技术内容，返回 JSON 格式的分析结果。

内容信息：
- 标题：{title}
- 来源：{source}
- 描述：{description}
- URL：{url}

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
- tech_depth: 技术深度
- practical_value: 实用价值
- timeliness: 时效性
- community_heat: 社区热度
- domain_match: AI/LLM/Agent 领域匹配度

可用标签：agent, rag, mcp, llm, fine-tuning, prompt-engineering, multi-agent,
tool-use, evaluation, deployment, security, reasoning, code-generation, vision, audio

标签必须英文小写，多词使用连字符。"""


def _extract_json_object(text: str) -> dict[str, Any]:
    """从 Codex CLI 最终输出中提取第一段 JSON 对象。"""
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
    """
    使用 Codex CLI 执行分析。

    该函数是流水线的分析执行适配层：负责把 prompt 交给 Codex CLI，
    并将最终回复解析为后续步骤可消费的 JSON 对象。
    """
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


def step_analyze(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Step 2: 调用 LLM 对每条内容进行分析。

    Args:
        items: 原始数据列表

    Returns:
        带分析结果的数据列表
    """
    print(f"\n{'='*60}")
    print(f"[Analyze] Step 2: 分析（{len(items)} 条内容）")
    print(f"{'='*60}")

    model = os.getenv("CODEX_MODEL")
    analyzed: list[dict[str, Any]] = []

    for i, item in enumerate(items):
        print(f"  [{i+1}/{len(items)}] 分析: {item['title'][:50]}...")

        prompt = ANALYZE_PROMPT_TEMPLATE.format(
            title=item["title"],
            source=item["source"],
            description=item.get("description") or item.get("raw_description", "无描述"),
            url=item.get("url") or item.get("source_url", ""),
        )

        try:
            analysis = analyze_with_codex_cli(prompt, model=model)
            enriched = normalize_analyzed_item({
                **item,
                **analysis,
                "analyzed_at": utc_now(),
            })
            analyzed.append(enriched)

        except (subprocess.CalledProcessError, json.JSONDecodeError, KeyError) as e:
            logger.warning("Codex CLI 分析失败: %s — %s", item["title"], e)
            enriched = normalize_analyzed_item({
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
            })
            analyzed.append(enriched)

    print(f"  分析完成: {len(analyzed)} 条")

    return analyzed


# ── Step 3: 整理（Organize） ─────────────────────────────────────────────

def step_organize(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Step 3: 去重、格式化、校验。

    Args:
        items: 带分析结果的数据列表

    Returns:
        整理后的数据列表
    """
    print(f"\n{'='*60}")
    print(f"[Organize] Step 3: 整理（{len(items)} 条内容）")
    print(f"{'='*60}")

    # 去重：按 url 去重。最终发布阶段还会结合历史库再次去重。
    seen_urls: set[str] = set()
    unique: list[dict[str, Any]] = []

    # 先读取已有文章的 URL
    if ARTICLES_DIR.exists():
        for f in ARTICLES_DIR.glob("*.json"):
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    existing = json.load(fh)
                    if "url" in existing:
                        seen_urls.add(existing["url"])
                    elif "source_url" in existing:
                        seen_urls.add(existing["source_url"])
            except (json.JSONDecodeError, IOError):
                pass

    dedup_count = 0
    for item in items:
        url = item.get("url") or item.get("source_url", "")
        if url in seen_urls:
            dedup_count += 1
            continue
        seen_urls.add(url)
        unique.append(item)

    # 标准化为 analyzed item，发布格式交给 step_save。
    organized: list[dict[str, Any]] = []
    for item in unique:
        organized.append(normalize_analyzed_item(item))

    print(f"  去重: 移除 {dedup_count} 条重复")
    print(f"  整理后: {len(organized)} 条")

    return organized


# ── Step 4: 保存（Save） ────────────────────────────────────────────────

def step_save(items: list[dict[str, Any]], dry_run: bool = False) -> list[Path]:
    """
    Step 4: 将文章保存为独立 JSON 文件。

    Args:
        items: 整理后的文章列表
        dry_run: 仅模拟，不实际写入

    Returns:
        已保存的文件路径列表
    """
    print(f"\n{'='*60}")
    print(f"[Save] Step 4: 保存（{len(items)} 条内容，dry_run={dry_run}）")
    print(f"{'='*60}")

    result = publish_analyzed_items(items, dry_run=dry_run)

    for filepath in result.saved_files:
        if dry_run:
            print(f"  [DRY RUN] 将发布: {filepath}")
        else:
            print(f"  已发布: {filepath}")

    if result.filtered_log_file:
        print(f"  过滤日志: {result.filtered_log_file}")
    if result.index_file:
        print(f"  索引文件: {result.index_file}")
    if result.filtered_items:
        print(f"  过滤: {len(result.filtered_items)} 条")

    print(f"\n  共 {'模拟' if dry_run else ''}发布 {len(result.saved_files)} 个文件")
    return result.saved_files


def _load_hook_module(name: str, path: Path) -> Any:
    """按需加载仓库内的 hook 模块，确保流水线和 Codex hook 共用同一套规则。"""
    if name in _HOOK_MODULE_CACHE:
        return _HOOK_MODULE_CACHE[name]

    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载 hook 模块: {path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    _HOOK_MODULE_CACHE[name] = module
    return module


def _run_hook_command(script_path: Path, filepaths: list[Path]) -> None:
    """执行 hook 脚本，保留与 Codex CLI/CI 一致的可见输出。"""
    if not filepaths:
        return

    command = [
        os.getenv("PYTHON_BIN", os.sys.executable),
        str(script_path),
        *[str(path) for path in filepaths],
    ]
    subprocess.run(
        command,
        check=False,
        cwd=PROJECT_ROOT,
        text=True,
        encoding="utf-8",
    )


def review_saved_articles(filepaths: list[Path]) -> tuple[list[Path], list[dict[str, Any]]]:
    """
    对当前批次文章执行结构校验和质量评估。

    Returns:
        passed_files: 通过审查的文件
        rejected_items: 失败文件对应的文章数据，供后续补采替换
    """
    if not filepaths:
        return [], []

    validate_module = _load_hook_module("mygk_validate_json", VALIDATE_HOOK)
    quality_module = _load_hook_module("mygk_check_quality", QUALITY_HOOK)

    _run_hook_command(VALIDATE_HOOK, filepaths)
    _run_hook_command(QUALITY_HOOK, filepaths)

    passed_files: list[Path] = []
    rejected_items: list[dict[str, Any]] = []

    for filepath in filepaths:
        try:
            data = json.loads(filepath.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            logger.warning("文章 JSON 解析失败，加入重采队列: %s (%s)", filepath, exc)
            rejected_items.append({"filepath": filepath, "reason": "invalid-json"})
            continue

        errors = validate_module.validate_article(data)
        report = quality_module.evaluate_quality(str(filepath), data)
        if errors or report.grade == "C":
            logger.warning(
                "文章未通过审查: %s | validate_errors=%s | quality_grade=%s",
                filepath.name,
                errors,
                report.grade,
            )
            rejected_items.append({
                "filepath": filepath,
                "reason": "validation-or-quality-failed",
                "data": data,
                "validate_errors": errors,
                "quality_grade": report.grade,
                "quality_score": report.total_score,
            })
            continue

        passed_files.append(filepath)

    return passed_files, rejected_items


def _remove_rejected_files(rejected_items: list[dict[str, Any]]) -> None:
    """删除当前运行中新生成且未通过审查的 article 文件，避免污染知识库。"""
    for item in rejected_items:
        filepath = item.get("filepath")
        if not isinstance(filepath, Path) or not filepath.exists():
            continue
        filepath.unlink()
        logger.info("已移除未通过审查的文章: %s", filepath)


def _repair_with_recollection(
    *,
    sources: list[str],
    target_count: int,
    attempt: int,
    dry_run: bool,
) -> tuple[list[Path], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """
    对未达标条目执行补采。

    返回值依次为：
        replacement_files, raw_items, analyzed_items, organized_items
    """
    if target_count <= 0:
        return [], [], [], []

    repair_limit = max(target_count * (attempt + 2), target_count + 2)
    print(f"\n[Repair] 第 {attempt} 次修正补采，目标补足 {target_count} 条，临时采集上限 {repair_limit}")

    raw_items = step_collect(sources, repair_limit)
    if not raw_items:
        return [], [], [], []

    analyzed_items = step_analyze(raw_items)
    organized_items = step_organize(analyzed_items)
    if not organized_items:
        return [], raw_items, analyzed_items, organized_items

    replacement_candidates = organized_items[:target_count]
    replacement_files = step_save(replacement_candidates, dry_run=dry_run)
    return replacement_files, raw_items, analyzed_items, organized_items


# ── 主流程 ───────────────────────────────────────────────────────────────

def run_pipeline(
    sources: list[str],
    limit: int = 20,
    dry_run: bool = False,
    steps: list[int] | None = None,
    auto_review: bool = True,
    repair_on_failure: bool = True,
    max_review_attempts: int = 3,
) -> dict[str, Any]:
    """
    运行完整的四步流水线。

    Args:
        sources: 数据源列表
        limit: 每个源的最大采集数
        dry_run: 仅模拟运行
        steps: 要执行的步骤列表（1-4），默认全部执行

    Returns:
        运行统计信息
    """
    run_steps = set(steps) if steps else {1, 2, 3, 4}

    start_time = datetime.now()
    print(f"\n{'#'*60}")
    print(f"# AI 知识库流水线 — {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"# 数据源: {', '.join(sources)} | 限制: {limit} | DryRun: {dry_run}")
    print(f"# 执行步骤: {sorted(run_steps)}")
    print(f"{'#'*60}")

    raw_items: list[dict] = []
    analyzed_items: list[dict] = []
    organized_items: list[dict] = []
    saved_files: list[str] = []
    review_passed_files: list[Path] = []
    review_failed = 0
    repair_rounds = 0

    # Step 1: 采集
    if 1 in run_steps:
        raw_items = step_collect(sources, limit)
        if not raw_items:
            print("\n[WARN] 没有采集到任何数据，流水线结束。")
            return {"collected": 0, "analyzed": 0, "saved": 0}

    # Step 2: 分析
    if 2 in run_steps and raw_items:
        analyzed_items = step_analyze(raw_items)

    # Step 3: 整理
    if 3 in run_steps and analyzed_items:
        organized_items = step_organize(analyzed_items)

    # Step 4: 保存
    if 4 in run_steps and organized_items:
        saved_files = step_save(organized_items, dry_run=dry_run)

    if 4 in run_steps and auto_review and not dry_run and saved_files:
        print(f"\n{'='*60}")
        print("[Review] 保存后自动触发审查")
        print(f"{'='*60}")

        current_files = list(saved_files)
        review_passed_files, rejected_items = review_saved_articles(current_files)
        review_failed = len(rejected_items)

        attempt = 0
        while rejected_items and repair_on_failure and attempt < max_review_attempts:
            attempt += 1
            repair_rounds = attempt
            _remove_rejected_files(rejected_items)

            replacement_files, repair_raw, repair_analyzed, repair_organized = _repair_with_recollection(
                sources=sources,
                target_count=len(rejected_items),
                attempt=attempt,
                dry_run=dry_run,
            )
            raw_items.extend(repair_raw)
            analyzed_items.extend(repair_analyzed)
            organized_items.extend(repair_organized)

            if not replacement_files:
                logger.warning("补采未生成可审查文章，停止自动修正。")
                break

            new_passed, rejected_items = review_saved_articles(replacement_files)
            review_passed_files.extend(new_passed)
            review_failed = len(rejected_items)

        if rejected_items:
            _remove_rejected_files(rejected_items)
            logger.warning("仍有 %d 篇文章未通过审查，已从知识库移除。", len(rejected_items))

        saved_files = [str(path) for path in review_passed_files]

    # 统计
    elapsed = (datetime.now() - start_time).total_seconds()
    stats = {
        "collected": len(raw_items),
        "analyzed": len(analyzed_items),
        "organized": len(organized_items),
        "saved": len(saved_files),
        "review_passed": len(review_passed_files) if auto_review and not dry_run else len(saved_files),
        "review_failed": review_failed,
        "repair_rounds": repair_rounds,
        "elapsed_seconds": round(elapsed, 1),
        "dry_run": dry_run,
    }

    print(f"\n{'#'*60}")
    print(f"# 流水线完成！耗时 {elapsed:.1f} 秒")
    print(f"# 采集: {stats['collected']} → 分析: {stats['analyzed']} "
          f"→ 整理: {stats['organized']} → 保存: {stats['saved']}")
    if auto_review and not dry_run:
        print(f"# 审查通过: {stats['review_passed']} | 审查失败: {stats['review_failed']} | 修正轮次: {stats['repair_rounds']}")
    print(f"{'#'*60}\n")

    return stats


# ── CLI 入口 ─────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="AI 知识库采集流水线",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    python3 pipeline/pipeline.py --sources github,rss --limit 20
    python3 pipeline/pipeline.py --sources github --limit 5 --dry-run
    python3 pipeline/pipeline.py --sources rss --limit 10
        """,
    )
    parser.add_argument(
        "--sources",
        type=str,
        default="github,rss",
        help="数据源，逗号分隔（默认: github,rss）",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="每个源的最大采集数量（默认: 20）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅模拟运行，不实际保存文件",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="显示详细日志",
    )
    parser.add_argument(
        "--step",
        type=int,
        action="append",
        help="指定执行的步骤（1-4），可多次使用，如 --step 1 --step 2",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Codex CLI 使用的模型名，覆盖环境变量 CODEX_MODEL",
    )
    parser.add_argument(
        "--skip-review",
        action="store_true",
        help="跳过保存后的自动审查与补采修正",
    )
    parser.add_argument(
        "--skip-repair",
        action="store_true",
        help="执行自动审查，但不做失败后的补采修正",
    )
    parser.add_argument(
        "--max-review-attempts",
        type=int,
        default=3,
        help="审查失败后的最大自动补采轮次（默认: 3）",
    )

    args = parser.parse_args()

    if args.model:
        os.environ["CODEX_MODEL"] = args.model

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    sources = [s.strip() for s in args.sources.split(",")]
    run_pipeline(
        sources=sources,
        limit=args.limit,
        dry_run=args.dry_run,
        steps=args.step,
        auto_review=not args.skip_review,
        repair_on_failure=not args.skip_repair,
        max_review_attempts=max(0, args.max_review_attempts),
    )


if __name__ == "__main__":
    main()
