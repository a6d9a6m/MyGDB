"""LangGraph multi-agent pipeline engine."""

from __future__ import annotations

import argparse
import json
import logging
import operator
import os
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any, Literal, TypedDict

from MyGK_DB.knowledge_contract import RAW_DIR, date_from_timestamp, json_dump, utc_now

from .analyzer import analyze_item
from .collector import collect_source
from .organizer import organize_items, publish_items
from .pipeline import parse_sources
from .reviewer import remove_rejected_files, review_saved_articles
from .source_registry import SourceConfig, select_sources

logger = logging.getLogger(__name__)


class KnowledgeGraphState(TypedDict, total=False):
    run_id: str
    thread_id: str
    started_at: str
    sources: list[str]
    source_configs: list[SourceConfig]
    limit: int
    dry_run: bool
    auto_review: bool
    repair_on_failure: bool
    max_review_attempts: int
    repair_rounds: int
    current_repair_target_count: int
    raw_batches: Annotated[list[dict[str, Any]], operator.add]
    raw_items: list[dict[str, Any]]
    analyzed_items: Annotated[list[dict[str, Any]], operator.add]
    organized_items: list[dict[str, Any]]
    saved_files: list[str]
    review_passed_files: Annotated[list[str], operator.add]
    rejected_items: list[dict[str, Any]]
    filtered_items: Annotated[list[dict[str, Any]], operator.add]
    errors: Annotated[list[dict[str, Any]], operator.add]
    stats: dict[str, Any]


class CollectTaskState(TypedDict, total=False):
    source_config: SourceConfig
    limit: int
    repair_round: int


class AnalyzeTaskState(TypedDict, total=False):
    item: dict[str, Any]


def _load_langgraph() -> tuple[Any, Any, Any, Any]:
    try:
        from langgraph.graph import END, START, StateGraph
        from langgraph.types import Send
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "LangGraph is not installed. Install project dependencies with `python -m pip install -e .[dev,checkpoint]`."
        ) from exc
    return StateGraph, START, END, Send


@contextmanager
def _checkpoint_saver(checkpoint: Literal["none", "memory", "sqlite"], checkpoint_db: Path | None) -> Any:
    if checkpoint == "none":
        yield None
        return
    if checkpoint == "memory":
        try:
            from langgraph.checkpoint.memory import InMemorySaver
        except ModuleNotFoundError:
            yield None
            return
        yield InMemorySaver()
        return
    if checkpoint == "sqlite":
        try:
            from langgraph.checkpoint.sqlite import SqliteSaver
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "SQLite checkpointing requires `langgraph-checkpoint-sqlite`. "
                "Install with `python -m pip install -e .[checkpoint]`."
            ) from exc
        path = checkpoint_db or Path(".tmp/langgraph-checkpoints.sqlite")
        path.parent.mkdir(parents=True, exist_ok=True)
        with SqliteSaver.from_conn_string(str(path)) as saver:
            yield saver
        return
    yield None


def init_run(state: KnowledgeGraphState) -> KnowledgeGraphState:
    run_id = state.get("run_id") or uuid.uuid4().hex[:12]
    started_at = state.get("started_at") or utc_now()
    source_configs = select_sources(state.get("sources", []))
    thread_id = state.get("thread_id") or f"mygk-{date_from_timestamp(started_at)}-{run_id}"
    print(f"\n{'#' * 60}")
    print(f"# AI 知识库 LangGraph 流水线 — {started_at}")
    print(f"# Run ID: {run_id} | Thread: {thread_id}")
    print(f"# 数据源: {', '.join(state.get('sources', []))} | 限制: {state.get('limit')} | DryRun: {state.get('dry_run')}")
    print(f"{'#' * 60}")
    return {
        "run_id": run_id,
        "thread_id": thread_id,
        "started_at": started_at,
        "source_configs": source_configs,
        "repair_rounds": int(state.get("repair_rounds", 0)),
        "raw_batches": [],
        "analyzed_items": [],
        "review_passed_files": [],
        "filtered_items": [],
        "errors": [],
    }


def route_collectors(state: KnowledgeGraphState) -> list[Any] | str:
    _, _, _, Send = _load_langgraph()
    source_configs = state.get("source_configs") or select_sources(state.get("sources", []))
    if not source_configs:
        return "merge_raw_batches"
    return [
        Send(
            "collect_source_node",
            {
                "source_config": source_config,
                "limit": state.get("limit", 20),
                "repair_round": state.get("repair_rounds", 0),
            },
        )
        for source_config in source_configs
    ]


def collect_source_node(state: CollectTaskState) -> KnowledgeGraphState:
    source_config = state["source_config"]
    limit = int(state.get("limit", 20))
    repair_round = int(state.get("repair_round", 0))
    print(f"[Graph] collect_source started: {source_config.id}")
    try:
        batch = collect_source(source_config, limit)
        batch["_graph_round"] = repair_round
        print(f"[Graph] collect_source completed: {source_config.id} ({batch.get('count', 0)} items)")
        errors = batch.get("errors", [])
        return {"raw_batches": [batch], "errors": list(errors)}
    except Exception as exc:  # pragma: no cover - defensive boundary
        logger.exception("Collector failed for %s", source_config.id)
        return {
            "raw_batches": [],
            "errors": [{"source": source_config.id, "reason": "source_fetch_failed", "detail": str(exc)}],
        }


def merge_raw_batches(state: KnowledgeGraphState) -> KnowledgeGraphState:
    print("[Graph] merge_raw_batches started")
    seen: set[str] = set()
    merged: list[dict[str, Any]] = []
    current_round = int(state.get("repair_rounds", 0))
    for batch in state.get("raw_batches", []):
        if int(batch.get("_graph_round", 0)) != current_round:
            continue
        for item in batch.get("items", []):
            key = str(item.get("url") or item.get("id") or "")
            if not key or key in seen:
                continue
            seen.add(key)
            merged.append({**item, "_graph_round": current_round})
    if not state.get("dry_run", False):
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        raw_file = RAW_DIR / f"raw-graph-{timestamp}.json"
        raw_file.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[Graph] merge_raw_batches completed: {len(merged)} items")
    return {"raw_items": merged}


def route_analyzers(state: KnowledgeGraphState) -> list[Any] | str:
    _, _, _, Send = _load_langgraph()
    raw_items = state.get("raw_items", [])
    if not raw_items:
        return "organize_batch"
    return [Send("analyze_item_node", {"item": item}) for item in raw_items]


def analyze_item_node(state: AnalyzeTaskState) -> KnowledgeGraphState:
    item = state["item"]
    print(f"[Graph] analyze_item started: {str(item.get('title', item.get('id', '')))[:60]}")
    analyzed = analyze_item(item, model=os.getenv("CODEX_MODEL"), fallback_on_failure=False)
    if analyzed.get("analysis_failed"):
        print(f"[Graph] analyze_item failed: {item.get('title', item.get('id'))}")
        error = {
            "source_id": item.get("id", ""),
            "title": item.get("title", ""),
            "reason": "analysis_failed",
            "detail": analyzed.get("analysis_error", ""),
        }
        return {"filtered_items": [error], "errors": [error]}
    return {"analyzed_items": [{**analyzed, "_graph_round": item.get("_graph_round", 0)}]}


def organize_batch(state: KnowledgeGraphState) -> KnowledgeGraphState:
    current_round = int(state.get("repair_rounds", 0))
    current_items = [
        item
        for item in state.get("analyzed_items", [])
        if int(item.get("_graph_round", 0)) == current_round
    ]
    print(f"[Graph] organize_batch started: {len(current_items)} items")
    organized = organize_items(current_items)
    print(f"[Graph] organize_batch completed: {len(organized)} items")
    return {"organized_items": organized}


def publish_batch(state: KnowledgeGraphState) -> KnowledgeGraphState:
    print(f"[Graph] publish_batch started: {len(state.get('organized_items', []))} items")
    result = publish_items(state.get("organized_items", []), dry_run=bool(state.get("dry_run", False)))
    saved_files = [str(path) for path in result.saved_files]
    filtered_items = list(result.filtered_items)
    print(f"[Graph] publish_batch completed: {len(saved_files)} files")
    return {"saved_files": saved_files, "filtered_items": filtered_items}


def review_batch(state: KnowledgeGraphState) -> KnowledgeGraphState:
    if state.get("dry_run") or not state.get("auto_review", True):
        return {"review_passed_files": list(state.get("saved_files", [])), "rejected_items": []}
    filepaths = [Path(path) for path in state.get("saved_files", [])]
    print(f"[Graph] review_batch started: {len(filepaths)} files")
    passed, rejected = review_saved_articles(filepaths, write_manual_review_log=True)
    print(f"[Graph] review_batch completed: passed={len(passed)} rejected={len(rejected)}")
    return {"review_passed_files": [str(path) for path in passed], "rejected_items": rejected}


def repair_router(state: KnowledgeGraphState) -> str:
    rejected = state.get("rejected_items", [])
    repair_rounds = int(state.get("repair_rounds", 0))
    if (
        rejected
        and state.get("repair_on_failure", True)
        and repair_rounds < int(state.get("max_review_attempts", 3))
        and not state.get("dry_run")
    ):
        return "repair_collect"
    return "finalize_stats"


def repair_collect(state: KnowledgeGraphState) -> KnowledgeGraphState:
    rejected = state.get("rejected_items", [])
    remove_rejected_files(rejected)
    repair_round = int(state.get("repair_rounds", 0)) + 1
    target_count = len(
        [
            item
            for item in rejected
            if item.get("reason") not in {"duplicate url", "analysis_failed"}
        ]
    )
    if target_count <= 0:
        return {"repair_rounds": repair_round, "rejected_items": []}
    repair_limit = max(target_count * (repair_round + 2), target_count + 2)
    print(f"[Graph] repair_round started: {repair_round} target={target_count} limit={repair_limit}")
    raw_batches: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for source_config in state.get("source_configs", []):
        try:
            batch = collect_source(source_config, repair_limit)
            batch["_graph_round"] = repair_round
            raw_batches.append(batch)
            errors.extend(batch.get("errors", []))
        except Exception as exc:  # pragma: no cover - defensive boundary
            errors.append({"source": source_config.id, "reason": "source_fetch_failed", "detail": str(exc)})
    return {
        "repair_rounds": repair_round,
        "raw_batches": raw_batches,
        "raw_items": [],
        "analyzed_items": [],
        "organized_items": [],
        "saved_files": [],
        "rejected_items": [],
        "errors": errors,
    }


def _write_errors(errors: list[dict[str, Any]]) -> None:
    if not errors:
        return
    now = utc_now()
    json_dump(
        RAW_DIR / f"errors-{date_from_timestamp(now)}.json",
        {"date": date_from_timestamp(now), "errored_at": now, "items": errors},
    )


def finalize_stats(state: KnowledgeGraphState) -> KnowledgeGraphState:
    if state.get("rejected_items") and not state.get("dry_run"):
        remove_rejected_files(state.get("rejected_items", []))
    errors = state.get("errors", [])
    _write_errors(errors)
    started_at = datetime.fromisoformat(state["started_at"].replace("Z", "+00:00"))
    elapsed = (datetime.now(timezone.utc) - started_at.astimezone(timezone.utc)).total_seconds()
    saved_count = len(state.get("review_passed_files") or state.get("saved_files", []))
    stats = {
        "collected": len(state.get("raw_items", [])),
        "analyzed": len(state.get("analyzed_items", [])),
        "organized": len(state.get("organized_items", [])),
        "saved": saved_count,
        "review_passed": len(state.get("review_passed_files", [])) if state.get("auto_review", True) and not state.get("dry_run") else len(state.get("saved_files", [])),
        "review_failed": len(state.get("rejected_items", [])),
        "repair_rounds": int(state.get("repair_rounds", 0)),
        "elapsed_seconds": round(elapsed, 1),
        "dry_run": bool(state.get("dry_run", False)),
        "engine": "graph",
        "run_id": state.get("run_id", ""),
        "errors_count": len(errors),
    }
    print(f"\n{'#' * 60}")
    print(f"# LangGraph 流水线完成！耗时 {stats['elapsed_seconds']} 秒")
    print(
        f"# 采集: {stats['collected']} → 分析: {stats['analyzed']} "
        f"→ 整理: {stats['organized']} → 保存: {stats['saved']}"
    )
    print(f"# 错误: {stats['errors_count']} | 修正轮次: {stats['repair_rounds']}")
    print(f"{'#' * 60}\n")
    return {"stats": stats}


def build_graph(
    *,
    checkpointer: Any = None,
    checkpoint: Literal["none", "memory", "sqlite"] | None = None,
    checkpoint_db: Path | None = None,
) -> Any:
    StateGraph, START, END, _ = _load_langgraph()
    graph = StateGraph(KnowledgeGraphState)
    graph.add_node("init_run", init_run)
    graph.add_node("collect_source_node", collect_source_node)
    graph.add_node("merge_raw_batches", merge_raw_batches)
    graph.add_node("analyze_item_node", analyze_item_node)
    graph.add_node("organize_batch", organize_batch)
    graph.add_node("publish_batch", publish_batch)
    graph.add_node("review_batch", review_batch)
    graph.add_node("repair_collect", repair_collect)
    graph.add_node("finalize_stats", finalize_stats)

    graph.add_edge(START, "init_run")
    graph.add_conditional_edges("init_run", route_collectors, ["collect_source_node", "merge_raw_batches"])
    graph.add_edge("collect_source_node", "merge_raw_batches")
    graph.add_conditional_edges("merge_raw_batches", route_analyzers, ["analyze_item_node", "organize_batch"])
    graph.add_edge("analyze_item_node", "organize_batch")
    graph.add_edge("organize_batch", "publish_batch")
    graph.add_edge("publish_batch", "review_batch")
    graph.add_conditional_edges(
        "review_batch",
        repair_router,
        {"repair_collect": "repair_collect", "finalize_stats": "finalize_stats"},
    )
    graph.add_edge("repair_collect", "merge_raw_batches")
    graph.add_edge("finalize_stats", END)

    if checkpointer is None and checkpoint is not None:
        if checkpoint == "sqlite":
            raise RuntimeError("SQLite checkpointing must be used through run_graph_pipeline().")
        with _checkpoint_saver(checkpoint, checkpoint_db) as saver:
            return graph.compile(checkpointer=saver)
    return graph.compile(checkpointer=checkpointer)


def run_graph_pipeline(
    *,
    sources: list[str],
    limit: int = 20,
    dry_run: bool = False,
    auto_review: bool = True,
    repair_on_failure: bool = True,
    max_review_attempts: int = 3,
    checkpoint: Literal["none", "memory", "sqlite"] = "memory",
    checkpoint_db: Path | None = None,
) -> dict[str, Any]:
    started_at = utc_now()
    run_id = uuid.uuid4().hex[:12]
    thread_id = f"mygk-{date_from_timestamp(started_at)}-{run_id}"
    initial_state: KnowledgeGraphState = {
        "run_id": run_id,
        "thread_id": thread_id,
        "started_at": started_at,
        "sources": sources,
        "limit": limit,
        "dry_run": dry_run,
        "auto_review": auto_review,
        "repair_on_failure": repair_on_failure,
        "max_review_attempts": max_review_attempts,
        "repair_rounds": 0,
        "raw_batches": [],
        "raw_items": [],
        "analyzed_items": [],
        "organized_items": [],
        "saved_files": [],
        "review_passed_files": [],
        "rejected_items": [],
        "filtered_items": [],
        "errors": [],
        "stats": {},
    }
    config = {"configurable": {"thread_id": thread_id}}
    with _checkpoint_saver(checkpoint, checkpoint_db) as checkpointer:
        compiled = build_graph(checkpointer=checkpointer)
        result = compiled.invoke(initial_state, config=config)
    return result.get("stats", {})


def main() -> None:
    parser = argparse.ArgumentParser(description="LangGraph AI 知识库采集流水线")
    parser.add_argument("--sources", type=str, default="github,rss", help="数据源，逗号分隔（默认: github,rss）")
    parser.add_argument("--limit", type=int, default=20, help="每个源的最大采集数量（默认: 20）")
    parser.add_argument("--dry-run", action="store_true", help="仅模拟运行，不实际保存文件")
    parser.add_argument("--verbose", action="store_true", help="显示详细日志")
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
    run_graph_pipeline(
        sources=parse_sources(args.sources),
        limit=args.limit,
        dry_run=args.dry_run,
        auto_review=not args.skip_review,
        repair_on_failure=not args.skip_repair,
        max_review_attempts=max(0, args.max_review_attempts),
        checkpoint=args.checkpoint,
        checkpoint_db=Path(args.checkpoint_db),
    )


if __name__ == "__main__":
    main()
