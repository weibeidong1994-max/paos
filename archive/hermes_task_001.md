# Hermes Task #001：为 PAOS 实现 RSS 输入适配器

> 任务类型：功能开发（新增文件 + 注册 + 测试）
> 预计耗时：15-30 分钟
> 项目路径：`/Users/weibeidongm2/Documents/trae_projects/paos/`

---

## 一、你的角色

你是 **Hermes Agent**，PAOS 的开发者与运维管家。
你的职责是直接读写 `paos/` 代码库，为 PAOS 开发新功能、修复 bug、优化架构。
你不是通过 API "查询" PAOS 数据，而是像人类工程师一样直接修改源代码并运行测试。

---

## 二、任务目标

为 PAOS 添加一个 **RSS 输入适配器**（`RSSAdapter`），使 PAOS 能够接收 RSS Feed 作为输入来源。

完成本任务后，用户可以通过以下方式向 PAOS 提交 RSS 内容：
```bash
curl -X POST http://127.0.0.1:8000/api/v1/input \
  -H "Content-Type: application/json" \
  -d '{"source": "rss", "data": {"content": "<rss>...</rss>"}}'
```

---

## 三、项目上下文

PAOS 的输入适配器采用统一抽象：
- 基类：`paos/adapters/input/base.py` → `BaseInputAdapter`
- 每个适配器继承基类，实现 `parse(self, raw_data: dict) -> InputItem`
- 适配器注册在：`paos/services/input_service.py` 的 `_INPUT_ADAPTERS` 字典中

**参考实现**：
- `paos/adapters/input/natural_language.py` —— 最简单的适配器
- `paos/adapters/input/openclaw.py` —— 带 metadata 处理的适配器

---

## 四、具体需求

### 4.1 新建文件

在 `paos/adapters/input/rss.py` 中实现 `RSSAdapter`：

```python
from paos.adapters.input.base import BaseInputAdapter
from paos.core.models import InputItem


class RSSAdapter(BaseInputAdapter):
    name = "rss"

    def parse(self, raw_data: dict) -> InputItem:
        # 实现逻辑...
```

**解析逻辑要求**：
1. `raw_data` 支持两种输入形式：
   - `{"content": "<rss>...</rss>"}`：直接传入 RSS XML 字符串
   - `{"url": "https://example.com/feed.xml"}`：传入 URL（可选支持，如果实现请用标准库 `urllib` 获取）
2. **优先使用标准库**（`xml.etree.ElementTree`）解析 RSS 2.0 格式，**不要引入外部依赖**（如 `feedparser`）。
3. 从 XML 中提取 `<channel><title>` 作为 feed 标题。
4. 从所有 `<item>` 中提取最近一条（列表第一个即可）的 `title`、`description`（或 `summary`）、`link`。
5. 构造 `InputItem`：
   - `source = self.name`
   - `content` 格式：`【{feed_title}】{item_title}\n\n{item_description}\n\n原文：{item_link}`
   - `metadata` 包含：`{"feed_title": ..., "item_link": ..., "total_entries": <item总数>}`
6. 如果解析失败或没有 `<item>`，抛出 `ValueError`。

### 4.2 注册适配器

修改 `paos/services/input_service.py`：
- import `RSSAdapter`
- 在 `_INPUT_ADAPTERS` 字典中注册：`RSSAdapter.name: RSSAdapter()`

### 4.3 编写测试

在 `tests/test_rss_adapter.py` 中编写测试：

```python
import pytest
from paos.adapters.input.rss import RSSAdapter
from paos.core.models import InputItem

SAMPLE_RSS = """<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <item>
      <title>First Post</title>
      <description>This is the first post.</description>
      <link>https://example.com/1</link>
    </item>
    <item>
      <title>Second Post</title>
      <description>This is the second post.</description>
      <link>https://example.com/2</link>
    </item>
  </channel>
</rss>
"""

def test_rss_adapter_parses_first_item():
    adapter = RSSAdapter()
    item = adapter.parse({"content": SAMPLE_RSS})
    assert item.source == "rss"
    assert "Test Feed" in item.content
    assert "First Post" in item.content
    assert "https://example.com/1" in item.content
    assert item.metadata["total_entries"] == 2
```

### 4.4 运行测试

确保新增测试和原有测试全部通过：
```bash
cd /Users/weibeidongm2/Documents/trae_projects/paos
pytest tests/ -v
```

---

## 五、验收标准

- [ ] `paos/adapters/input/rss.py` 文件存在且逻辑正确
- [ ] `paos/services/input_service.py` 已注册 RSSAdapter
- [ ] `tests/test_rss_adapter.py` 测试通过
- [ ] **全部测试**（原有 + 新增）通过，无回归
- [ ] 代码风格与现有项目一致（PEP 8、类型注解可选但推荐）

---

## 六、约束与提醒

1. **不要修改现有适配器的行为**，只新增。
2. **不要引入外部依赖**，用标准库 `xml.etree.ElementTree` 解析 RSS。
3. 如果 URL 获取太复杂或环境限制，**可以只实现 `content` 字符串解析**，并在代码注释中说明 URL 模式待扩展。
4. 有任何不确定的地方，先阅读参考文件（`natural_language.py`、`openclaw.py`、`base.py`）。
5. 完成后请告诉我：你改了哪些文件、测试结果如何、以及下一步建议做什么。

---

## 七、为什么这个任务有价值

这是 INTEGRATION_PLAN.md 中 "社交媒体适配器" 方向的第一步。
RSS 是社交媒体信息汇入 PAOS 的基础管道，跑通它意味着 PAOS 开始具备"主动拉取外部信息源"的能力，而不仅限于被动接收用户输入。
