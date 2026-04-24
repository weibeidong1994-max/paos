# PAOS — Personal AI OS

个人AI操作系统（Personal AI Operating System）是一个以**本地计算为中枢、以多源输入为触角、以多态输出为目标**的智能工作流平台。

> 核心理念：把**你自己的认知和工作流**变成一个可运行、可迁移、可进化的系统。

---

## 🏗️ 系统架构

```
┌─────────────────────────────────────────┐
│  INPUT LAYER    输入层                  │
│  [自然语言] [OpenClaw] [社交媒体]       │
└─────────────────────────────────────────┘
                   ↓
┌─────────────────────────────────────────┐
│  PROCESS LAYER  处理层                  │
│  [信息提纯] [配置中心] [结构化存储]     │
└─────────────────────────────────────────┘
                   ↓
┌─────────────────────────────────────────┐
│  OUTPUT LAYER   输出层                  │
│  [文章生成] [网站/Demo] [App/H5]        │
└─────────────────────────────────────────┘
```

---

## 🚀 快速开始

### 1. 安装

```bash
./install.sh
```

### 2. 启动服务

```bash
source .venv/bin/activate
uvicorn paos.main:app --reload
```

服务默认运行在 http://127.0.0.1:8000

### 3. 测试输入

```bash
# 提交一段自然语言输入
curl -X POST http://127.0.0.1:8000/api/v1/input \
  -H "Content-Type: application/json" \
  -d '{"source": "natural_language", "data": {"content": "今天读到一篇文章，讲的是AI Agent的未来趋势，很有启发。"}}'
```

### 4. 生成文章

```bash
# 基于最近的存储内容生成一篇结构化文章
curl -X POST "http://127.0.0.1:8000/api/v1/generate/article?limit=5"
```

### 5. 本地模拟完整流程（不启动服务）

```bash
python scripts/simulate_workflow.py
```

---

## 🔌 MCP Server（供 OpenClaw 或其他 MCP Client 调用）

PAOS 已内置 MCP Server，可作为 **OpenClaw 调用 PAOS 的可选方案**（尤其适用于复杂多步操作场景）。日常输入仍建议通过 REST API 直接调用 PAOS。

### 启动 MCP Server

```bash
# stdio 模式
python -m paos.mcp_server

# SSE 模式（通过 HTTP 访问）
python -m paos.mcp_server --sse --host 127.0.0.1 --port 8001
```

### 已暴露的 MCP 工具

| 工具名 | 用途 |
|--------|------|
| `paos_list_index` | 查看全局目录索引 |
| `paos_list_fallback` | 查看 fallback 队列 |
| `paos_get_processed` | 按 ID 读取提纯记录 |
| `paos_health_check` | 检查 PAOS 健康状态（DB / 索引 / 目录） |
| `paos_add_note` | 添加运维日志 |
| `paos_complete_fallback` | 补全 fallback 并联动更新 |
| `paos_update_tags` | 更新标签并刷新汇总文件 |
| `paos_regenerate_summary` | 重新生成 `processed_summary.md` |
| `paos_generate_article` | 基于最近记录生成文章 |

> 💡 **架构说明**：
> - **OpenClaw** 是 PAOS 的对外接口层，用户通过 OpenClaw 使用 PAOS。
> - **Hermes** 是 PAOS 的开发者/运维管家，直接读写 `paos/` 代码库来管理和优化 PAOS 服务，不走 MCP。

---

## 📂 数据存储与目录映射

PAOS 采用**三重存储**机制，确保你的内容既结构化又可读、又可追溯：

| 层级 | 数据库存储 | Markdown 文件 | 说明 |
|------|-----------|---------------|------|
| **原始输入** | `paos.db` → `raw_input` | `data/raw/` | 保留你提交的原始内容 |
| **提纯知识** | `paos.db` → `processed_item` | `data/processed/` | LLM 提炼后的摘要和标签 |
| **生成输出** | - | `data/output/` | 最终生成的文章、Demo 等内容 |
| **提纯汇总** | - | `data/processed_summary.md` | 所有提纯知识的极简自动汇总 |

所有内容的关联关系统一由 **`data/index.json`** 维护，相当于整个系统的目录索引：

```json
[
  {
    "entry_id": "E00002",
    "raw_id": 2,
    "raw_file": "raw/20260414_165548_00002.md",
    "processed_id": 2,
    "processed_file": "processed/20260414_165548_00002.md",
    "source": "natural_language",
    "content_preview": "如果大模型本身是一个系统...",
    "distilled_preview": "将大模型视为一个系统时...",
    "output_files": {
      "article": "output/article_20260414_165646.md"
    }
  }
]
```

你可以随时通过 API 查询整个目录映射：

```bash
curl http://127.0.0.1:8000/api/v1/index
```

### 提纯知识汇总（`processed_summary.md`）

每次有新的输入经过 Pipeline，或 Agent Fallback 被补全后，系统都会自动重写 `data/processed_summary.md`，汇总所有已提纯的知识。格式极简：

```markdown
# 提纯知识汇总

### 2026-04-15 03:57 | natural_language
**标签**: 财富观念, 资产所有权, 被动收入, 个人成长
**摘要**: 真正的财富来源于拥有能产生现金流的资产，而非单纯出租时间换取薪酬。
```

---

## 🔧 配置中心

**所有配置项统一由 `paos/config/default.yaml` 管理，代码中无任何硬编码。**

修改 `default.yaml` 即可改变系统行为，无需改代码。

### 关键配置项

```yaml
server:
  host: "127.0.0.1"
  port: 8000

llm:
  provider: "openai"
  api_key: ""                # 填入你的 API Key，或通过环境变量传入
  model: "gpt-4o-mini"
  base_url: "https://api.openai.com/v1"

output:
  article:
    save_dir: "./data/output"   # 修改此处即可改变文章输出位置
```

### 环境变量覆盖

配置也支持通过环境变量覆盖，优先级：**环境变量 > `default.yaml`**

| 环境变量 | 说明 | 示例 |
|---------|------|------|
| `PAOS_DATA_DIR` | 用户数据目录 | `./data` |
| `PAOS_SERVER__HOST` / `PAOS_SERVER__PORT` | 服务监听地址/端口 | `127.0.0.1` / `8000` |
| `PAOS_LLM__API_KEY` / `OPENAI_API_KEY` | LLM API 密钥 | `sk-...` |
| `PAOS_LLM__MODEL` / `OPENAI_MODEL` | 默认模型 | `gpt-4o-mini` |
| `PAOS_LLM__BASE_URL` / `OPENAI_BASE_URL` | API 基础地址 | `https://api.openai.com/v1` |
| `PAOS_OUTPUT__ARTICLE__SAVE_DIR` | 文章输出目录 | `./data/output` |

> 💡 **设计原则**：所有代码中的路径、模型、接口地址均从配置中心读取，修改 `default.yaml` 即可生效。

---

## 🤖 Agent Fallback（无 LLM 配置时的兜底机制）

PAOS 内置了 **Agent Fallback Queue**：当你没有配置 OpenAI API Key，或者外部 LLM 接口失效时，系统不会直接报错，而是把请求写入本地队列 `data/fallback_queue/`，由对话中的 **Kimi Agent** 帮你处理。

### 工作原理

1. **提交输入**（系统检测到无 API Key 或接口失败）
2. **系统自动将 LLM 请求排入 `fallback_queue`**，同时关联 `processed_id` 和文件路径
3. **你在对话中喊 Kimi Agent 处理**
4. **Agent 生成结果并写回系统**
5. **系统联动更新**：SQLite 数据库、`processed/` Markdown 文件、`index.json`、以及 `processed_summary.md`

### 触发 Agent 补全的方法

#### 方法 1：一键生成提示语（推荐）

```bash
source .venv/bin/activate
python -m paos.cli.notify_agent
```

运行后，终端会自动输出一段提示语，你**直接复制到 Kimi CLI 对话里发送**即可。例如：

```
PAOS 当前有 1 个 pending 的 fallback 请求，请帮我处理并补全结果。

--- Request ID: 5298354f ---
任务类型: chat_completion
System Prompt:
你是一位信息提纯助手...
User Content:
如果大模型本身是一个系统...

处理完成后，请调用 `paos.core.fallback.complete_request(req_id, result)` 写回结果。
```

#### 方法 2：直接对我说

在 Kimi CLI 对话中，直接说：

> **"PAOS 里有 pending 的 fallback 请求，帮我处理一下"**

或

> **"帮我清一下 PAOS 的 fallback 队列"**

我收到后会自动读取队列、生成内容、更新所有关联文件（数据库、Markdown、索引、汇总）。

#### 方法 3：查看队列状态后手动触发

```bash
# 查看 pending 请求
python -m paos.cli.fallback_runner

# 或通过 API
curl http://127.0.0.1:8000/api/v1/fallback
```

然后你**把 Request ID 告诉我**，比如：

> **"PAOS fallback ID 是 5298354f，帮我生成结果"**

### 关闭 Fallback 机制

如果你不需要这个功能，在 `default.yaml` 中设置：

```yaml
llm:
  fallback:
    enabled: false
```

---

## 🧪 测试

```bash
# 运行所有测试
pytest tests/ -v
```

当前测试覆盖：
- `tests/test_pipeline.py`：基础 Pipeline 单元测试
- `tests/test_e2e.py`：端到端测试，验证输入 → Fallback 补全 → 文章生成的完整链路

---

## 📦 项目目录结构

```
paos/
├── paos/
│   ├── api/              # FastAPI 路由
│   ├── cli/              # 命令行工具（fallback_runner, notify_agent）
│   ├── config/           # 配置中心
│   ├── core/             # 核心模型、LLM 封装、Pipeline、Fallback 队列
│   ├── adapters/         # 输入/输出适配器（可插拔）
│   ├── storage/          # 存储层（SQLite、Index Manager、向量库预留）
│   ├── services/         # 业务服务
│   └── mcp_server/       # MCP Server（Hermes 对接入口）
├── scripts/              # 本地模拟与辅助脚本
│   └── simulate_workflow.py
├── data/                 # 用户数据（.gitignore，本地保留）
│   ├── index.json        # 目录索引：原文 → 提纯 → 输出 映射
│   ├── paos.db           # SQLite 结构化数据
│   ├── raw/              # 原始输入 Markdown
│   ├── processed/        # 提纯知识 Markdown
│   ├── processed_summary.md  # 提纯知识自动汇总
│   ├── output/           # 生成内容 Markdown
│   └── fallback_queue/   # Agent Fallback 队列
├── tests/                # 测试用例
├── install.sh
├── README.md
└── pyproject.toml
```

**可迁移性**：`paos/` 目录下的系统代码可 Git 管理，`data/` 目录完全本地隔离，换机器只需重新运行 `install.sh`。

---

## 📜 License

MIT
