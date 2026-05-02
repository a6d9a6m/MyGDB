---
name: hacker-news-top
description: 用于从 Hacker News Top Stories 中筛选 AI/LLM/Agent 相关条目的采集方法说明
---

# Hacker News Top Skill

本 skill 只定义 **Hacker News Top Stories 采集方法**，不定义 Collector 的角色边界。

## 适用场景

- 任务明确要求采集 Hacker News 热门 AI 相关文章。
- 需要生成可交给 Analyzer 的 HN raw batch。

## 输入

- Top Stories 抽样数量，默认 50。
- AI 相关关键词集合。
- 最终保留数量，建议 10-15 条。

## 执行步骤

### 1. 读取 Top Stories

先获取 Top Stories ID 列表，再逐条读取详情。

### 2. 关键词筛选

建议关键词：
- `AI`
- `LLM`
- `agent`
- `GPT`
- `Claude`
- `model`
- `RAG`
- `OpenAI`
- `Anthropic`

### 3. 质量过滤

优先保留：
- 标题明确与 AI/LLM/Agent 相关
- 有外链或正文内容
- 有一定热度和讨论量

优先剔除：
- 与 AI 关系极弱的泛技术新闻
- 仅短句、几乎无上下文的占位帖
- 明显重复讨论同一链接的低质量条目

### 4. 标准化字段

输出必须符合 `.codex/contracts/knowledge-base.md`。

每个 item 至少提取：
- `id`
- `title`
- `url`
- `collected_at`

推荐补充：
- `score`
- `comments`
- `author`
- `time`

### 5. 输出检查

- `id` 不重复。
- `count` 与 `items.length` 一致。
- 保留原始热度信息。
- 对没有 `url` 的条目，只有在正文价值明确时才保留。

## 异常处理

- 单条详情获取失败：跳过并记录。
- Top Stories 接口短暂失败：最多重试 3 次。
- 结果过少：放宽关键词但保持 AI 相关性。
