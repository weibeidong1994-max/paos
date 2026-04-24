# PAOS 开发变更日志

> 本文档记录 PAOS 项目的关键改动和设计决策，供后续 Agent 快速了解上下文。

---

## v0.2.0 — 2026-04-17 在线搜索 + 异步架构 + 去重防护

### 核心改动总览

| # | 改动 | 影响 |
|---|------|------|
| 1 | 在线搜索能力集成 | 新增 9 个搜索引擎，4 种集成方式 |
| 2 | Ingest 异步化 | OpenClaw webhook 立即返回，后台处理蒸馏+文章生成 |
| 3 | 内容去重机制 | 60秒内相同内容不重复入库，跨来源匹配 |
| 4 | 文章标题 LLM 生成 | 无 H1/H2 时通过 LLM 生成高质量标题 |
| 5 | 文章生成空内容保护 | Step 1/Step 2 空内容检测，防止生成空文章 |
| 6 | 轻量级 Ping 端点 | `/api/v1/ping` 即时返回，供 OpenClaw 两步调用 |
| 7 | OpenClaw 配置优化 | SKILL.md/SOUL.md/USER.md 全面精简，禁止额外检查 |

---

### 1. 在线搜索能力集成

**新增**：PAOS 系统接入在线搜索，支持通过搜索引擎抓取结果，无需 API Key

**4 种集成方式**：

```
┌───────────────┬───────────────┬───────────────┬───────────────┐
│  Pipeline增强  │  输入适配器    │   MCP 工具     │   REST API    │
│ (自动补充素材)  │ (按需搜索入库)  │ (Agent按需调用) │  (HTTP接口)   │
└───────────────┴───────────────┴───────────────┴───────────────┘
```

**支持的搜索引擎**（默认 DuckDuckGo，无需 API Key）：

| 引擎 | Key | 说明 |
|------|-----|------|
| DuckDuckGo | `duckduckgo` | 默认引擎，HTML版无验证码，结果质量好 |
| 百度 | `baidu` | 国内搜索，可能触发验证码 |
| Bing 国内 | `bing_cn` | Bing中文版，可能触发验证码 |
| Bing 国际 | `bing_int` | Bing英文版 |
| 搜狗 | `sogou` | 搜狗网页搜索 |
| 微信搜索 | `wechat` | 微信公众号文章搜索 |
| 头条搜索 | `toutiao` | 今日头条搜索 |
| 360搜索 | `so360` | 360搜索引擎 |
| Ecosia | `ecosia` | 环保搜索引擎 |

**新增文件**：
- `paos/core/web_search.py` — WebSearchService 核心服务（同步+异步、多引擎、广告过滤）
- `paos/adapters/input/web_search.py` — web_search 输入适配器

**修改文件**：
- `paos/config/default.yaml` — 新增 search 配置段
- `paos/config/settings.py` — 新增 SearchConfig
- `paos/core/pipeline.py` — Pipeline 搜索补充步骤 + `_enrich_with_search` 方法
- `paos/services/input_service.py` — 注册 web_search 适配器 + 新增 parse/pipeline_async_process 方法
- `paos/mcp_server/tools.py` — 3 个新 MCP 工具
- `paos/mcp_server/server.py` — 注册新工具
- `paos/api/router.py` — 搜索 API + Ping + 异步 Ingest + 去重
- `pyproject.toml` — 新增 beautifulsoup4 依赖

**新增 MCP 工具**：`paos_web_search`、`paos_web_search_and_ingest`、`paos_list_search_engines`

**新增 REST API**：`POST /api/v1/search`、`POST /api/v1/search/ingest`、`GET /api/v1/search/engines`

---

### 2. Ingest 异步化

**问题**：OpenClaw 调用 Ingest 时，同步等待 LLM 蒸馏+文章生成（30-60秒），期间 OpenClaw 主动做额外检查导致误报

**方案**：OpenClaw webhook 端点改为异步模式

```
之前：Ingest → 同步等待 LLM → 30-60秒后返回完整结果
现在：Ingest → 立即返回 {"status": "accepted"} → 后台 asyncio task 处理
```

- 响应时间从 **30-60秒** 降到 **0.014秒**
- 后台自动完成蒸馏和文章生成
- `/api/v1/input` 端点保持同步（供需要即时结果的场景使用）

**修改文件**：`paos/api/router.py`、`paos/services/input_service.py`

---

### 3. 内容去重机制

**问题**：OpenClaw 对同一条消息可能用不同来源（openclaw/natural_language）和不同内容格式（完整/截断）多次调用 PAOS，导致重复入库

**方案**：基于内容指纹的去重，60秒窗口内不重复入库

```python
def _content_fingerprint(content: str) -> str:
    # 去掉所有空白字符后取前200字符计算 MD5
    # 跨来源匹配（不包含 source 在哈希键中）
    # 处理换行符差异（完整版 vs 截断版）
```

- 返回 `{"deduplicated": true}` 表示内容已入库
- 同时应用于 `/api/v1/input` 和 `/api/v1/webhook/openclaw`

**修改文件**：`paos/api/router.py`

---

### 4. 文章标题 LLM 生成

**问题**：khazix-writer 风格文章不使用 H1/H2 标题，`_postprocess_article` 兜底为"未命名文章"

**方案**：当文章没有 H1/H2 时，通过 LLM 生成标题（8-20字）

- 优先级：H2 提升 > LLM 生成 > 加粗文本提取 > 首段句子 > "未命名文章"
- 空内容保护：内容 < 10 字符时不调用 LLM

**修改文件**：`paos/adapters/output/article.py`

---

### 5. 文章生成空内容保护

**问题**：Step 2 风格改写返回空内容时覆盖了 Step 1 的正常内容

**方案**：
- Step 1 返回空内容 → 立即返回错误，不继续 Step 2
- Step 2 返回空内容或 fallback → 保留 Step 1 原始内容
- `_extract_title_from_content` 对空内容直接返回"未命名文章"

**修改文件**：`paos/adapters/output/article.py`

---

### 6. 轻量级 Ping 端点

**新增**：`GET /api/v1/ping` — 无 I/O 操作，即时返回 `{"status": "ok"}`

供 OpenClaw 两步调用流程的第一步：先 Ping 确认服务在线，再 Ingest 保存内容。

**修改文件**：`paos/api/router.py`

---

### 7. OpenClaw 配置优化

**问题**：OpenClaw 在 Ingest 后做大量多余检查（查 fallback、查索引、查日志），导致误报"文章未生成"

**方案**：
- SKILL.md：精简为三步流程（Ping → Ingest → 确认），明确禁止额外检查
- SOUL.md：执行流程简化，新增"为什么不需要额外检查"说明
- USER.md：同步更新规则

**修改文件**：`~/.openclaw/workspace/skills/paos/SKILL.md`、`~/.openclaw/workspace/SOUL.md`、`~/.openclaw/workspace/USER.md`

---

### 完整 API 端点一览（v2.0）

| 端点 | 方法 | 说明 | 版本 |
|------|------|------|------|
| `/api/v1/ping` | GET | 轻量级健康检查 | v2.0 新增 |
| `/api/v1/input` | POST | 通用输入（同步） | v1.0 |
| `/api/v1/webhook/openclaw` | POST | OpenClaw 入口（异步） | v2.0 改为异步 |
| `/api/v1/search` | POST | 在线搜索 | v2.0 新增 |
| `/api/v1/search/ingest` | POST | 搜索并存入系统 | v2.0 新增 |
| `/api/v1/search/engines` | GET | 列出搜索引擎 | v2.0 新增 |
| `/api/v1/index` | GET | 查询知识索引 | v1.0 |
| `/api/v1/fallback` | GET | 查看 fallback 队列 | v1.0 |
| `/api/v1/config` | GET | 查看配置 | v1.0 |
| `/api/v1/generate/article` | POST | 手动生成文章 | v1.0 |

### 完整 MCP 工具一览（v2.0）

| 工具 | 说明 | 版本 |
|------|------|------|
| `paos_health_check` | 健康检查 | v1.0 |
| `paos_add_note` | 添加笔记 | v1.0 |
| `paos_get_processed` | 获取提纯记录 | v1.0 |
| `paos_list_index` | 查看索引 | v1.0 |
| `paos_update_tags` | 更新标签 | v1.0 |
| `paos_list_fallback` | 查看 fallback | v1.0 |
| `paos_complete_fallback` | 完成 fallback | v1.0 |
| `paos_regenerate_summary` | 重新提纯 | v1.0 |
| `paos_generate_article` | 生成文章 | v1.0 |
| `paos_web_search` | 在线搜索 | v2.0 新增 |
| `paos_web_search_and_ingest` | 搜索并入库 | v2.0 新增 |
| `paos_list_search_engines` | 列出搜索引擎 | v2.0 新增 |

---

## v1.0.0 — 2026-04-16 ~ 2026-04-17 初始版本

### 1. 服务管理修复

**问题**：`paos gateway start` 通过 nohup 启动 uvicorn 时报 `ModuleNotFoundError: No module named 'paos'`

**原因**：nohup 进程的工作目录不是 `$PAOS_DIR`，导致 editable install 无法解析 paos 包

**修复**：在 `bin/paos` 的 `gateway_start()` 中 nohup 命令前加了 `cd "$PAOS_DIR"`

**文件**：[bin/paos](file:///Users/bytedance/Documents/trae_projects/paos_cocoding/bin/paos)

---

### 2. 版本管理系统

**新增**：基于 Git + tag 的全量快照系统

**命令**：
- `paos snapshot save [name]` — 保存快照（自动名用时间戳）
- `paos snapshot list` — 列出所有快照
- `paos snapshot restore <name>` — 回滚到快照（自动保存未提交改动）
- `paos snapshot diff <name>` — 查看与快照的差异

**实现**：快照本质是 `git tag snap/<name>`，restore 时 `git checkout <tag> -- .`

**文件**：[bin/paos](file:///Users/bytedance/Documents/trae_projects/paos_cocoding/bin/paos)、[.gitignore](file:///Users/bytedance/Documents/trae_projects/paos_cocoding/.gitignore)

---

### 3. 文章生成流程重构（核心改动）

**旧流程**：素材 → khazix-writer SKILL.md 全文(414行) + 素材 → LLM → 文章

**新流程**：
```
素材 → default.yaml prompt_template → LLM → 原始文章
                                              ↓
                              khazix-writer SKILL.md → LLM → 风格优化文章
                                                              ↓
                                                    补 H1 标题 → 最终文章
```

**设计原则**：
- **生成与风格解耦**：Step 1 只管内容，Step 2 只管风格
- **skill 可插拔**：换写作风格只需安装不同 skill，article.py 不用改
- **skill 即 prompt**：Step 2 的 system_prompt 就是 SKILL.md 完整内容
- **无 skill 兜底**：没有写作 skill 时，Step 1 原始文章直接输出

**文件**：[paos/adapters/output/article.py](file:///Users/bytedance/Documents/trae_projects/paos_cocoding/paos/adapters/output/article.py)

---

### 4. 后处理逻辑迁移：article.py → skill

**改动**：将作者/邮箱清理逻辑从 `article.py` 移到 `khazix-writer` SKILL.md

**article.py 后处理**（现在只做通用逻辑）：
- 补 H1 标题（无则提升 H2 或用"未命名文章"）

**khazix-writer SKILL.md**（业务逻辑由 skill 控制）：
- 绝对禁区新增第 8 条：不输出作者和联系方式
- 删除了结构模板末尾的作者/邮箱示例

**文件**：[article.py](file:///Users/bytedance/Documents/trae_projects/paos_cocoding/paos/adapters/output/article.py)、[khazix-writer/SKILL.md](file:///Users/bytedance/Documents/trae_projects/paos_cocoding/skills/khazix-writer/SKILL.md)

---

### 5. 技能安装与清理

| 技能 | 操作 | 说明 |
|------|------|------|
| feishu-cli | 安装后删除 | 飞书 CLI，keychain 沙箱限制无法使用，已清理 |
| md2wechat | 安装 | Markdown → 微信公众号 HTML，v2.0.7，路径 `~/.local/bin/md2wechat` |
| md2wechat config | 已初始化 | `~/.config/md2wechat/config.yaml`，默认 API 模式 |

**卸载 md2wechat**：`rm ~/.local/bin/md2wechat && rm -rf ~/.config/md2wechat`

---

### 6. 数据目录规范

**新增**：`data/output/assets/` — 保存非 Markdown 文件（HTML、PNG、prompt.txt 等）

**目录结构**：
```
data/output/
├── article_*.md          ← 文章（Markdown）
└── assets/               ← 非 Markdown 资源
    ├── *.html
    ├── *.png
    └── *.txt
```

---

### 7. 项目文档

| 文档 | 说明 |
|------|------|
| [PROJECT.md](file:///Users/bytedance/Documents/trae_projects/paos_cocoding/PROJECT.md) | 项目结构与功能文档（完整版） |
| [MEMORY.md](file:///Users/bytedance/Documents/trae_projects/paos_cocoding/MEMORY.md) | 项目记忆卡 |
| [CHANGELOG.md](file:///Users/bytedance/Documents/trae_projects/paos_cocoding/CHANGELOG.md) | 本文档 |

---

### 8. 工具链

| 工具 | 版本/路径 | 用途 |
|------|-----------|------|
| Playwright Chromium | v145（.venv 内） | HTML 截图，通过 `scripts/capture_*.py` 调用 |
| md2wechat | v2.0.7（`~/.local/bin/`） | Markdown → 微信公众号 HTML |
| paos gateway | `/usr/local/bin/paos` | 服务管理（start/stop/restart/status/url） |
| paos snapshot | 同上 | 版本管理（save/list/restore/diff） |

---

## 当前系统状态

- **服务**：运行中，PID 文件 `paos_cocoding/.paos.pid`
- **Git**：已初始化，1 个快照 `v0.1.0-stable`
- **已安装 skill**：example-skill、khazix-writer、huashu-nuwa、onepager、md2wechat
- **LLM**：阶跃星辰 step-3.5-flash-2603
- **文章生成**：两步流程（生成 → khazix-writer 风格优化）
