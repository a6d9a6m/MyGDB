# AGENTS.md — AI 知识库项目

> 本文件是项目级记忆，负责定义目标、数据契约边界、Agent 协作原则，以及各类能力的职责划分。

## 项目定义

**MyGK_DB（AI 知识库）** 是一个自动化技术情报收集与整理系统。
它持续追踪 GitHub Trending、Hacker News、arXiv 等来源，将分散的技术资讯
转化为结构化、可检索、可归档的 JSON 知识条目。

### 核心价值
- 每日自动收集 AI/LLM/Agent 领域的高质量文章与开源项目。
- 通过多 Agent 协作完成“采集 → 分析 → 归档”的单向流水线。
- 产出统一格式的 JSON 条目，便于后续检索、展示与二次消费。

### 设计原则
- **Agent 管边界**：定义角色、输入、输出、禁止事项。
- **Skill 管方法**：定义某类任务的执行步骤、质量标准、异常处理。
- **Contract 管格式**：定义流水线中所有 JSON 结构与字段语义。

## 数据目录

```text
knowledge/
├── raw/                    # 原始采集结果、分析中间结果、过滤日志
└── articles/               # 最终发布的知识条目与 index.json
```

## 数据生命周期

```text
[Collector]
  -> 生成 raw batch
  -> 写入或返回 knowledge/raw/*-YYYY-MM-DD.json

[Analyzer]
  -> 读取 raw batch
  -> 为 item 补充 summary / tags / score
  -> 形成 analyzed batch

[Organizer]
  -> 读取 analyzed batch
  -> 过滤、去重、编号、归档
  -> 输出 knowledge/articles/*.json 与 index.json
```

### 严格规则
1. **单向流动**：Collector → Analyzer → Organizer，不允许反向修改上游语义。
2. **职责隔离**：Collector 不分析，Analyzer 不归档，Organizer 不补抓外部信息。
3. **格式统一**：所有结构必须遵循 `.codex/contracts/knowledge-base.md`。
4. **幂等优先**：同一天重复执行时，不能制造重复知识条目。
5. **可追溯性**：每个最终条目都必须能回溯到 `source`、`source_id`、`url`、`collected_at`。

## 文件命名规范

### 原始采集批次
- `knowledge/raw/{source}-{YYYY-MM-DD}.json`
- 例：`knowledge/raw/github-trending-2026-05-01.json`
- 例：`knowledge/raw/hackernews-top-2026-05-01.json`

### 过滤日志
- `knowledge/raw/filtered-{YYYY-MM-DD}.json`

### 错误日志
- `knowledge/raw/errors-{YYYY-MM-DD}.json`

### 最终知识条目
- `knowledge/articles/{YYYY-MM-DD}-{slug}.json`
- 例：`knowledge/articles/2026-05-01-openai-agents-sdk.json`

### 索引文件
- `knowledge/articles/index.json`

## JSON 通用规范

- 使用 2 空格缩进。
- 日期统一使用 ISO 8601 UTC 格式：`YYYY-MM-DDTHH:mm:ssZ`
- 文件编码统一为 UTF-8。
- JSON key、代码、文件名使用英文。
- 摘要、分析、注释说明以中文为主。
- 标签 `tags` 使用英文小写，多个单词用连字符连接。

## 评分与质量门槛

- Analyzer 负责生成 `relevance_score` 与 `score_breakdown`。
- Organizer 负责执行最终过滤。
- 默认过滤门槛：`relevance_score < 0.60` 的条目不进入正式知识库。
- 如有例外，必须在日志中说明原因。

## 错误处理

- 外部请求失败：记录错误并跳过单条，不中断整批流程。
- API 限流：按来源规则重试，最多 3 次。
- 数据格式异常：记录到 `knowledge/raw/errors-{YYYY-MM-DD}.json`。
- 字段缺失：Analyzer 可保守分析；Organizer 必须决定过滤或标记 `incomplete`。

## Agent 协作约定

### Collector
- 输入：来源范围、时间范围、数量限制、必要的关键词条件。
- 输出：符合 contract 的 raw batch。
- 不负责分析、评分、归档。

### Analyzer
- 输入：raw batch 或其中的候选条目。
- 输出：符合 contract 的 analyzed item / analyzed batch。
- 不负责最终写盘发布。

### Organizer
- 输入：analyzed batch。
- 输出：标准 article JSON、index 更新、filtered log。
- 不负责外部抓取或重新解释上游事实。

## 统一真源

以下文件是当前系统的真源：
- 角色边界：`.codex/agents/*.toml`
- 执行方法：`.codex/skills/*/SKILL.md`
- 数据结构：`.codex/contracts/knowledge-base.md`
- Hook 管理：`.codex/requirements.toml`
- Python 包与入口配置：`pyproject.toml`

如三者发生冲突，优先级为：
1. `.codex/contracts/knowledge-base.md`
2. 当前 Agent 的 `developer_instructions`
3. 对应 Skill 的执行建议

## 维护原则

- 优先修改 contract，再让 agent/skill 引用 contract。
- 避免把同一规则复制到多个文件中。
- 任何新增来源、评分规则或输出格式，都应先更新 contract，再补 skill。

## 运行环境与包约定

- 本仓库采用 `src/` 布局，主包为 `MyGK_DB`。
- 根目录 `pyproject.toml` 是 Python 包元数据、依赖与命令行入口的真源。
- `pyproject.toml` 的 `[tool.mygk-db.env]` 记录仓库脚本与 CI 需要的环境变量。
- 运行流水线优先使用 `python -m MyGK_DB.pipeline.pipeline` 或安装后的 `mygk-pipeline`。
- 运行 MCP 服务优先使用 `python -m MyGK_DB.mcp_knowledge_server` 或安装后的 `mygk-mcp-server`。
- 包内模块必须使用相对导入或完整包路径导入，不再通过修改 `sys.path` 兼容外部脚本布局。
- 各级包目录需要保留 `__init__.py`，只暴露稳定入口，避免在包初始化阶段执行采集、分析或写盘逻辑。
- Codex hook 定义使用 `.codex/requirements.toml` 的内联 TOML 格式，不使用 `hooks.toml` 或独立 `hooks.json`。
- `.codex/config.toml` 只保留普通项目配置；hook 开关与 hook 命令由 `.codex/requirements.toml` 统一管理。

## Agent 与模型调用约定

- 本仓库只使用 Codex CLI 作为 agent 支持入口。
- 不维护下载脚本中携带的 `model_client.py`、`create_provider`、`chat_with_retry`、`LLM_PROVIDER` 等多 provider 抽象。
- 需要模型能力的脚本应调用 Codex CLI，例如 `codex exec`，或把任务交给 `.codex/agents/*.toml` 定义的角色执行。
- 如需指定模型，使用 Codex CLI 的 `--model` 参数或仓库脚本中的 `CODEX_MODEL` 环境变量；本机 Codex 不在 PATH 时，用 `.env.local` 中的 `CODEX_BIN` 指向可执行文件。
- Python 代码负责采集、格式校验、文件组织与索引更新；摘要、标签、评分等智能分析能力交给 Codex agent。
