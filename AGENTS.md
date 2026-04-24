# PAOS — Personal AI OS 项目上下文

> 本文档供 Kimi Code 使用，包含项目全貌、部署状态、操作指南及迭代建议。
> 文档位置：`/Users/weibeidongm2/Documents/vibecoding/paos/AGENTS.md`

---

## 1. 项目概述

PAOS（Personal AI OS）是一个**个人AI操作系统**，以本地计算为中枢，将碎片化信息自动提纯为结构化知识，并生成文章。

### 核心流程
```
用户输入 → 输入适配器 → Pipeline 提纯(LLM摘要+标签) → 存储(DB+MD双备份) → 自动生成文章
```

### 当前状态
- ✅ **已部署并运行**，服务监听 `http://127.0.0.1:8000`
- ✅ LLM API Key 已配置（阶跃星辰 step-3.5-flash-2603）
- ✅ 历史数据完整，共 58+ 条记录
- ❌ **OpenClaw 暂未安装**（当前通过 REST API / MCP 使用）

---

## 2. 技术栈

| 组件 | 技术 |
|------|------|
| Web 框架 | FastAPI + uvicorn |
| 数据库 | SQLite + SQLModel |
| 配置管理 | Pydantic Settings + YAML + dotenv |
| LLM | OpenAI 兼容 API（阶跃星辰 step-3.5-flash-2603）|
| MCP | FastMCP（stdio + SSE 双模式）|
| 搜索 | httpx + BeautifulSoup4（9个搜索引擎，零 API Key）|
| Python | **3.13**（venv 内） |
| 服务管理 | nohup + uvicorn + bin/paos 脚本 |

---

## 3. 目录结构

```
paos/                          # 项目根目录（当前路径）
├── paos/                      # 核心源码
│   ├── main.py                # FastAPI 应用入口
│   ├── api/router.py          # REST API 路由
│   ├── cli/                   # CLI 工具（fallback_runner, notify_agent）
│   ├── config/                # 配置中心
│   │   ├── settings.py        # Pydantic Settings 统一配置
│   │   └── default.yaml       # 默认配置（无硬编码）
│   ├── core/                  # 核心业务逻辑
│   │   ├── pipeline.py        # 信息处理主流程
│   │   ├── llm.py             # LLM 客户端封装（含 Fallback）
│   │   ├── fallback.py        # Agent Fallback 队列管理
│   │   ├── models.py          # 数据模型
│   │   └── web_search.py      # 在线搜索核心服务
│   ├── adapters/              # 输入/输出适配器
│   │   ├── input/             # 自然语言、OpenClaw、RSS、搜索等
│   │   └── output/            # 文章、Website、App-H5
│   ├── mcp_server/            # MCP Server（供 AI Agent 调用）
│   ├── services/              # 业务服务层
│   ├── skills/                # 技能系统内置路由
│   └── storage/               # 存储层（SQLite、索引、向量库预留）
├── skills/                    # 可插拔技能目录（与核心分离）
│   ├── khazix-writer/         # 卡兹克公众号写作风格
│   ├── onepager/              # OnePage 信息图生成
│   ├── md2wechat/             # 公众号排版
│   └── ...
├── data/                      # 运行时数据（.gitignore）
│   ├── paos.db                # SQLite 数据库
│   ├── index.json             # 目录索引
│   ├── processed_summary.md   # 提纯知识自动汇总
│   ├── raw/                   # 原始输入 Markdown
│   ├── processed/             # 提纯结果 Markdown
│   ├── output/                # 生成文章 Markdown
│   └── fallback_queue/        # Fallback 请求队列
├── bin/paos                   # 服务管理脚本（start/stop/restart/status/url）
├── scripts/                   # 辅助脚本
│   └── simulate_workflow.py   # 本地模拟完整流程
├── tests/                     # 测试用例
├── .venv/                     # Python 虚拟环境（3.13）
├── pyproject.toml             # 依赖配置
└── AGENTS.md                  # ← 本文档
```

---

## 4. ⚠️ 关键注意事项

### Python 版本陷阱
- 系统 `python3` 指向 **Python 3.14**（/Library/Frameworks/Python.framework/Versions/3.14/）
- venv 内是 **Python 3.13**，通过 uv 安装
- **`source .venv/bin/activate` 不会覆盖 `python3` 命令！**
- **正确做法**：直接使用 `.venv/bin/python3` 或 `.venv/bin/python`

### 依赖安装
```bash
# 推荐用 uv（已安装）
uv pip install -e ".[dev]"

# 或 pip
.venv/bin/pip3 install -e ".[dev]"
```

---

## 5. 一键启动服务

### 方法 1：直接使用 uvicorn（推荐开发时）
```bash
cd /Users/weibeidongm2/Documents/vibecoding/paos
.venv/bin/python3 -m uvicorn paos.main:app --host 127.0.0.1 --port 8000 --reload
```

### 方法 2：使用管理脚本（推荐生产/后台）
```bash
cd /Users/weibeidongm2/Documents/vibecoding/paos
./bin/paos gateway start    # 后台启动
./bin/paos gateway status   # 查看状态
./bin/paos gateway stop     # 停止
./bin/paos gateway restart  # 重启
./bin/paos gateway url      # 获取服务URL
```

### 方法 3：nohup 后台运行
```bash
cd /Users/weibeidongm2/Documents/vibecoding/paos
nohup .venv/bin/python3 -m uvicorn paos.main:app --host 127.0.0.1 --port 8000 \
    >> logs/paos-stdout.log 2>> logs/paos-stderr.log &
echo $! > .paos.pid
```

---

## 6. API 使用速查

### 健康检查
```bash
curl http://127.0.0.1:8000/api/v1/ping
```

### 提交输入（自然语言）
```bash
curl -X POST http://127.0.0.1:8000/api/v1/input \
  -H "Content-Type: application/json" \
  -d '{"source": "natural_language", "data": {"content": "你的灵感/笔记内容"}}'
```

### 搜索并入库
```bash
curl -X POST http://127.0.0.1:8000/api/v1/search/ingest \
  -H "Content-Type: application/json" \
  -d '{"query": "AI Agent 趋势", "engine": "duckduckgo", "max_results": 5}'
```

### 查看目录索引
```bash
curl http://127.0.0.1:8000/api/v1/index
```

### 手动生成文章
```bash
curl -X POST "http://127.0.0.1:8000/api/v1/generate/article?limit=5"
```

### 查看配置（脱敏）
```bash
curl http://127.0.0.1:8000/api/v1/config
```

### 查看 Fallback 队列
```bash
curl http://127.0.0.1:8000/api/v1/fallback
```

---

## 7. MCP Server（供 AI Agent 调用）

PAOS 内置 MCP Server，暴露 12 个工具供外部 Agent 调用。

### 启动方式
```bash
# stdio 模式（供 Claude Desktop / Kimi Code 等本地调用）
.venv/bin/python3 -m paos.mcp_server

# SSE 模式（HTTP 访问）
.venv/bin/python3 -m paos.mcp_server --sse --host 127.0.0.1 --port 8001
```

### 已暴露工具
| 工具名 | 用途 |
|--------|------|
| `paos_list_index` | 查看全局目录索引 |
| `paos_list_fallback` | 查看 fallback 队列 |
| `paos_get_processed` | 按 ID 读取提纯记录 |
| `paos_health_check` | 检查 PAOS 健康状态 |
| `paos_add_note` | 添加运维日志 |
| `paos_complete_fallback` | 补全 fallback 并联动更新 |
| `paos_update_tags` | 更新标签并刷新汇总 |
| `paos_regenerate_summary` | 重新生成 `processed_summary.md` |
| `paos_generate_article` | 基于最近记录生成文章 |
| `paos_web_search` | 在线搜索 |
| `paos_web_search_and_ingest` | 搜索并存入 PAOS |
| `paos_list_search_engines` | 列出所有搜索引擎 |

---

## 8. 配置中心

所有配置在 `paos/config/default.yaml`，支持环境变量覆盖。

### 关键环境变量
| 变量 | 说明 |
|------|------|
| `PAOS_LLM__API_KEY` / `OPENAI_API_KEY` | LLM API 密钥 |
| `PAOS_LLM__MODEL` | 模型名称 |
| `PAOS_LLM__BASE_URL` | API 基础地址 |
| `PAOS_DATA_DIR` | 数据目录 |
| `PAOS_SERVER__HOST` / `PAOS_SERVER__PORT` | 服务监听地址 |

### 修改配置生效
修改 `default.yaml` 后**重启服务**即可，无需改代码。

---

## 9. 技能系统

技能是可插拔的 Python 模块，安装在 `skills/` 目录。

### 当前已安装技能
- `khazix-writer` — 卡兹克公众号写作风格（文章生成 Step 2 自动调用）
- `md2wechat` — 公众号排版
- `onepager` — OnePage 信息图生成
- `smart_flowchart_generator` — 智能流程图
- `huashu-nuwa` — 话术生成

### 技能结构
```
skills/<skill-name>/
├── SKILL.md          # 技能定义（元数据、接口）
└── *.py              # 实现代码
```

### 加载原理
`paos/skills/__init__.py` 中的 `SkillRegistry` 自动扫描 `skills/` 目录，加载所有有效技能。

---

## 10. OpenClaw 接入方案（预留）

> 当前电脑**未安装 OpenClaw**，以下为接入方案，需要时执行。

### OpenClaw 与 PAOS 的关系
- **OpenClaw** 是 PAOS 的**对外接口层**，用户通过 OpenClaw 触发 PAOS 存储
- **PAOS** 是**本地中枢**，负责提纯、存储、文章生成
- **MCP** 是两者之间的通信协议之一（也可走 REST API）

### 接入步骤

#### 步骤 1：安装 OpenClaw
```bash
# 按 OpenClaw 官方文档安装
# https://github.com/openclaw-org/openclaw
```

#### 步骤 2：配置 PAOS Skill
创建 OpenClaw workspace skill：
```bash
mkdir -p ~/.openclaw/workspace/skills/paos
cat > ~/.openclaw/workspace/skills/paos/SKILL.md << 'EOF'
# PAOS Skill

## 描述
将用户消息存入 Personal AI OS（PAOS），自动提纯并生成文章。

## 调用方式
1. **Ping** — 确认 PAOS 服务在线：`GET http://127.0.0.1:8000/api/v1/ping`
2. **Ingest** — 发送内容：`POST http://127.0.0.1:8000/api/v1/webhook/openclaw`
3. **确认** — 收到 `{"status": "accepted"}` 即表示成功，后台自动处理

## 规则
- 每条消息只调用一次 Ingest
- Ingest 后禁止查 fallback、查索引、查日志
- `status: accepted` = 成功，无需额外检查
EOF
```

#### 步骤 3：配置 SOUL.md（最高优先级规则）
```bash
cat > ~/.openclaw/workspace/SOUL.md << 'EOF'
# PAOS 集成规则

1. 用户分享的任何有价值内容，自动调用 PAOS Ingest API 存入
2. Ingest 后立即返回 "已存入 PAOS"，不做额外检查
3. 不查询 fallback 状态、不查询索引、不查询日志
EOF
```

#### 步骤 4：OpenClaw Webhook 端点
PAOS 已内置 OpenClaw 适配器：`paos/adapters/input/openclaw.py`

Webhook 地址：
```
POST http://127.0.0.1:8000/api/v1/webhook/openclaw
Content-Type: application/json

Body: {"text"/"content"/"message": "用户内容"}
```

支持字段容错：`text`、`content`、`message` 任一字段均可。

### 接入后的数据流
```
用户在 OpenClaw 聊天 → OpenClaw 调用 PAOS Ingest → PAOS 立即返回 accepted
                                      ↓
                         后台 asyncio task:
                         解析 → 保存 raw → LLM 蒸馏 → 保存 processed
                         → 刷新索引 → 生成文章 → 保存 output
```

---

## 11. Fallback 机制

当 LLM API 失效或未配置 API Key 时，系统不会报错，而是将请求排入 `data/fallback_queue/`，由 Agent 补全。

### 触发 Agent 补全
```bash
# 一键生成提示语
.venv/bin/python3 -m paos.cli.notify_agent

# 查看队列
.venv/bin/python3 -m paos.cli.fallback_runner
curl http://127.0.0.1:8000/api/v1/fallback
```

### 补全后联动更新
Agent 调用 `paos.core.fallback.complete_request(req_id, result)` 后，系统自动：
1. 更新 SQLite DB
2. 重写 `processed/` Markdown 文件
3. 更新 `index.json`
4. 重新生成 `processed_summary.md`

---

## 12. 测试

```bash
# 运行所有测试
.venv/bin/python3 -m pytest tests/ -v

# 单文件测试
.venv/bin/python3 -m pytest tests/test_pipeline.py -v
.venv/bin/python3 -m pytest tests/test_e2e.py -v
```

---

## 13. Kimi Code 迭代速查

### 修改代码后重启服务
```bash
cd /Users/weibeidongm2/Documents/vibecoding/paos
./bin/paos gateway restart
```

### 添加新输入适配器
1. 在 `paos/adapters/input/` 新建文件，继承 `BaseInputAdapter`
2. 在 `paos/config/default.yaml` 的 `adapters.input.enabled` 中注册
3. 在 `paos/api/router.py` 添加路由（如需）

### 添加新输出适配器
1. 在 `paos/adapters/output/` 新建文件，继承 `BaseOutputAdapter`
2. 在 `paos/config/default.yaml` 的 `adapters.output.enabled` 中注册
3. 在 `paos/api/router.py` 添加路由（如需）

### 添加新技能
1. 在 `skills/` 下新建目录（如 `skills/my-skill/`）
2. 创建 `SKILL.md` 定义元数据
3. 创建实现代码
4. `SkillRegistry` 自动加载，无需改核心代码

### 修改 Pipeline 逻辑
核心文件：`paos/core/pipeline.py` → `Pipeline.process_input()`

### 修改 LLM 配置
直接改 `paos/config/default.yaml`，重启生效。

---

## 14. 数据备份与迁移

PAOS 遵循**代码与数据分离**原则：
- `paos/` 代码 → 可 Git 管理
- `data/` 数据 → `.gitignore`，完全本地隔离

**迁移到新机器**：
1. `git clone` 代码
2. 复制 `data/` 目录到新机器
3. 运行 `./install.sh`
4. 配置 API Key

---

## 15. 联系与参考

- `README.md` — 面向人类用户的快速开始
- `PROJECT.md` — 详细的项目结构与技术决策
- `CHANGELOG.md` — 版本变更日志
- `MEMORY.md` — 项目迭代记忆卡

---

*文档版本: v1.0 | 创建时间: 2026-04-21 | 供 Kimi Code 使用*
