# biomni/agent/nodes/retry_decider.py  v2.4
"""
Retry Decider 节点——基于错误分类决定是否重试。

职责：
  - 检查 error.retryable 标志
  - 计算重试次数，防止无限重试
  - 生成给 LLM 的重试建议（plan_correction_hint）
  - 决定下一个节点：continue（重试）| escalate（上报）| end（终止）
"""

from datetime import datetime, timezone

MAX_RETRIES = 3  # 最大重试次数（超过后强制 escalate）


def decide_retry(state: dict) -> dict:
    """
    Retry Decider 节点。

    Args:
        state: 当前 BiomniGraphState

    Returns:
        dict，包含 status 更新和 research_log
    """
    error = state.get("error")
    if not error:
        return {"status": "ok", "research_log": []}

    retryable = error.get("retryable", False)
    retry_count = state.get("_retry_count", 0)

    if not retryable:
        decision = "escalate"
        reason = f"错误 {error.get('code')} 不可重试，转为人工处理"
    elif retry_count >= MAX_RETRIES:
        decision = "escalate"
        reason = f"已重试 {retry_count} 次，超过最大重试次数 {MAX_RETRIES}，转为人工处理"
    else:
        decision = "retry"
        reason = (
            f"错误 {error.get('code')} 可重试（第 {retry_count + 1} 次 / 最多 {MAX_RETRIES} 次）。"
            f"建议：{error.get('plan_correction_hint', '请参考错误信息调整参数重试')}"
        )

    log_entry = {
        "t":       _now_iso(),
        "stage":   "retry_decider",
        "message": f"[RetryDecider] decision={decision}，reason={reason}",
    }

    updates: dict = {
        "status":       "retrying" if decision == "retry" else "error",
        "research_log": [log_entry],
    }

    if decision == "retry":
        updates["_retry_count"] = retry_count + 1

    return updates


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
