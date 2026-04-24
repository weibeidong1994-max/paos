# PAOS × OpenClaw × Hermes Agent 三方联动方案

> 设计日期：2026-04-15
> 前置文档：`archive/CODE_REVIEW.md`（代码审查报告，P0/P1 问题已修复）

---

## 核心设计意图

本方案确立以下架构原则：

1. **PAOS 是唯一的知识归宿和核心系统** —— 所有知识数据的提纯、存储、索引、输出都在 PAOS 内完成。
2. **OpenClaw 是 PAOS 的对外接口层** —— 所有外部用户/系统不直接调用 PAOS，而是通过 OpenClaw 来"使用" PAOS。
3. **Hermes 是 PAOS 的开发者/运维管家** —— 类似 Kimi Agent，Hermes 直接管理 PAOS 的**代码、实现和服务**，为 PAOS 修 bug、加功能、优化架构。

---

## 一、三方能力画像与定位

| 维度 | PAOS | OpenClaw | Hermes Agent |
|------|------|----------|-------------|
| **核心定位** | 知识中枢 + 数据处理引擎 | PAOS 的**对外接口层** + 通信网关 | PAOS 的**开发者 + 运维管家** |
| **最强能力** | 信息提纯、三重存储、结构化索引 | 50+平台接入、Webhook触发、硬件桥接、协议适配 | 代码生成、自动修复、闭环学习、多终端执行、持久记忆 |
| **与 PAOS 的关系** | 被管理、被使用 | **使用 PAOS** —— 把外部请求翻译成 PAOS API 调用 | **管理 PAOS** —— 直接读写 `paos/` 代码库 |
| **数据视角** | 数据的**唯一归宿** | 数据的**入口网关**——负责把外部输入送进 PAOS | 数据的**优化者**——通过修改 PAOS 代码来提升数据处理能力 |
| **通信方式** | REST API (FastAPI) | Webhook + Gateway + MCP（调用 PAOS） | CLI + 文件系统直接操作 + 代码编辑 |
| **存储格式** | SQLite + Markdown + index.json | 轻量缓存 + 路由配置 | 与 PAOS 共享代码库，独立运行时记忆 |
| **短板** | 无通信渠道、无自主学习 | 无提纯能力、无长期知识管理 | 不直接面向终端用户做日常交互（那是 OpenClaw 的事） |

**一句话定位**：
- **OpenClaw = PAOS 的嘴和耳朵** —— 替 PAOS 对接外部世界，所有用户通过 OpenClaw 使用 PAOS
- **PAOS = 大脑和工厂** —— 核心的知识提纯、存储、输出
- **Hermes = PAOS 的工程师** —— 直接写代码、修 bug、改配置、部署服务，让 PAOS 越变越强

---

## 二、三方联动架构

```
                        外部用户/世界
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
   [微信] [飞书] [Telegram] [钉钉] [邮件] [硬件] ...
        │                     │                     │
        └─────────────────────┼─────────────────────┘
                              ↓
              ┌───────────────────────────────┐
              │      OpenClaw（接口层）        │
              │  • 接收多渠道碎片化输入         │
              │  • 协议适配和轻量预处理         │
              │  • 调用 PAOS API               │
              │  • 将 PAOS 输出推送回用户       │
              └───────────────┬───────────────┘
                              │
                              ↓ 调用 PAOS API
              ┌───────────────────────────────┐
              │         PAOS（核心系统）        │
              │  ┌─────────────────────────┐  │
              │  │  输入层 → 处理层 → 输出层 │  │
              │  │  提纯 Pipeline           │  │
              │  │  SQLite + MD + index.json│  │
              │  └─────────────────────────┘  │
              └───────────────────────────────┘
                     ▲                    │
                     │ 直接管理/修改代码    │
                     │                    │
              ┌──────┴────────────────────┐
              │    Hermes（开发者/运维）    │
              │  • 读取 paos/ 代码         │
              │  • 修复 bug / 添加功能     │
              │  • 优化配置和架构          │
              │  • 运行测试和部署          │
              │  • 生成 Skill 沉淀经验     │
              └────────────────────────────┘
```

### 架构说明

- **OpenClaw 不存储知识**，它只作为 PAOS 的代理网关：接收外部输入 → 调用 PAOS API → 把结果推回给用户。
- **PAOS 不直接面对外部渠道**，所有外部通信都经过 OpenClaw 这层接口。
- **Hermes 不通过 MCP 工具"查询" PAOS 的数据**，它直接管理 PAOS 的代码实现。当 PAOS 的 fallback 解析有问题时，Hermes 修改的是 `paos/core/pipeline.py`；当 PAOS 需要新功能时，Hermes 直接写代码。

---

## 三、OpenClaw 作为 PAOS 接口层的详细设计

### 3.1 核心原则：OpenClaw 是 PAOS 的唯一外部接口

用户在任何渠道（微信、飞书、Telegram、邮件、语音等）与 PAOS 交互时，感知到的"对方"是 OpenClaw，但本质上 OpenClaw 只是在代理 PAOS。

### 3.2 四种典型交互场景

**场景 A：随手记（最轻量）**
```
用户 → 微信发一条消息
     → OpenClaw 捕获
     → OpenClaw 调用 PAOS POST /api/v1/webhook/openclaw
     → PAOS 自动提纯 + 存储
     → OpenClaw 向用户回复"已保存"
```

**场景 B：查询知识**
```
用户 → "我上周关于 RAG 的笔记有哪些？"
     → OpenClaw 捕获
     → OpenClaw 调用 PAOS GET /api/v1/index?source=...
     → PAOS 返回检索结果
     → OpenClaw 整理后回复用户
```

**场景 C：生成内容**
```
用户 → "帮我写一篇关于 AI Agent 的文章"
     → OpenClaw 捕获
     → OpenClaw 调用 PAOS POST /api/v1/generate/article
     → PAOS 生成文章并返回 file_path
     → OpenClaw 将文章摘要和文件路径推送给用户
```

**场景 D：系统指令（需要 Hermes 介入开发）**
```
用户 → "PAOS 的 fallback 解析好像有问题，帮我修一下"
     → OpenClaw 捕获
     → OpenClaw 识别为"开发/运维指令"
     → OpenClaw 将任务转交给 Hermes（或通过用户转发给 Hermes）
     → Hermes 直接修改 `paos/core/pipeline.py`
     → Hermes 运行测试确认修复
     → Hermes 通知用户/OpenClaw"已修复"
```

### 3.3 OpenClaw 对接 PAOS 的技术方案

**方案 A：直接调用 PAOS REST API（当前已实现）**

OpenClaw 通过 HTTP 直接调用 PAOS 的 FastAPI 接口：
- `POST /api/v1/webhook/openclaw` —— 接收碎片输入
- `GET /api/v1/index` —— 查询知识库
- `POST /api/v1/generate/article` —— 生成文章
- `GET /api/v1/fallback` —— 查询 fallback 队列

**方案 B：通过 MCP Server 调用 PAOS（已预留）**

PAOS 已实现 MCP Server（`python -m paos.mcp_server`）。OpenClaw 也可以作为 MCP Client 连接 PAOS，获得更细粒度的工具调用能力。这在 OpenClaw 需要执行复杂多步操作时更有优势。

**推荐**：日常输入走 REST API（轻量），复杂运维/查询场景可走 MCP（精细控制）。

---

## 四、Hermes 直接管理 PAOS 的详细设计

### 4.1 核心原则：Hermes 是 PAOS 的"全职工程师"

Hermes 不像普通用户那样"使用"PAOS，而是像 Kimi Agent 管理代码项目一样，直接：
- 读取 `paos/` 目录的源代码
- 修改配置文件和实现逻辑
- 运行测试和部署命令
- 生成 Skill 沉淀开发经验

### 4.2 Hermes 的职责矩阵

| 职责 | 负责方 | 具体说明 |
|------|--------|----------|
| **功能开发** | Hermes | 为 PAOS 开发新适配器、新 Pipeline 步骤、新输出格式 |
| **Bug 修复** | Hermes | 修复 PAOS 测试失败、解析错误、存储异常等问题 |
| **架构优化** | Hermes | 重构慢查询、优化 Pipeline 性能、改进存储结构 |
| **配置调优** | Hermes | 调整 `default.yaml`、环境变量映射、部署参数 |
| **测试维护** | Hermes | 补充测试用例、修复 flaky test、提升覆盖率 |
| **部署运维** | Hermes | 运行 `install.sh`、启动服务、查看日志、热更新 |
| **数据质量优化（通过改代码实现）** | Hermes | 发现标签解析脆弱 → 改 `_parse_distillation`；发现索引慢 → 加向量库 |

### 4.3 Hermes 不做的职责

| 职责 | 负责方 | 原因 |
|------|--------|------|
| 日常信息输入 | OpenClaw | Hermes 不替用户发微信 |
| 知识查询回复 | OpenClaw | Hermes 不直接回复"你上周的 RAG 笔记是..." |
| 直接操作 PAOS 数据库里的单条记录 | 不建议 | Hermes 通过改代码来提升系统能力，而不是手工修数据 |

### 4.4 协作流程详解

**流程 1：用户发现 PAOS 有 Bug**
```
用户在微信里说："PAOS 生成文章时好像没用到我传的 prompt_override"
  → OpenClaw 捕获并转发给用户与 Hermes 的对话
  → Hermes 读取 `paos/adapters/output/article.py`
  → 发现 key 不匹配（`prompt_template` vs `prompt_override`）
  → Hermes 修改代码并运行 `pytest tests/`
  → 测试通过后，Hermes 回复："已修复，prompt_override 现在可以正确传递了"
```

**流程 2：用户想要新功能**
```
用户说："希望 PAOS 能支持小红书作为输入源"
  → Hermes 读取 `paos/adapters/input/` 现有实现
  → 新建 `xiaohongshu.py` 适配器
  → 在 `input_service.py` 中注册
  → 编写测试并运行
  → 更新 README 和 MEMORY.md
  → 通知用户："已添加小红书输入适配器，重启 PAOS 后生效"
```

**流程 3：Hermes 主动优化（学习闭环）**
```
Hermes 定期审视 PAOS 代码和测试报告
  → 发现 `index.json` 在大数据量下加载慢
  → Hermes 设计分页方案，修改 `index_manager.py`
  → 补充性能测试
  → 运行测试确认无回归
  → 将"index.json 分页优化"沉淀为 Skill 文档
```

**流程 4：Hermes 处理 PAOS Fallback（通过改系统，而非手工补全）**
```
用户说："PAOS 没有 API Key 时老是 fallback，能不能自动处理？"
  → Hermes 分析 `paos/core/fallback.py` 和 `paos/core/llm.py`
  → 设计"自动 fallback 补全"机制（或接入本地 LLM 兜底）
  → 修改代码实现
  → 运行端到端测试验证
  → 更新文档
```

> 💡 **关键区别**：在旧方案中 Hermes 通过 MCP 工具"查询然后手工补全"fallback；在新方案中，Hermes 做的是**修改 PAOS 系统本身**，让 PAOS 自己变得更智能或更容错。

---

## 五、知识数据统一方案

### 5.1 核心原则不变：PAOS 是唯一知识归宿

```
所有知识数据 → PAOS data/ 目录
  ├── paos.db          ← 结构化数据（唯一真相源）
  ├── index.json       ← 全局索引（唯一目录）
  ├── raw/             ← 原始输入
  ├── processed/       ← 提纯知识
  ├── output/          ← 生成内容
  └── processed_summary.md  ← 自动汇总
```

### 5.2 三方数据边界

**OpenClaw**
- **不存储知识**，只存储轻量路由配置和会话上下文
- 所有用户输入通过 OpenClaw 进入 PAOS，但数据最终只留在 PAOS
- OpenClaw 可以缓存 PAOS 的 API 响应用于快速回复，但不作为主存储

**PAOS**
- **唯一主存储**
- OpenClaw 通过 API 读取 PAOS 的数据来回复用户
- Hermes 通过修改 PAOS 代码来优化 PAOS 的数据处理能力

**Hermes**
- **不直接持有 PAOS 的用户知识数据**
- Hermes 的 `MEMORY.md/USER.md` 只记录它作为"PAOS 开发者"的经验（如"上次修这个 bug 改了哪个文件"）
- Hermes 生成的 Skill 文档可以保存在 `~/.hermes/skills/` 中，但 Skill 本身是关于"如何开发和维护 PAOS"的，不是关于用户的知识内容

---

## 六、技术对接实现方案

### 6.1 OpenClaw ↔ PAOS（核心接口层）

**当前已实现**：OpenClaw Webhook 适配器（`POST /api/v1/webhook/openclaw`）

**需要增强**：
1. OpenClaw 配置中把 PAOS 设为默认后端：
```json5
{
  backends: {
    default: "paos",
    paos: {
      type: "webhook",
      url: "http://localhost:8000/api/v1/webhook/openclaw",
      // 或 MCP 模式：
      // type: "mcp",
      // command: "python -m paos.mcp_server"
    }
  }
}
```

2. OpenClaw 增加 PAOS 专用的消息路由：
   - 识别 `note` / `command` / `query` / `feedback` 类型
   - `query` 调用 `GET /api/v1/index`
   - `command` 调用对应 PAOS API（如文章生成）
   - 开发/运维类指令可标记为 `devops`，转发给 Hermes 或通知用户联系 Hermes

3. OpenClaw 增加 PAOS 输出格式化：
   - 把 PAOS 返回的 JSON 整理成适合各渠道阅读的文本/卡片

### 6.2 Hermes ↔ PAOS（直接代码管理）

**Hermes 不通过 API/MCP 管理 PAOS，而是通过文件系统直接操作。**

Hermes 的工作目录就是 PAOS 项目根目录：`/Users/weibeidongm2/Documents/trae_projects/paos/`

Hermes 的常用操作：
```bash
# 读取代码
cat paos/core/pipeline.py

# 修改代码后运行测试
pytest tests/ -v

# 部署/重启
uvicorn paos.main:app --reload

# 查看数据状态
cat data/processed_summary.md
python -m paos.cli.fallback_runner
```

**Hermes 的触发方式**：
1. **用户在 OpenClaw 渠道发送开发/运维指令** → OpenClaw 识别后通知用户"已转交给 Hermes 工程师" → Hermes 开始处理
2. **用户直接在 Hermes CLI 中对话** → "帮我看看 PAOS 代码有什么可以优化的" → Hermes 直接读代码分析
3. **Hermes 定期主动审视** → 每周检查一次 PAOS 测试覆盖、代码质量、待办事项

### 6.3 Hermes 的 MCP 是否还需要？

当前已实现的 `paos/mcp_server/` 不再主要服务于 Hermes，而是作为 **OpenClaw 调用 PAOS 的可选方案** 保留：
- 当 OpenClaw 需要执行复杂多步操作（如"先查索引，再生成文章，最后更新标签"）时，通过 MCP 工具链比多次 HTTP 调用更高效
- 也可以供其他 MCP Client（如 Claude Desktop）使用

---

## 七、实施路线

### Phase 1（1-2周）：跑通 OpenClaw → PAOS 接口层

- [ ] OpenClaw 配置 PAOS 为默认后端（Webhook 模式）
- [ ] OpenClaw 实现 PAOS 消息路由（note/query/command/devops）
- [ ] PAOS OpenClaw 适配器增强：支持消息类型识别和上下文传递
- [ ] 端到端测试：微信发消息 → OpenClaw → PAOS 提纯存储 → OpenClaw 回复

### Phase 2（2-3周）：Hermes 开始接管 PAOS 开发维护

- [ ] Hermes 配置 PAOS 项目为工作目录
- [ ] Hermes 建立第一个运维 Skill："PAOS 健康检查与修复流程"
- [ ] Hermes 演练一次完整 bug 修复：读取代码 → 修改 → 运行测试 → 提交
- [ ] 端到端测试：用户报 bug → OpenClaw 转交 → Hermes 修复 → 验证

### Phase 3（3-4周）：自动化与闭环

- [ ] Hermes 定期自动审视 PAOS 代码（每周扫描测试状态、TODO、架构问题）
- [ ] Hermes 自动生成并优化 PAOS 适配器（如社交媒体输入适配器）
- [ ] OpenClaw 支持 MCP 模式调用 PAOS（复杂多步操作场景）
- [ ] 完整三方联动测试

### Phase 4（5-6周）：系统增强

- [ ] PAOS 引入向量数据库，OpenClaw 的查询能力增强
- [ ] PAOS 知识管理 Web UI（由 Hermes 开发）
- [ ] OpenClaw 支持更智能的上下文多轮对话
- [ ] 数据迁移和备份工具（由 Hermes 开发）

---

## 八、关键设计决策

| 决策 | 选择 | 原因 |
|------|------|------|
| PAOS 的对外接口 | OpenClaw | 统一网关，50+平台接入，用户无需关心 PAOS API |
| OpenClaw 与 PAOS 通信 | REST API 为主，MCP 为辅 | REST 足够轻量；MCP 留给复杂多步场景 |
| Hermes 与 PAOS 关系 | 直接代码管理 | Hermes 的优势是代码生成和系统维护，不是手工查询数据 |
| 知识存储唯一归宿 | PAOS data/ | 避免数据分散，OpenClaw 不存、Hermes 也不存用户知识 |
| Hermes 记忆 | 独立保留 | Hermes 的 MEMORY.md/USER.md 记录的是"如何维护 PAOS"的开发经验 |
| MCP Server 归属 | 作为 OpenClaw 的可选调用方式 | 已实现的 `paos/mcp_server/` 不废弃，转交 OpenClaw 使用 |

---

*文档生成时间：2026-04-15*  
*更新时间：2026-04-15（Hermes 定位调整为 PAOS 开发者/运维管家，OpenClaw 调整为 PAOS 对外接口层）*
