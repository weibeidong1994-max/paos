"""
Agent Fallback Runner

用法：
    在 Kimi CLI 对话中，运行以下命令来处理 PAOS 的 fallback 队列：

    python -m paos.cli.fallback_runner

或者由 Kimi Agent 直接读取 pending 请求并调用 complete_request() 写回结果。
"""

from paos.core.fallback import complete_request, get_request, list_requests


def show_pending() -> list[dict]:
    """打印并返回所有 pending 的 fallback 请求"""
    pending = list_requests(status="pending")
    if not pending:
        print("✅ 当前没有 pending 的 fallback 请求。")
        return []

    print(f"📬 发现 {len(pending)} 个 pending 的 fallback 请求：\n")
    for req in pending:
        print(f"--- Request ID: {req['id']} ---")
        print(f"Task Type: {req['task_type']}")
        print(f"Created At: {req['created_at']}")
        print(f"System Prompt:\n{req['system_prompt']}\n")
        print(f"User Content:\n{req['user_content']}\n")
    return pending


def submit_result(req_id: str, result: str) -> bool:
    """提交 Agent 处理结果"""
    ok = complete_request(req_id, result)
    if ok:
        print(f"✅ Request {req_id} 处理结果已保存。")
    else:
        print(f"❌ Request {req_id} 未找到。")
    return ok


def main():
    """CLI 入口：展示 pending 请求，等待外部 Agent 处理"""
    show_pending()
    print("\n💡 提示：请让 Kimi Agent 读取上述请求并生成回复，")
    print("   然后调用 submit_result(req_id, result) 写回结果。")


if __name__ == "__main__":
    main()
