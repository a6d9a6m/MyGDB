# Knowledge Base Contract

本文件是 AI 知识库流水线的唯一数据契约真源。

## 1. Raw Batch

Collector 的标准输出是一个 raw batch。

```json
{
  "source": "github-trending",
  "collected_at": "2026-05-01T08:00:00Z",
  "query": "AI OR LLM OR agent, past 7 days, sorted by stars",
  "count": 20,
  "items": []
}
```

### 必填字段
- `source`: 数据源标识，例如 `github-trending`、`hackernews-top`
- `collected_at`: 本批次采集时间
- `count`: 条目数量
- `items`: 原始候选条目数组

### 推荐字段
- `query`: 查询条件或筛选策略摘要
- `errors`: 采集过程中的局部错误数组

## 2. Raw Item

raw item 是尚未分析的候选条目。

```json
{
  "id": "openai/agents-sdk",
  "title": "agents-sdk",
  "description": "OpenAI Agents SDK for building agentic AI applications",
  "url": "https://github.com/openai/agents-sdk",
  "collected_at": "2026-05-01T08:00:00Z"
}
```

### 必填字段
- `id`
- `title`
- `url`
- `collected_at`

### 来源增强字段
- GitHub 常见字段：`stars`, `language`, `topics`, `created_at`, `updated_at`
- Hacker News 常见字段：`score`, `comments`, `author`, `time`

## 3. Analyzed Item

Analyzer 的标准输出是在 raw item 上补充分析字段。

```json
{
  "id": "openai/agents-sdk",
  "title": "agents-sdk",
  "description": "OpenAI Agents SDK for building agentic AI applications",
  "url": "https://github.com/openai/agents-sdk",
  "collected_at": "2026-05-01T08:00:00Z",
  "summary": "OpenAI 官方发布的 Agent 开发 SDK，核心价值在于把多 Agent 协作、任务交接与守护逻辑抽象成可复用组件，适合需要快速搭建 agent workflow 的工程团队。",
  "relevance_score": 0.87,
  "score_breakdown": {
    "tech_depth": 0.80,
    "practical_value": 0.95,
    "timeliness": 0.90,
    "community_heat": 0.85,
    "domain_match": 0.95
  },
  "tags": ["agent-framework", "multi-agent", "python", "openai"],
  "analyzed_at": "2026-05-01T08:30:00Z"
}
```

### 新增必填字段
- `summary`
- `relevance_score`
- `score_breakdown`
- `tags`
- `analyzed_at`

### `score_breakdown` 必须包含
- `tech_depth`
- `practical_value`
- `timeliness`
- `community_heat`
- `domain_match`

## 4. Article Item

Organizer 发布到知识库的正式条目。

```json
{
  "id": "kb-2026-05-01-001",
  "title": "OpenAI Agents SDK",
  "source": "github-trending",
  "source_id": "openai/agents-sdk",
  "url": "https://github.com/openai/agents-sdk",
  "summary": "OpenAI 官方发布的 Agent 开发 SDK，核心价值在于把多 Agent 协作、任务交接与守护逻辑抽象成可复用组件，适合需要快速搭建 agent workflow 的工程团队。",
  "tags": ["agent-framework", "multi-agent", "python", "openai"],
  "relevance_score": 0.87,
  "collected_at": "2026-05-01T08:00:00Z",
  "analyzed_at": "2026-05-01T08:30:00Z",
  "organized_at": "2026-05-01T09:00:00Z",
  "status": "published"
}
```

### 必填字段
- `id`
- `title`
- `source`
- `source_id`
- `url`
- `summary`
- `tags`
- `relevance_score`
- `collected_at`
- `analyzed_at`
- `organized_at`
- `status`

### 规则
- `id` 采用 `kb-{YYYY-MM-DD}-{三位序号}`。
- `status` 默认使用 `published`。
- `source_id` 必须保留原始来源条目标识。

## 5. Index File

`knowledge/articles/index.json` 的标准结构如下：

```json
{
  "last_updated": "2026-05-01T09:00:00Z",
  "total_count": 42,
  "entries": [
    {
      "id": "kb-2026-05-01-001",
      "title": "OpenAI Agents SDK",
      "file": "2026-05-01-openai-agents-sdk.json",
      "tags": ["agent-framework", "multi-agent"],
      "relevance_score": 0.87,
      "organized_at": "2026-05-01T09:00:00Z"
    }
  ]
}
```

### 规则
- `entries` 按 `organized_at` 降序。
- `total_count` 必须等于实际已发布条目数。

## 6. Filtered Log

Organizer 过滤掉的条目必须记录到日志中。

```json
{
  "date": "2026-05-01",
  "filtered_at": "2026-05-01T09:00:00Z",
  "items": [
    {
      "source_id": "foo/bar",
      "title": "Example",
      "reason": "relevance_score below 0.60"
    }
  ]
}
```

### 必填字段
- `date`
- `filtered_at`
- `items`

### `items[]` 必须至少记录
- `source_id` 或原始 `id`
- `title`
- `reason`

## 7. 通用验证规则

- 所有时间字段使用 ISO 8601 UTC。
- 所有 JSON 使用 2 空格缩进。
- `tags` 必须为英文小写。
- 多词标签使用连字符，例如 `large-language-model`。
- `relevance_score` 范围必须在 `0.00` 到 `1.00`。

## 8. 流水线边界

- Collector 只生成 Raw Batch / Raw Item。
- Analyzer 只补充 Analyzed Item 字段。
- Organizer 才能生成 Article Item、Index File、Filtered Log。

## 9. Source Registry

Graph pipeline 使用统一 source registry 描述来源配置。当前 RSS registry
仍位于 `src/MyGK_DB/pipeline/rss/rss_sources.yaml`，GitHub Trending 由代码内置默认项提供。

每个 source entry 的标准字段：

- `id`: 来源稳定标识，例如 `github-trending` 或 `rss:langchain-blog`
- `type`: `github` 或 `rss`
- `name`: 人类可读名称
- `enabled`: 是否启用
- `category`: 来源类别，例如 `open-source`、`research`、`industry`
- `trust_tier`: `high`、`medium`、`low`
- `limit`: 单来源默认采集上限，可省略
- `keywords`: 关键词范围
- `quality_weight`: 来源质量权重，默认 `1.0`

RSS source 额外字段：

- `url`
- `parser`: 默认 `rss`
- `fetch_timeout_seconds`

GitHub source 额外字段：

- `query_keywords`
- `min_stars`
- `pushed_within_days`
- `include_readme_top_n`

## 10. Error Log

Graph pipeline 中外部请求失败、分析失败、节点异常等错误写入：

```text
knowledge/raw/errors-{YYYY-MM-DD}.json
```

结构：

```json
{
  "date": "2026-05-14",
  "errored_at": "2026-05-14T08:00:00Z",
  "items": [
    {
      "source_id": "example",
      "title": "Example",
      "reason": "analysis_failed",
      "detail": "error summary"
    }
  ]
}
```

错误日志只记录失败事实，不改变已发布 article。

## 11. Manual Review Queue

Reviewer 可将需要人工判断的条目写入：

```text
knowledge/raw/review-required-{YYYY-MM-DD}.json
```

结构：

```json
{
  "date": "2026-05-14",
  "review_required_at": "2026-05-14T08:00:00Z",
  "items": [
    {
      "filepath": "knowledge/articles/2026-05-14-example.json",
      "source_id": "example",
      "title": "Example",
      "reason": "low trust source with high score",
      "quality_grade": "B",
      "quality_score": 65.0
    }
  ]
}
```

进入人工复核队列的条目不得进入最终发布索引。
