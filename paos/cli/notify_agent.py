"""
Notify Agent - 一键生成提示语，用于在 Kimi CLI 对话中触发 Agent 补全

用法：
    cd /Users/weibeidongm2/Documents/trae_projects/paos
    source .venv/bin/activate
    python -m paos.cli.notify_agent
"""

from paos.core.fallback import list_requests


def generate_prompt() -> str:
    pending = list_requests(status="pending")
    if not pending:
        print("✅ 当前没有 pending 的 fallback 请求，无需通知 Agent。")
        return ""

    lines = [f"PAOS 当前有 {len(pending)} 个 pending 的 fallback 请求，请帮我处理并补全结果。\n"]
    for req in pending:
        lines.append(f"--- Request ID: {req['id']} ---")
        lines.append(f"任务类型: {req['task_type']}")
        lines.append(f"System Prompt:\n{req['system_prompt']}")
        lines.append(f"User Content:\n{req['user_content']}\n")

    lines.append("处理完成后，请调用 `paos.core.fallback.complete_request(req_id, result)` 写回结果，")
    lines.append("并更新对应的 SQLite 记录和 Markdown 文件（如果需要）。")
    return "\n".join(lines)


def main():
    prompt = generate_prompt()
    if prompt:
        print("\n" + "=" * 60)
        print("📋 请将以下内容复制到 Kimi CLI 对话中发送给 Agent：")
        print("=" * 60 + "\n")
        print(prompt)
        print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
