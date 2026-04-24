# PAOS 项目结构与功能文档 v2.0

> PAOS（Personal AI OS）— 个人 AI 操作系统，采用 **输入层 → 处理层 → 输出层** 三层架构，将碎片化信息自动提纯为结构化知识并生成文章。

---

## 目录结构总览

```
paos_cocoding/
├── bin/
│   └── paos                          # 服务管理脚本（start/stop/restart/status/url）
├── paos/                             # 核心代码
│   ├── main.py                       # FastAPI 应用入口
│   ├── adapters/                     # 适配器层（输入/输出）
│   │   ├── input/                    # 输入适配器
│   │   │   ├── base.py               #   抽象基类 BaseInputAdapter
│   │   │   ├── natural_language.py   #   自然语言输入
│   │   │   ├── openclaw.py           #   OpenClaw Webhook 输入
│   │   │   ├── web_search.py         #   在线搜索输入 [v2.0 新增]
│   │   │   ├── rss.py                #   RSS 输入（预留）
│   │   │   └── social_media.py       #   社交媒体输入（预留）
│   │   └── output/                   # 输出适配器
│   │       ├── base.py               #   抽象基类 BaseOutputAdapter
│   │       ├── article.py            #   文章生成（LLM标题+空内容保护）[v2.0 增强]
│   │       ├── app_h5.py             #   App-H5 生成（预留）
│   │       └── website.py            #   Website 生成（预留）
│   ├── api/
│   │   └── router.py                 # REST API（异步Ingest+搜索+Ping+去重）[v2.0 增强]
│   ├── cli/
│   │   ├── fallback_runner.py        # Fallback 队列查看工具
│   │   └── notify_agent.py           # 一键生成 Agent 提示语
│   ├── config/
│   │   ├── settings.py               # 统一配置中心（+SearchConfig）[v2.0 增强]
│   │   └── default.yaml              # 默认配置文件（+search段）[v2.0 增强]
│   ├── core/                         # 核心业务逻辑
│   │   ├── pipeline.py               # 信息处理主流程（+搜索补充）[v2.0 增强]
│   │   ├── llm.py                    # LLM 客户端封装（含 Fallback）
│   │   ├── fallback.py               # Agent Fallback 队列管理
│   │   ├── models.py                 # 数据模型定义
│   │   └── web_search.py             # 在线搜索核心服务 [v2.0 新增]
│   ├── mcp_server/                   # MCP Server（供 AI Agent 调用）
│   │   ├── server.py                 # FastMCP 服务注册（+3搜索工具）[v2.0 增强]
│   │   ├── tools.py                  # 12 个 MCP 工具实现 [v2.0 增强]
│   │   └── __main__.py               # 启动入口
│   ├── services/
│   │   ├── input_service.py          # 输入服务层（+parse/async方法）[v2.0 增强]
│   │   └── output_service.py         # 输出服务层
│   ├── skills/                       # 技能系统（PAOS 内置）
│   │   ├── __init__.py               # SkillRegistry / Skill / SkillManifest
│   │   └── router.py                 # Skills REST API 路由
│   └── storage/                      # 存储层
│       ├── base.py                   # 存储抽象基类
│       ├── base_vector_store.py      # 向量存储抽象基类（预留）
│       ├── sqlite_store.py           # SQLite + SQLModel 实现
│       ├── index_manager.py          # 目录索引管理器
│       └── vector_store.py           # 向量存储实现（预留）
├── skills/                           # 可插拔技能目录（与核心代码分离）
│   ├── example-skill/                # 示例技能
│   ├── khazix-writer/                # 卡兹克公众号写作风格
│   ├── nuwa-skill/                   # 女娲造人（人物 Skill 生成）
│   └── onepager/                     # OnePage 信息图生成
├── data/                             # 运行时数据（.gitignore）
│   ├── paos.db                       # SQLite 数据库
│   ├── index.json                    # 目录索引
│   ├── processed_summary.md          # 提纯知识汇总
│   ├── raw/                          # 原始输入 Markdown 归档
│   ├── processed/                    # 提纯结果 Markdown 归档
│   ├── output/                       # 生成文章 Markdown 归档
│   └── fallback_queue/               # Fallback 请求 JSON 队列
├── logs/                             # 服务运行日志
├── .env                              # 环境变量（LLM API Key 等）
├── .venv/                            # Python 虚拟环境（3.13）
├── CHANGELOG.md                      # 变更日志
└── MEMORY.md                         # 项目记忆卡
```

---

## 核心架构

### 三层处理流程（v2.0）

```
用户输入 → [输入适配器] → [Pipeline 提纯] → [输出适配器] → 文章/知识库
              │                  │                  │
         natural_language    LLM 提纯摘要       ArticleAdapter
         openclaw           标签提取           (khazix-writer skill)
         web_search [v2.0]  搜索补充 [v2.0]    LLM标题生成 [v2.0]
         rss (预留)         Fallback 兜底      website (预留)
         social_media (预留)                   app_h5 (预留)
```

### v2.0 数据流转

```
┌─────────────────────────────────────────────────────────────────────┐
│                        OpenClaw 调用流程                             │
│                                                                     │
│  ① Ping ──▶ {"status":"ok"}                                        │
│  ② Ingest ──▶ {"status":"accepted"} ──▶ 立即返回（0.014秒）          │
│       │                                                             │
│       └──▶ 后台 asyncio task:                                       │
│             ③ 解析输入 → ④ 保存 raw → ⑤ LLM 蒸馏 → ⑥ 保存 processed│
│             → ⑦ 刷新索引 → ⑧ 生成文章 → ⑨ 保存 output              │
│                                                                     │
│  去重: 60秒内相同内容指纹 → {"deduplicated": true}                   │
└─────────────────────────────────────────────────────────────────────┘
```

### 在线搜索集成方式（v2.0 新增）

```
┌───────────────┬───────────────┬───────────────┬───────────────┐
│  Pipeline增强  │  输入适配器    │   MCP 工具     │   REST API    │
│ (自动补充素材)  │ (按需搜索入库)  │ (Agent按需调用) │  (HTTP接口)   │
└───────────────┴───────────────┴───────────────┴───────────────┘
         │              │               │               │
         └──────────────┴───────────────┴───────────────┘
                              │
                    ┌─────────┴─────────┐
                    │  WebSearchService  │
                    │  httpx + BS4      │
                    │  9个搜索引擎       │
                    │  广告过滤          │
                    │  同步+异步         │
                    └───────────────────┘
```

---

## 模块详解

### 1. 配置中心 (`paos/config/`)

**设计原则**：零硬编码，`default.yaml` 是唯一真理来源。

- 所有配置项集中在 `default.yaml`
- 支持环境变量覆盖：`PAOS_` 前缀 + `__` 双下划线表示嵌套
- `.env` 文件通过 `python-dotenv` 自动加载

**v2.0 新增配置段**：

```yaml
search:
  default_engine: "duckduckgo"      # 默认搜索引擎
  auto_search: false                # 是否自动搜索
  auto_search_engine: "duckduckgo"  # 自动搜索使用的引擎
  max_results: 10                   # 最大结果数
  timeout: 15.0                     # 请求超时（秒）
  enrich_pipeline: false            # Pipeline提纯前是否自动搜索补充素材
```

### 2. 核心流程 (`paos/core/`)

#### Pipeline (`pipeline.py`)

信息处理主流程，`process_input()` 方法执行：

1. **保存原始输入** → SQLite + Markdown 文件
2. **(可选) 在线搜索补充** → 搜索相关内容补充素材 [v2.0 新增]
3. **LLM 提纯** → 调用 LLM 生成摘要和标签
4. **保存提纯结果** → SQLite + Markdown 文件 + 索引
5. **刷新知识汇总** → 重写 `processed_summary.md`
6. **自动生成文章** → 调用 ArticleAdapter（可配置关闭）

#### WebSearchService (`web_search.py`) [v2.0 新增]

在线搜索核心服务：
- **9 个搜索引擎**：DuckDuckGo（默认）、百度、Bing 国内/国际、搜狗、微信、头条、360、Ecosia
- **零 API Key**：通过 HTTP 请求 + BeautifulSoup 解析搜索结果页
- **广告过滤**：自动过滤 DuckDuckGo 广告结果
- **同步 + 异步**：`search()` / `asearch()` / `multi_search()`
- **URL 规范化**：DuckDuckGo 重定向 URL 自动解析真实链接

### 3. 适配器层 (`paos/adapters/`)

#### 输入适配器

| 适配器 | 状态 | 说明 |
|--------|------|------|
| `natural_language` | ✅ 可用 | 通用自然语言输入 |
| `openclaw` | ✅ 可用 | OpenClaw Webhook，支持 text/content/message 多字段容错 |
| `web_search` | ✅ 可用 [v2.0] | 在线搜索输入，搜索结果作为素材进入 Pipeline |
| `rss` | 🔲 预留 | RSS 订阅输入 |
| `social_media` | 🔲 预留 | 社交媒体输入 |

#### 输出适配器 — ArticleAdapter [v2.0 增强]

文章生成两步流程 + 空内容保护：

```
Step 1: LLM 生成原始文章
  ↓ 空内容检查 → 空则返回错误
  ↓ Fallback 检查 → Fallback 则返回错误
Step 2: khazix-writer skill 风格改写
  ↓ 空内容/Fallback 检查 → 保留 Step 1 内容
后处理: 补 H1 标题
  ↓ H2 提升 > LLM 生成 > 加粗文本 > 首段句子 > "未命名文章"
  ↓ 空内容保护: 内容 < 10 字符不调用 LLM
```

### 4. REST API (`paos/api/router.py`)

| 端点 | 方法 | 说明 | 模式 | 版本 |
|------|------|------|------|------|
| `/api/v1/ping` | GET | 轻量级健康检查 | 同步 | v2.0 新增 |
| `/api/v1/input` | POST | 通用输入接口 | 同步 | v1.0 |
| `/api/v1/webhook/openclaw` | POST | OpenClaw 入口 | **异步** | v2.0 改为异步 |
| `/api/v1/search` | POST | 在线搜索 | 同步 | v2.0 新增 |
| `/api/v1/search/ingest` | POST | 搜索并存入系统 | 同步 | v2.0 新增 |
| `/api/v1/search/engines` | GET | 列出搜索引擎 | 同步 | v2.0 新增 |
| `/api/v1/generate/article` | POST | 手动生成文章 | 同步 | v1.0 |
| `/api/v1/fallback` | GET | 查看 Fallback 队列 | 同步 | v1.0 |
| `/api/v1/fallback/{req_id}/complete` | POST | 提交 Fallback 结果 | 同步 | v1.0 |
| `/api/v1/index` | GET | 查询目录映射 | 同步 | v1.0 |
| `/api/v1/config` | GET | 查看当前配置（脱敏） | 同步 | v1.0 |

**v2.0 关键设计**：

- **异步 Ingest**：`/api/v1/webhook/openclaw` 立即返回 `{"status": "accepted"}`，后台 asyncio task 处理蒸馏+文章生成
- **内容去重**：基于内容指纹（去空白+前200字符 MD5），60秒窗口内跨来源去重
- **Ping 端点**：无 I/O 操作，供 OpenClaw 两步调用流程

### 5. MCP Server (`paos/mcp_server/`)

基于 FastMCP 的 AI Agent 接口，支持 stdio 和 SSE 两种传输模式。

**12 个 MCP 工具**：

| 工具 | 用途 | 版本 |
|------|------|------|
| `paos_health_check` | 检查健康状态（DB/索引/目录） | v1.0 |
| `paos_add_note` | 添加笔记/运维日志 | v1.0 |
| `paos_get_processed` | 按 ID 读取提纯记录 | v1.0 |
| `paos_list_index` | 查看全局目录索引 | v1.0 |
| `paos_update_tags` | 更新标签并刷新汇总 | v1.0 |
| `paos_list_fallback` | 查看 fallback 队列 | v1.0 |
| `paos_complete_fallback` | 补全 fallback 并联动更新 | v1.0 |
| `paos_regenerate_summary` | 重新生成知识汇总 | v1.0 |
| `paos_generate_article` | 基于最近记录生成文章 | v1.0 |
| `paos_web_search` | 在线搜索，返回结构化结果 | v2.0 新增 |
| `paos_web_search_and_ingest` | 搜索并将结果存入 PAOS | v2.0 新增 |
| `paos_list_search_engines` | 列出所有支持的搜索引擎 | v2.0 新增 |

---

## 外部集成

### OpenClaw 集成

PAOS 已部署为 OpenClaw workspace skill，实现自动触发保存。

**配置文件**：
- `~/.openclaw/workspace/skills/paos/SKILL.md` — Skill 定义（v2.0 精简）
- `~/.openclaw/workspace/SOUL.md` — 最高优先级规则（v2.0 简化流程）
- `~/.openclaw/workspace/USER.md` — 用户偏好（v2.0 同步更新）

**v2.0 调用流程**：

```
① Ping ──▶ 确认服务在线
② Ingest ──▶ 立即返回 {"status": "accepted"}
③ 确认 ──▶ "已存入 PAOS" → 结束（不做任何额外检查）
```

**关键规则**：
- 每条消息只调用一次 Ingest
- Ingest 后禁止查 fallback、查索引、查日志
- `status: accepted` = 成功，后台自动处理

---

## 技术栈

| 组件 | 技术 |
|------|------|
| Web 框架 | FastAPI |
| 数据库 | SQLite + SQLModel |
| 配置管理 | Pydantic Settings + YAML + dotenv |
| LLM | OpenAI 兼容 API（阶跃星辰 step-3.5-flash-2603） |
| MCP | FastMCP |
| 搜索 | httpx + BeautifulSoup4 [v2.0 新增] |
| Python | 3.13（Homebrew） |
| 服务管理 | nohup + uvicorn |

---

## 关键设计决策

1. **零硬编码**：所有可变参数集中在 `default.yaml`，代码中无硬编码路径/模型名/URL
2. **数据与代码分离**：`data/` 在 `.gitignore` 中，系统代码可任意迁移
3. **技能可插拔**：技能安装在 `skills/` 目录，与 `paos/` 核心代码完全分离
4. **Fallback 全量联动**：补全 fallback 后自动更新 DB + MD + Index + Summary
5. **Ingest 异步化**：OpenClaw webhook 立即返回，后台处理蒸馏+文章生成 [v2.0]
6. **内容去重**：基于内容指纹的 60 秒去重窗口，跨来源匹配 [v2.0]
7. **零 API Key 搜索**：默认 DuckDuckGo HTML 版，无需任何 API Key [v2.0]
8. **文章生成防护**：Step 1/Step 2 空内容检测 + LLM 标题生成 [v2.0]
9. **OpenClaw 精简交互**：三步流程（Ping → Ingest → 确认），禁止额外检查 [v2.0]

---

*文档版本：v2.0 | 更新时间：2026-04-17*
