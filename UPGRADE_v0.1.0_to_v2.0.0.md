# PAOS v0.1.0 → v2.0.0 升级改动记录

> 升级日期: 2026-04-17 | 机器: wei 的 Mac (Apple Silicon)
> 由 Hermes Agent 执行

---

## 一、升级概览

| 项目 | v0.1.0 | v2.0.0 |
|------|--------|--------|
| 在线搜索 | 无 | 9 个搜索引擎，4 种集成方式 |
| Ingest 模式 | 同步（30-60秒阻塞） | 异步（0.014秒立即返回） |
| 内容去重 | 无 | 60秒窗口内容指纹去重 |
| 文章标题 | H2提升 / "未命名文章" | LLM 智能生成 8-20 字标题 |
| 文章生成保护 | 无空内容检测 | Step1/Step2 双重空内容保护 |
| Ping 端点 | 无 | GET /api/v1/ping |
| MCP 工具数 | 9 个 | 12 个（+3 搜索工具） |
| REST API 端点数 | 7 个 | 11 个（+4 新端点） |
| OpenClaw 集成 | 同步调用 | 三步异步流程 |
| Python 依赖 | 8 个 | 9 个（+beautifulsoup4） |

---

## 二、执行步骤与改动

### 步骤 1：停止服务
```bash
paos gateway stop
```

### 步骤 2：备份数据
```bash
cp -r data data_backup_v0.1.0
```
升级成功后已删除备份。

### 步骤 3：源代码覆盖
```bash
cd ~/Documents/trae_projects
tar xzf paos_v2.0.0_source.tar.gz
rsync -av --exclude='data' --exclude='.venv' --exclude='.env' --exclude='.git' paos_v2.0.0/ paos/
```
保留的文件：data/（运行时数据）、.venv/（Python 环境）、.env（API密钥）

### 步骤 4：安装新依赖
```bash
.venv/bin/python3 -m pip install "beautifulsoup4>=4.12.0"
# 安装结果: beautifulsoup4 4.14.3 + soupsieve 2.8.3
```
注意：原 .venv 缺少 pip，通过 `python3 -m ensurepip` 补装。

### 步骤 5：配置确认
`paos/config/default.yaml` 已自动包含新增配置，无需手动修改：
- `search:` 配置段（6 个参数）
- `adapters.input.enabled` 新增 `web_search`

### 步骤 6：修正 bin/paos 脚本路径
**问题**：v2.0.0 源码包来自另一台电脑，bin/paos 中 `PAOS_DIR` 指向 `paos_cocoding`。
**修复**：
```
PAOS_DIR="$HOME/Documents/trae_projects/paos_cocoding"
→
PAOS_DIR="$HOME/Documents/trae_projects/paos"
```

### 步骤 7：启动服务
```bash
paos gateway start
# PAOS started (PID: 67811)
```

---

## 三、代码文件变更明细

### 新增文件

| 文件 | 说明 |
|------|------|
| `paos/core/web_search.py` | 在线搜索核心服务（9引擎、广告过滤、同步+异步） |
| `paos/adapters/input/web_search.py` | 在线搜索输入适配器 |
| `paos/skills/__init__.py` | SkillRegistry / Skill / SkillManifest |
| `paos/skills/router.py` | Skills REST API 路由 |
| `CHANGELOG.md` | 变更日志 |
| `PROJECT.md` | 产品结构文档 |
| `skills/flowchart-generator-skill/` | 流程图生成技能 |
| `skills/md2wechat-skill/` | Markdown 转微信公众号格式技能（Go 项目） |
| `skills/nuwa-skill/` | 女娲造人（人物 Skill 生成）技能 |
| `skills/onepager/` | OnePage 信息图生成技能 |
| `scripts/ai_convert.py` | AI 内容转换脚本 |
| `scripts/capture_aios.py` | AIOS 内容采集脚本 |
| `scripts/capture_html.py` | HTML 内容采集脚本 |
| `scripts/capture_wechat.py` | 微信内容采集脚本 |
| `scripts/gen_structure.py` | 项目结构生成脚本 |

### 修改文件

| 文件 | 改动要点 |
|------|----------|
| `paos/api/router.py` | 新增 Ping/Search/SearchIngest/Engines 4个端点；OpenClaw webhook 改为异步；新增内容去重机制 |
| `paos/adapters/output/article.py` | LLM 智能标题生成；Step1/Step2 空内容保护 |
| `paos/core/pipeline.py` | 新增 WebSearchService 导入和搜索补充步骤 |
| `paos/services/input_service.py` | 注册 WebSearchAdapter；新增 parse/pipeline_async_process/ingest_async 方法 |
| `paos/config/settings.py` | 新增 SearchConfig 类和 Settings.search 字段 |
| `paos/config/default.yaml` | 新增 search 配置段和 web_search 适配器 |
| `paos/mcp_server/tools.py` | 新增 3 个搜索 MCP 工具 |
| `paos/mcp_server/server.py` | 注册 3 个新 MCP 工具 |
| `pyproject.toml` | 新增 beautifulsoup4 依赖 |
| `bin/paos` | 新增 snapshot（save/list/restore/diff）版本管理功能；改用 PID 文件+nohup 模式 |
| `skills/khazix-writer/SKILL.md` | 绝对禁区新增第 8 条"不输出作者和联系方式" |
| `.gitignore` | 新增 data 子目录的显式忽略规则 |

---

## 四、验证结果

| 验证项 | 期望 | 实际 | 状态 |
|--------|------|------|------|
| GET /api/v1/ping | {"status":"ok"} | {"status":"ok","service":"paos"} | PASS |
| GET /api/v1/search/engines | 9 个引擎 | 9 个引擎 | PASS |
| POST /api/v1/search (百度) | 搜索结果 | 返回 3 条结果 | PASS |
| POST /api/v1/search (DuckDuckGo) | 搜索结果 | 0 结果（国内网络限制） | KNOWN |
| POST /api/v1/webhook/openclaw | {"status":"accepted"} | {"status":"accepted"} | PASS |
| GET /api/v1/config (search段) | 包含 search | 包含 search | PASS |

---

## 五、OpenClaw 配置更新

### 新增文件
- `~/.openclaw/workspace/skills/paos/SKILL.md` — v2.0 版本，Ping+Ingest 两步异步流程

### 修改文件
- `~/.openclaw/workspace/SOUL.md` — 重写，加入 PAOS 最高优先级规则
- `~/.openclaw/workspace/USER.md` — 重写，加入 PAOS Integration 段

### 删除文件（旧版 skill，已被新版替代）
- `~/.openclaw/workspace/skills/paos-integration/` — 整个目录已删除

关键变化：
- v0.1.0 skill 用 Python 脚本调用 PAOS，v2.0.0 改为直接用 curl
- v0.1.0 同步等待返回，v2.0.0 异步立即返回
- v0.1.0 有查询/生成文章功能，v2.0.0 简化为只保存

---

## 六、清理记录

| 清理项 | 说明 |
|--------|------|
| `=1.0.0` | 根目录空文件（pip 残留），已删除 |
| `.DS_Store` | macOS 缓存，已清理 |
| `__pycache__/` | Python 编译缓存（10个目录+32个pyc），已清理 |
| `.pytest_cache/` | pytest 缓存，已删除 |
| `data_backup_v0.1.0/` | 升级前备份，已确认成功后删除 |
| `paos_v2.0.0_source.tar.gz` | v2.0.0 源码包，已删除 |
| `paos_v2.0.0_MIGRATION.md` | 迁移文档，已删除 |
| `~/Desktop/paos-v0.1.0.tar.gz` | v0.1.0 打包文件，已删除 |
| `~/Desktop/PAOS_MIGRATION_GUIDE.md` | v0.1.0 迁移文档，已删除 |
| `~/.openclaw/workspace/.tmp_paos_content.txt` | OpenClaw 临时文件，已删除 |
| `~/.openclaw/workspace/skills/paos-integration/` | 旧版 PAOS skill，已被新版 paos/ 替代 |

---

## 七、已知问题

1. **DuckDuckGo 搜索在国内无结果** — HTML 抓取被网络限制，百度/搜狗/Bing国内版正常
2. **bin/paos 路径硬编码** — 从另一台电脑迁移过来时需要手动修正 PAOS_DIR
3. **launchd plist 未更新** — 当前用 bin/paos (PID+nohup) 管理，未切换回 launchd

---

*文档生成时间: 2026-04-17*
