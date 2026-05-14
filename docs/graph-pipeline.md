# LangGraph Pipeline

MyGK_DB 的 graph engine 将现有知识库流水线升级为多 agent 编排，但保留
`.codex/contracts/knowledge-base.md` 和 `knowledge_contract.py` 作为数据契约真源。

## Nodes

- `init_run`: 初始化 run id、thread id、source registry。
- `collect_source_node`: Collector agent，采集 GitHub 或 RSS raw batch。
- `merge_raw_batches`: 合并 raw batch，并按 URL/source id 去重。
- `analyze_item_node`: Analyzer agent，通过 Codex CLI 生成 summary/tags/score。
- `organize_batch`: Organizer agent，标准化 analyzed item 并排除重复。
- `publish_batch`: Publisher agent，唯一写入 `knowledge/articles` 和 `index.json` 的节点。
- `review_batch`: Reviewer agent，执行 contract 和质量门禁。
- `repair_collect`: Supervisor repair 分支，按失败情况补采替换候选。
- `finalize_stats`: 汇总统计并写入错误日志。

## CLI

```bash
mygk-pipeline --engine graph --sources github,rss --limit 20
mygk-graph-pipeline --sources rss --limit 5 --dry-run --skip-review
```

Checkpoint:

```bash
mygk-pipeline --engine graph --checkpoint memory
mygk-pipeline --engine graph --checkpoint none
mygk-pipeline --engine graph --checkpoint sqlite --checkpoint-db .tmp/langgraph-checkpoints.sqlite
```

## Reliability Rules

- Collector 只输出 raw batch，不做摘要、评分或标签。
- Analyzer 是唯一生成 `summary`、`tags`、`relevance_score` 的节点。
- Publisher 是唯一写入 article/index 的节点。
- Reviewer 不重写上游事实，只做 passed/rejected/manual review 判断。
- Graph 模式下分析失败会进入 `knowledge/raw/errors-{date}.json`，不发布 fallback article。
- 人工复核条目进入 `knowledge/raw/review-required-{date}.json`，不进入最终索引。
