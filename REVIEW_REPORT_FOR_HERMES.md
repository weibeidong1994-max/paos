# PAOS v0.2.0 改进报告

> 基于 Kimi Code Review 报告，由 Hermes Agent 逐项修复。
> 修复日期: 2026-04-17

---

## 修复总览

| 优先级 | 编号 | 问题 | 状态 | 改动文件 |
|--------|------|------|------|----------|
| P0 | C1 | DEBUG 代码泄露 API Key | **已修复** | `paos/config/settings.py` |
| P0 | C2 | 端到端测试断言失败 | **已修复** | `tests/test_e2e.py` |
| P1 | M1 | 去重缓存无清理（内存泄漏） | **已修复** | `paos/api/router.py` |
| P1 | M2 | MCP 测试调用真实 LLM | **已修复** | `tests/test_mcp_server.py` |
| P1 | M3 | 缺少 python-dotenv 显式依赖 | **已修复** | `pyproject.toml` |
| P1 | M4 | regenerate_summary 注释不符 | **已修复** | `paos/core/pipeline.py` |
| P1 | M5 | asyncio.get_event_loop() 已弃用 | **已修复** | `paos/api/router.py` |
| P2 | M6 | 输出适配器全局单例并发隐患 | **已修复** | `paos/services/output_service.py`, `tests/test_e2e.py` |
| P2 | m1 | 关联原文文件名跨秒不一致 | **已修复** | `paos/core/pipeline.py` |
| P2 | m2 | strip 写法可读性差 | **已修复** | `paos/adapters/output/article.py` |
| P2 | m3 | multi_search 顺序执行 | **保留** | 预留优化点，当前性能可接受 |
| P2 | m4 | 百度跳转链接未解析 | **已修复** | `paos/core/web_search.py` |
| P2 | m5 | complete_fallback 每次新建 IndexManager | **已修复** | `paos/api/router.py` |
| P2 | m6 | Skills Router 参数非 RESTful | **已修复** | `paos/skills/router.py` |
| P2 | m7 | 空 `__init__.py` 文件 | **已修复** | 5 个 `__init__.py` |

**14/15 项已修复，1 项保留（m3 多引擎并发，非必须）。**

---

## 详细改动

### C1. 删除 DEBUG 代码（安全红线）

**文件**: `paos/config/settings.py` 第 137-140 行

删除了 4 行调试代码：
```python
# 已删除:
# import sys
# print(f"[DEBUG load_settings] merged llm keys: ...")
# print(f"[DEBUG load_settings] api_key value: {repr(...)}")
```

**验证**: 重启后 stderr 无 API Key 输出。

---

### C2 + M6. 修复测试断言 + 输出适配器工厂化

**根因**: `ArticleAdapter` 的 Step 2 (khazix-writer) 会覆盖 Step 1 内容，测试 FakeLLM 返回值不含断言关键词。

**修复方案**:

1. `paos/services/output_service.py` — 将全局单例 `_OUTPUT_ADAPTERS` dict 改为工厂函数 `_get_output_adapter(name)`，每次调用创建新实例。`OutputService.generate()` 新增 `adapter_override` 参数支持依赖注入。

2. `tests/test_e2e.py` — FakeLLMClient 返回值包含 `请用产品经理的视角` 关键词；使用 `_get_output_adapter()` + `adapter_override=` 注入，不再修改全局变量。

---

### M1. 去重缓存 TTL 清理

**文件**: `paos/api/router.py` 第 18-50 行

新增 `_cleanup_cache()` 函数，在 `_check_dedup()` 和 `_record_ingest()` 中自动调用，清理超过 60 秒的过期条目。import 从函数内移到模块顶部（`hashlib`, `re`, `time`, `asyncio`）。

---

### M2. MCP 测试避免调用真实 LLM

**文件**: `tests/test_mcp_server.py` fixture `mcp_env`

在 setup 时将 `settings.llm.api_key = ""` 强制 fallback 模式，teardown 时恢复原始值。同时正确保存/恢复 `settings.database.filename`。

---

### M3. 添加 python-dotenv 显式依赖

**文件**: `pyproject.toml`

在 `dependencies` 列表末尾添加 `"python-dotenv>=1.0.0"`。

---

### M4. regenerate_summary 注释修正

**文件**: `paos/core/pipeline.py` 第 159 行

`"""从 DB 重新生成极简提纯知识汇总文件到 output/"""` → `"""从 DB 重新生成极简提纯知识汇总文件到 data_dir 根目录"""`

---

### M5. asyncio API 规范化

**文件**: `paos/api/router.py` 第 110 行

`asyncio.get_event_loop().create_task(...)` → `asyncio.create_task(...)`

同时清理了函数内的 `import asyncio` 和 `import time as _time`，统一到模块顶部。

---

### m1. 关联原文文件名一致性

**文件**: `paos/core/pipeline.py`

在 `process_input` 的两个 metadata 构建处添加 `"raw_filename": raw_filename`，在 `_build_processed_md` 中优先从 metadata 读取，fallback 到时间戳计算。

---

### m2. strip 可读性

**文件**: `paos/adapters/output/article.py` 第 65 行

`strip("\"'\u201c\u201d《》【】")` → `strip('''"\u2018\u201c《》【】''')`

---

### m4. 百度搜索结果 URL 解析

**文件**: `paos/core/web_search.py` `_normalize_url` 函数

百度搜索结果的 `/link?url=REAL_URL` 跳转链接，现在解析出真实 URL 返回，而非原样返回跳转链接。

---

### m5. IndexManager 复用

**文件**: `paos/api/router.py`

模块级创建 `index_manager = IndexManager()`，在 `complete_fallback` 和 `get_index` 路由中复用，避免每次请求重新加载 `index.json`。

---

### m6. Skills Router RESTful 规范

**文件**: `paos/skills/router.py`

- 新增 `InstallSkillRequest(BaseModel)` 和 `CallSkillRequest(BaseModel)` Pydantic 模型
- `install_skill` 和 `call_skill` 改为接收 JSON body，不再通过 query/mixed 参数传递

---

### m7. __init__.py 包级 docstring

**文件**: 5 个 `__init__.py`

```
paos/adapters/__init__.py  → """PAOS Output Adapters: article, website, app_h5."""
paos/api/__init__.py       → """PAOS REST API routes."""
paos/core/__init__.py      → """PAOS Core: models, pipeline, LLM client, fallback queue."""
paos/services/__init__.py  → """PAOS Services: input processing, output generation."""
paos/storage/__init__.py   → """PAOS Storage: SQLite store, index manager."""
```

---

## 测试结果

```
pytest tests/ -v
============================= 18 passed in 53.08s ==============================

tests/test_e2e.py           1/1 PASSED   ✅ (之前 FAILED)
tests/test_mcp_server.py    9/9 PASSED   ✅ (之前部分 timeout)
tests/test_pipeline.py      2/2 PASSED   ✅
tests/test_rss_adapter.py   6/6 PASSED   ✅
```

## 服务验证

```
curl http://127.0.0.1:8000/api/v1/ping
→ {"status":"ok","service":"paos"}          ✅

curl http://127.0.0.1:8000/api/v1/config | app_version
→ PAOS v0.2.0                               ✅

stderr 日志
→ 无 API Key 输出                            ✅

去重验证 (连续两次相同内容)
→ 第1次: accepted  第2次: deduplicated:true   ✅
```

---

## 未修复项

| 编号 | 原因 |
|------|------|
| m3 (multi_search 并发) | 预留优化点，当前单次搜索耗时可接受。如需优化可用 `asyncio.gather` 调用 `asearch`。 |

---

*报告生成时间: 2026-04-17*
*执行者: Hermes Agent*
*Reviewer: Kimi Code CLI*
