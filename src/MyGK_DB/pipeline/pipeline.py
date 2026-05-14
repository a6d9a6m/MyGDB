"""AI knowledge-base pipeline CLI.

The legacy engine keeps the original four-step behavior. The graph engine is
implemented in `MyGK_DB.pipeline.graph` and reuses the same collector/analyzer
and publisher adapters.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from MyGK_DB.knowledge_contract import PROJECT_ROOT, RAW_DIR

from .analyzer import (
    ANALYZE_PROMPT_TEMPLATE,
    _extract_json_object,
    analyze_item,
    analyze_items,
    analyze_with_codex_cli,
)
from .collector import collect_github, collect_rss, collect_source, collect_sources
from .organizer import organize_items, publish_items
from .reviewer import remove_rejected_files, review_saved_articles

load_dotenv(PROJECT_ROOT / ".env.local")
load_dotenv(PROJECT_ROOT / ".env")
if os.getenv("CODEX_API_KEY") and not os.getenv("OPENAI_API_KEY"):
    os.environ["OPENAI_API_KEY"] = os.environ["CODEX_API_KEY"]

logger = logging.getLogger(__name__)


def step_collect(sources: list[str], limit: int) -> list[dict[str, Any]]:
    """Step 1: collect raw items and persist raw snapshots."""
    print(f"\n{'=' * 60}")
    print(f"[Collect] Step 1: 采集（sources={sources}, limit={limit}）")
    print(f"{'=' * 60}")

    raw_batches = collect_sources(sources, limit)
    all_items: list[dict[str, Any]] = []
    for batch in raw_batches:
        all_items.extend(batch.get("items", []))

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    raw_file = RAW_DIR / f"raw_{timestamp}.json"
    raw_file.write_text(json.dumps(all_items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    batch_file = RAW_DIR / f"raw-batch-{timestamp}.json"
    combined_batch = {
        "source": ",".join(batch.get("source", "") for batch in raw_batches),
        "collected_at": raw_batches[0].get("collected_at") if raw_batches else "",
        "query": f"sources={','.join(sources)} limit={limit}",
        "count": len(all_items),
        "items": all_items,
    }
    errors = [error for batch in raw_batches for error in batch.get("errors", [])]
    if errors:
        combined_batch["errors"] = errors
    batch_file.write_text(json.dumps(combined_batch, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"  采集到 {len(all_items)} 条原始数据")
    print(f"  保存到 {raw_file}")
    print(f"  Contract batch 保存到 {batch_file}")
    return all_items


def step_analyze(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Step 2: analyze raw items through Codex CLI."""
    print(f"\n{'=' * 60}")
    print(f"[Analyze] Step 2: 分析（{len(items)} 条内容）")
    print(f"{'=' * 60}")

    model = os.getenv("CODEX_MODEL")
    analyzed: list[dict[str, Any]] = []
    for index, item in enumerate(items, 1):
        print(f"  [{index}/{len(items)}] 分析: {str(item.get('title', ''))[:50]}...")
        analyzed.append(analyze_item(item, model=model, fallback_on_failure=True))

    print(f"  分析完成: {len(analyzed)} 条")
    return analyzed


def step_organize(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Step 3: deduplicate and normalize analyzed items."""
    print(f"\n{'=' * 60}")
    print(f"[Organize] Step 3: 整理（{len(items)} 条内容）")
    print(f"{'=' * 60}")

    organized = organize_items(items)
    print(f"  去重: 移除 {len(items) - len(organized)} 条重复或不可发布条目")
    print(f"  整理后: {len(organized)} 条")
    return organized


def step_save(items: list[dict[str, Any]], dry_run: bool = False) -> list[Path]:
    """Step 4: publish analyzed items as article JSON files."""
    print(f"\n{'=' * 60}")
    print(f"[Save] Step 4: 保存（{len(items)} 条内容，dry_run={dry_run}）")
    print(f"{'=' * 60}")

    result = publish_items(items, dry_run=dry_run)
    for filepath in result.saved_files:
        print(f"  {'[DRY RUN] 将发布' if dry_run else '已发布'}: {filepath}")
    if result.filtered_log_file:
        print(f"  过滤日志: {result.filtered_log_file}")
    if result.index_file:
        print(f"  索引文件: {result.index_file}")
    if result.filtered_items:
        print(f"  过滤: {len(result.filtered_items)} 条")

    print(f"\n  共 {'模拟' if dry_run else ''}发布 {len(result.saved_files)} 个文件")
    return result.saved_files


def _repair_with_recollection(
    *,
    sources: list[str],
    target_count: int,
    attempt: int,
    dry_run: bool,
) -> tuple[list[Path], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Recollect replacement candidates for failed review items."""
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

    replacement_files = step_save(organized_items[:target_count], dry_run=dry_run)
    return replacement_files, raw_items, analyzed_items, organized_items


def run_pipeline(
    sources: list[str],
    limit: int = 20,
    dry_run: bool = False,
    steps: list[int] | None = None,
    auto_review: bool = True,
    repair_on_failure: bool = True,
    max_review_attempts: int = 3,
) -> dict[str, Any]:
    """Run the legacy four-step pipeline."""
    run_steps = set(steps) if steps else {1, 2, 3, 4}
    start_time = datetime.now()
    print(f"\n{'#' * 60}")
    print(f"# AI 知识库流水线 — {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"# 数据源: {', '.join(sources)} | 限制: {limit} | DryRun: {dry_run}")
    print(f"# 执行步骤: {sorted(run_steps)}")
    print(f"{'#' * 60}")

    raw_items: list[dict[str, Any]] = []
    analyzed_items: list[dict[str, Any]] = []
    organized_items: list[dict[str, Any]] = []
    saved_files: list[Path | str] = []
    review_passed_files: list[Path] = []
    review_failed = 0
    repair_rounds = 0

    if 1 in run_steps:
        raw_items = step_collect(sources, limit)
        if not raw_items:
            print("\n[WARN] 没有采集到任何数据，流水线结束。")
            return {"collected": 0, "analyzed": 0, "saved": 0}

    if 2 in run_steps and raw_items:
        analyzed_items = step_analyze(raw_items)

    if 3 in run_steps and analyzed_items:
        organized_items = step_organize(analyzed_items)

    if 4 in run_steps and organized_items:
        saved_files = step_save(organized_items, dry_run=dry_run)

    if 4 in run_steps and auto_review and not dry_run and saved_files:
        print(f"\n{'=' * 60}")
        print("[Review] 保存后自动触发审查")
        print(f"{'=' * 60}")

        current_files = [Path(path) for path in saved_files]
        review_passed_files, rejected_items = review_saved_articles(current_files)
        review_failed = len(rejected_items)

        attempt = 0
        while rejected_items and repair_on_failure and attempt < max_review_attempts:
            attempt += 1
            repair_rounds = attempt
            remove_rejected_files(rejected_items)

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
            remove_rejected_files(rejected_items)
            logger.warning("仍有 %d 篇文章未通过审查，已从知识库移除。", len(rejected_items))

        saved_files = [str(path) for path in review_passed_files]

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
        "engine": "legacy",
    }

    print(f"\n{'#' * 60}")
    print(f"# 流水线完成！耗时 {elapsed:.1f} 秒")
    print(
        f"# 采集: {stats['collected']} → 分析: {stats['analyzed']} "
        f"→ 整理: {stats['organized']} → 保存: {stats['saved']}"
    )
    if auto_review and not dry_run:
        print(
            f"# 审查通过: {stats['review_passed']} | 审查失败: {stats['review_failed']} "
            f"| 修正轮次: {stats['repair_rounds']}"
        )
    print(f"{'#' * 60}\n")
    return stats


def parse_sources(value: str) -> list[str]:
    return [source.strip() for source in value.split(",") if source.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AI 知识库采集流水线",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    mygk-pipeline --engine graph --sources github,rss --limit 20
    mygk-pipeline --engine legacy --sources github --limit 5 --dry-run
    mygk-graph-pipeline --sources rss --limit 10
        """,
    )
    parser.add_argument("--engine", choices=["legacy", "graph"], default="graph", help="执行引擎（默认: graph）")
    parser.add_argument("--sources", type=str, default="github,rss", help="数据源，逗号分隔（默认: github,rss）")
    parser.add_argument("--limit", type=int, default=20, help="每个源的最大采集数量（默认: 20）")
    parser.add_argument("--dry-run", action="store_true", help="仅模拟运行，不实际保存文件")
    parser.add_argument("--verbose", action="store_true", help="显示详细日志")
    parser.add_argument("--step", type=int, action="append", help="legacy 引擎指定步骤（1-4）")
    parser.add_argument("--model", type=str, default=None, help="Codex CLI 使用的模型名，覆盖环境变量 CODEX_MODEL")
    parser.add_argument("--skip-review", action="store_true", help="跳过保存后的自动审查与补采修正")
    parser.add_argument("--skip-repair", action="store_true", help="执行自动审查，但不做失败后的补采修正")
    parser.add_argument("--max-review-attempts", type=int, default=3, help="审查失败后的最大自动补采轮次（默认: 3）")
    parser.add_argument("--checkpoint", choices=["none", "memory", "sqlite"], default="memory", help="graph checkpoint 后端")
    parser.add_argument("--checkpoint-db", type=str, default=".tmp/langgraph-checkpoints.sqlite", help="SQLite checkpoint 路径")
    args = parser.parse_args()

    if args.model:
        os.environ["CODEX_MODEL"] = args.model

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    sources = parse_sources(args.sources)
    if args.engine == "graph":
        from .graph import run_graph_pipeline

        run_graph_pipeline(
            sources=sources,
            limit=args.limit,
            dry_run=args.dry_run,
            auto_review=not args.skip_review,
            repair_on_failure=not args.skip_repair,
            max_review_attempts=max(0, args.max_review_attempts),
            checkpoint=args.checkpoint,
            checkpoint_db=Path(args.checkpoint_db),
        )
        return

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
