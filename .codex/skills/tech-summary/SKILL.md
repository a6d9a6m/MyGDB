---
name: tech-summary
description: 用于为候选技术条目生成中文摘要、标签和评分的方法说明
---

# Tech Summary Skill

本 skill 只定义 **技术摘要与评分方法**，不定义 Analyzer 的角色边界。

## 适用场景

- 已经有 raw batch 或 raw item。
- 需要生成中文摘要、英文标签、相关性评分。

## 输入

- 符合 `.codex/contracts/knowledge-base.md` 的 raw item。
- 可选的 README 摘录、文章正文片段、页面摘要。

## 输出

- 符合 contract 的 analyzed item。

## 执行步骤

### 1. 提取核心信息

优先理解以下内容：
- 这是什么
- 解决什么问题
- 技术方案或工程亮点是什么
- 对 AI/LLM/Agent 工程实践的价值是什么

### 2. 生成摘要

摘要要求：
- 使用中文。
- 100-200 字为宜。
- 直接进入主题，不要写“这是一篇介绍……”之类空泛开场。
- 技术术语可以保留英文原文。
- 优先写事实、用途和适用场景，不要写宣传式话术。

### 3. 提取标签

标签规则：
- 3-5 个。
- 全部英文小写。
- 多词标签使用连字符。

建议覆盖三类信息：
- 技术方向，例如 `rag`、`mcp`、`multi-agent`
- 应用场景，例如 `code-generation`、`document-qa`
- 技术栈，例如 `python`、`typescript`、`openai`

### 4. 打分

评分维度：
- `tech_depth`：技术深度，权重 0.25
- `practical_value`：实用价值，权重 0.30
- `timeliness`：时效性，权重 0.20
- `community_heat`：社区热度，权重 0.15
- `domain_match`：领域匹配度，权重 0.10

总分公式：

```text
relevance_score = tech_depth * 0.25
                + practical_value * 0.30
                + timeliness * 0.20
                + community_heat * 0.15
                + domain_match * 0.10
```

### 5. 输出检查

- `summary` 为中文。
- `relevance_score` 范围在 0.00-1.00。
- `score_breakdown` 含全部 5 个维度。
- `tags` 数量 3-5，格式正确。
- `analyzed_at` 使用 ISO 8601。

## 写作准则

- 先判断事实，再组织表达。
- 如果信息不足，保守表述，不做夸大推断。
- 不因热度高就自动给高分。
- 评分是绝对判断，不是相对排名。
