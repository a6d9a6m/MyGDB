---
name: article-publish
description: 用于将 analyzed items 过滤、去重、编号并发布为知识库标准 JSON 的方法说明
---

# Article Publish Skill

本 skill 只定义 **归档发布方法**，不定义 Organizer 的角色边界。

## 适用场景

- 已经有 analyzed batch。
- 需要生成 article 文件、更新 index，并记录 filtered log。

## 输入

- 符合 `.codex/contracts/knowledge-base.md` 的 analyzed item / analyzed batch。
- 现有 `knowledge/articles/index.json`。
- 现有 `knowledge/articles/*.json`。

## 输出

- 发布后的 article files
- 更新后的 `index.json`
- `filtered-{date}.json`

## 执行步骤

### 1. 验证 contract

逐条检查 analyzed item 是否具备：
- `id`
- `title`
- `url`
- `summary`
- `relevance_score`
- `tags`
- `analyzed_at`

缺字段条目：
- 标记为 `incomplete`
- 记录到过滤日志
- 不发布

### 2. 质量过滤

默认过滤规则：
- `relevance_score < 0.60`
- `summary` 过短或没有有效信息
- `tags` 少于 2 个
- `url` 无效或为空

### 3. 去重

优先级：
1. `url` 完全相同则视为重复
2. `title` 高度相似时人工保守判断为重复

所有去重决策都要写入 filtered log。

### 4. 生成 article 字段

按 contract 组装 article item，并补充：
- `source`
- `source_id`
- `organized_at`
- `status = "published"`

### 5. 生成 ID 与 slug

ID：
- `kb-{YYYY-MM-DD}-{三位序号}`

slug：
- 标题转英文小写
- 空格转连字符
- 去掉特殊字符
- 保持简洁可读

### 6. 写入 article

路径：
- `knowledge/articles/{YYYY-MM-DD}-{slug}.json`

要求：
- 2 空格缩进
- UTF-8
- 文件名与正文日期一致

### 7. 更新 index

索引必须：
- 增量更新
- 按 `organized_at` 降序
- `total_count` 与实际文件数一致

## 输出检查

- article、index、filtered log 三者相互一致。
- 没有重复 `id`。
- 没有重复 `url`。
- 所有 tags 格式合法。
