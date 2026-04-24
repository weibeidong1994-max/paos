# PAOS 项目记忆卡（Session Memory）

> 文件用途：记录截至当前会话的 PAOS 项目状态、架构决策和待办事项。
> 下次启动 Kimi CLI 时，请先让我读取此文件以恢复上下文。

---

## 🎯 项目目标

PAOS（Personal AI OS）是一个以个人为中心的 AI 操作系统，采用 **输入层 - 处理层 - 输出层** 三层架构。

- **输入层**：自然语言、OpenClaw Webhook、社交媒体（预留）
- **处理层**：信息提纯 Pipeline、统一配置中心、结构化存储
- **输出层**：文章生成器（已可用）、Website/App-H5（预留）

---

## ✅ 已完成的核心功能

### 1. 完整项目骨架
- FastAPI 服务入口（`paos.main:app`），使用 `lifespan` context manager
- 输入/输出适配器抽象层（`adapters/`）
- SQLite + SQLModel 存储层（`storage/`）
- 业务服务层（`services/`）

### 2. 统一配置中心（零硬编码）
- 所有可变参数集中在 `paos/config/default.yaml`
- 代码中**没有任何硬编码**的路径、模型名、URL
- 支持环境变量覆盖（`PAOS_` 前缀 + 双下划线嵌套，以及 `OPENAI_API_KEY` 等直接映射到 `llm.*`）
- 可配置项包括：
  - `server.host` / `server.port`
  - `llm.provider` / `llm.api_key` / `llm.model` / `llm.base_url`
  - `output.article.save_dir`
  - `database.filename`
  - `llm.fallback.enabled`

### 3. 三重存储 + 目录索引 + 提纯知识汇总
每次输入走完后，会同时产生：

| 内容 | 数据库 | Markdown 文件 | 索引关联 |
|------|--------|---------------|----------|
| 原始输入 | `paos.db` → `raw_input` | `data/raw/` | ✅ |
| 提纯知识 | `paos.db` → `processed_item` | `data/processed/` | ✅ |
| 生成文章 | - | `data/output/` | ✅ |
| **提纯知识汇总** | - | `data/processed_summary.md` | - |

- 目录索引文件：`data/index.json`
- API 查询：`GET /api/v1/index`
- **提纯知识汇总** `data/processed_summary.md`：每次输入或 fallback 补全后自动从 DB 刷新，极简记录所有知识条目（时间、来源、标签、摘要）

### 4. Agent Fallback 机制（已联动更新）
- 当没有配置 `OPENAI_API_KEY` 或 LLM 接口失效时，系统不报错
- 自动将 LLM 请求写入 `data/fallback_queue/`
- Pipeline 会自动把 `processed_id` 和文件路径关联到 fallback JSON，便于后续联动更新
- 用户可在对话中喊我（Kimi Agent）处理
- **补全后自动联动更新**：SQLite 记录、`processed/` Markdown、`index.json`、以及 `processed_summary.md`
- 触发方式：
  1. `python -m paos.cli.notify_agent` → 生成可直接复制给我的提示语
  2. 直接说：**"PAOS 帮我清一下 fallback 队列"**

### 5. CLI 工具
- `python -m paos.cli.fallback_runner`：查看 pending fallback 请求
- `python -m paos.cli.notify_agent`：一键生成触发 Agent 的提示语

### 6. MCP Server（已可用，主要供 OpenClaw 调用）
PAOS 已内置 MCP Server，可作为 OpenClaw 调用 PAOS 的**可选方案**（尤其适用于复杂多步操作）。Hermes 作为 PAOS 的开发者/运维管家，直接通过文件系统管理 PAOS 代码，不走 MCP。

**启动方式**：
```bash
# stdio 模式
python -m paos.mcp_server

# SSE 模式
python -m paos.mcp_server --sse --host 127.0.0.1 --port 8001
```

**已暴露的 9 个 MCP 工具**：
| 工具名 | 用途 |
|--------|------|
| `paos_list_index` | 查看全局索引 |
| `paos_list_fallback` | 查看 fallback 队列 |
| `paos_get_processed` | 按 ID 读取提纯记录 |
| `paos_health_check` | 检查 PAOS 健康状态 |
| `paos_add_note` | 添加运维日志 |
| `paos_complete_fallback` | 补全 fallback 并联动更新 |
| `paos_update_tags` | 更新标签并刷新汇总文件 |
| `paos_regenerate_summary` | 重新生成 `processed_summary.md` |
| `paos_generate_article` | 基于最近记录生成文章 |

### 7. 测试与模拟脚本
- `tests/test_pipeline.py`：基础单元测试
- `tests/test_e2e.py`：端到端测试，覆盖输入 → fallback 补全 → 文章生成的完整链路
- `scripts/simulate_workflow.py`：本地脚本，无需启动 FastAPI 即可模拟完整产品流程

---

## 📂 关键文件路径

```
/Users/bytedance/Documents/trae_projects/paos_cocoding/
├── paos/config/default.yaml          # 统一配置中心
├── paos/core/pipeline.py             # 信息处理主流程（含异步入口 + 汇总刷新）
├── paos/core/llm.py                  # LLM 封装 + Fallback 触发
├── paos/core/fallback.py             # Fallback 队列管理（含联动更新逻辑）
├── paos/storage/base_vector_store.py # 向量存储抽象基类
├── paos/storage/index_manager.py     # data/index.json 管理器
├── paos/storage/sqlite_store.py      # SQLite 存储实现
├── paos/adapters/output/article.py   # 文章生成适配器
├── paos/cli/notify_agent.py          # 一键通知 Agent
├── paos/api/router.py                # FastAPI 路由（已改用 Pydantic 请求模型）
├── paos/mcp_server/                  # MCP Server（Hermes 对接入口）
│   ├── server.py
│   ├── tools.py
│   └── __main__.py
├── scripts/simulate_workflow.py      # 本地工作流模拟脚本
├── tests/test_pipeline.py            # 基础测试
├── tests/test_e2e.py                 # 端到端测试
├── tests/test_mcp_server.py          # MCP Server 测试
├── data/index.json                   # 目录索引（原文→提纯→输出）
├── data/paos.db                      # SQLite 数据库
├── data/processed_summary.md         # 提纯知识自动汇总
└── MEMORY.md                         # ← 本文件
```

---

## 🔧 如何启动项目

```bash
cd /Users/bytedance/Documents/trae_projects/paos_cocoding
source .venv/bin/activate
uvicorn paos.main:app --reload
```

---

## 💡 常用操作速查

### 提交输入
```bash
curl -X POST http://127.0.0.1:8000/api/v1/input \
  -H "Content-Type: application/json" \
  -d '{"source": "natural_language", "data": {"content": "你的输入内容"}}'
```

### 生成文章
```bash
curl -X POST "http://127.0.0.1:8000/api/v1/generate/article?limit=5"
```

### 查询目录索引
```bash
curl http://127.0.0.1:8000/api/v1/index
```

### 查看 Fallback 队列
```bash
python -m paos.cli.fallback_runner
```

### 一键生成 Agent 提示语
```bash
python -m paos.cli.notify_agent
```

### 本地模拟完整流程（不启动服务）
```bash
python scripts/simulate_workflow.py
```

---

## 📝 下次恢复对话时，请对我说

> **"先读一下 PAOS 的 MEMORY.md，帮我恢复上下文"**

或者更完整一点：

> **"我在做 PAOS 项目，请读取 `/Users/bytedance/Documents/trae_projects/paos_cocoding/MEMORY.md`，然后告诉我当前项目状态，以及接下来可以做什么"**

---

## 🚧 当前待办 / 后续可扩展方向

1. **OpenClaw 协议对接**：当前仅为 Webhook 占位，需根据实际协议细化解析逻辑。
2. **社交媒体适配器**：小红书 / 知乎 / 即刻的 RSS / 爬虫接入。
3. **向量数据库**：引入 Chroma 或类似方案，支持语义检索（`BaseVectorStore` 已预留接口）。
4. **配置中心 Web UI**：用轻量前端管理 YAML 配置。
5. **Website / App-H5 适配器**：从占位实现为真正的脚手架生成器。
6. **API 模块级服务实例化改为依赖注入**：当前 `router.py` 中 storage/service 在 import 时实例化，不利于测试替换（P1 遗留）。
7. **适配器自动注册机制**：替代当前的硬编码字典（P2 改进项）。
8. **index.json 分页与容错**：大数据量场景需考虑（P2 改进项）。
9. **Hermes 首个开发 Skill**：编写 "PAOS Bug 修复流程" Skill 的 Prompt 模板，让 Hermes 演练一次完整的"读取代码 → 修改 → 运行测试 → 验证"闭环。

> **说明**：此前标记为"自动更新 processed .md"和"自动化 Agent Fallback 回写"的待办，已在 2026-04-15 修复中完成。fallback 补全后会自动联动更新 SQLite、processed Markdown、index.json 和 processed_summary.md。

---

## 🗣️ 关键决策记录

- **LLM 默认走云端 API**（OpenAI 兼容），但代码已封装好，切换本地 Ollama 只需改配置。
- **OpenClaw 作为已有外部服务处理**，系统仅提供接收接口。
- **数据与代码严格分离**：`data/` 在 `.gitignore` 中，系统代码可任意迁移。
- **所有配置项统一管理**：`default.yaml` 是唯一真理来源，代码中无硬编码。
- **Fallback 补全采用全量联动更新策略**：`complete_request()` 直接更新 DB + MD + Index + Summary，而非增量补丁，逻辑简单且一致性强。
- **processed_summary.md 采用全量刷新策略**：每次触发时从 SQLite 读取全部记录重写，避免追加遗漏或顺序混乱的问题。

---

*最后更新：2026-04-16（迁移 + OpenClaw 集成版）**


### 8. OpenClaw Skill 集成（2026-04-16 新增）

PAOS 已部署为 OpenClaw workspace skill，当用户在 OpenClaw 中表达保存/记录意图时，自动调用 PAOS 服务。

**Skill 位置**: `~/.openclaw/workspace/skills/paos/SKILL.md`

**支持的 4 个操作**:
1. **Ingest Knowledge** — 保存知识到 PAOS（支持 natural_language 和 openclaw 两种 source）
2. **Query Knowledge Index** — 查询知识索引
3. **Check Fallback Queue** — 查看 fallback 队列
4. **Service Status** — 检查 PAOS 服务状态

**自动触发规则**（写入 SOUL.md + USER.md）:
当用户说"保存/存一下/存住/记录/记一下/记住/记着/记下来/写下来/存下来/留个记录/帮我记/帮我存/收藏/存档"等关键词时，OpenClaw 自动调用 paos skill 的 Ingest Knowledge，无需确认，原文保存。

**关键设计决策**:
- SKILL.md 中 URL 硬编码为 `http://127.0.0.1:8000`，不依赖环境变量（因为 OpenClaw gateway 进程无法加载 shell 环境变量）
- 使用 OpenClaw webhook 端点 `/api/v1/webhook/openclaw` 作为主要输入通道
- 不暴露 Generate Article 操作（文章由 pipeline 自动生成）

---

## 🏗️ 项目迁移记录

### 2026-04-16: paos → paos_cocoding

| 变更项 | 旧值 | 新值 |
|--------|------|------|
| 项目目录 | `/Users/weibeidongm2/Documents/trae_projects/paos` | `/Users/bytedance/Documents/trae_projects/paos_cocoding` |
| Python | 系统 Python 3.9 | Homebrew Python 3.13 (`/opt/homebrew/bin/python3.13`) |
| LLM | 未配置 | step-3.5-flash-2603 (阶跃星辰) |
| .env | 不存在 | 已创建，含 API Key |
| 虚拟环境 | 旧路径 shebang | 已重建，指向新路径 |

**注意事项**:
- 移动项目目录后必须重建 `.venv`（shebang 硬编码了旧路径）
- `.env` 文件使用相对路径加载（`Path(__file__).parent.parent.parent / ".env"`），不受目录移动影响
- `data/` 目录使用相对路径 `./data`，不受影响
- OpenClaw SKILL.md 中的启动命令路径已同步更新
