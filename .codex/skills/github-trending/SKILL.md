---
name: github-trending
description: 用于从 GitHub Search / Trending 语义中采集 AI/LLM/Agent 相关热门仓库的方法说明
---

# GitHub Trending Skill

本 skill 只定义 **GitHub 热门仓库采集方法**，不定义 Collector 的角色边界。

## 适用场景

- 任务明确要求采集 GitHub Trending 或 GitHub 热门仓库。
- 任务要求获得可交给 Analyzer 的 GitHub raw batch。

## 输入

- 时间窗口，默认近 7 天。
- 关键词范围，默认聚焦 AI / LLM / Agent / RAG / MCP。
- 数量上限，默认 20，最多建议 30。

## 执行步骤

### 1. 构造查询

默认关键词：
- `AI`
- `LLM`
- `agent`
- `"large language model"`
- `RAG`
- `MCP`
- `"model context protocol"`
- `agentic`

默认规则：
- `sort=stars`
- `order=desc`
- `per_page=20`

可使用 GitHub Search API：

```text
GET https://api.github.com/search/repositories
```

## 2. 过滤结果

优先保留：
- 非 fork 仓库
- 有清晰 description 的仓库
- 与 AI/LLM/Agent 主题明显相关的仓库
- 热度较高或近一周明显增长的仓库

优先剔除：
- 纯 awesome-list
- 明显课程作业、个人备份、模板空壳
- 与用户目标弱相关的泛技术仓库

## 3. 标准化字段

输出必须符合 `.codex/contracts/knowledge-base.md` 中的 raw batch / raw item。

每个 item 至少提取：
- `id`
- `title`
- `description`
- `url`
- `collected_at`

推荐补充：
- `stars`
- `language`
- `topics`
- `created_at`
- `updated_at`

## 4. 轻量增强

仅在能明显提升后续摘要质量时，才额外读取 README 摘录。

增强原则：
- 只给 Top 5 仓库做增强。
- 只取前 300-500 字摘要。
- 不要把采集阶段变成深度分析阶段。

## 5. 输出检查

- 批次内 `id` 不重复。
- `url` 使用 `https://`。
- 热度字段保持数值类型。
- `count` 与 `items.length` 一致。

## 异常处理

- 401：说明认证失败，记录错误并停止当前来源。
- 403 / 限流：记录限流状态，可短暂重试，最多 3 次。
- 422：说明查询条件过宽或格式异常，应收紧查询。
- 单仓库详情获取失败：跳过单条并保留错误摘要。
