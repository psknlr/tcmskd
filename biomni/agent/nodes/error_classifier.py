# biomni/agent/nodes/error_classifier.py  v2.4
"""
Error Classifier 节点——对工具执行错误进行分级和分类。

职责：
  - 解析 Envelope 中的 error 对象
  - 基于 error_code 确定错误类别和处理策略
  - 为 RetryDecider 节点提供决策依据
"""

from datetime import datetime, timezone

# ── 错误码到类别的映射 ──────────────────────────────────────────────────────────
ERROR_CATEGORIES = {
    "EXECUTION_CRASH":    {"category": "BUG",      "severity": "high",   "retryable": False},
    "EXECUTION_OOM":      {"category": "RESOURCE",  "severity": "medium", "retryable": True},
    "EXECUTION_TIMEOUT":  {"category": "RESOURCE",  "severity": "medium", "retryable": True},
    "TOOL_NOT_FOUND":     {"category": "CONFIG",    "severity": "high",   "retryable": False},
    "INVALID_ARGS":       {"category": "INPUT",     "severity": "low",    "retryable": True},
    "PERMISSION_DENIED":  {"category": "AUTH",      "severity": "high",   "retryable": False},
    "NETWORK_ERROR":      {"category": "TRANSIENT", "severity": "low",    "retryable": True},
    "DATA_NOT_FOUND":     {"category": "DATA",      "severity": "medium", "retryable": False},
    "SCHEMA_VIOLATION":   {"category": "CONTRACT",  "severity": "high",   "retryable": False},
    "UNKNOWN":            {"category": "UNKNOWN",   "severity": "high",   "retryable": False},
}


def classify_error(state: dict) -> dict:
    """
    Error Classifier 节点。

    从 state.error 读取错误对象，补充分类信息。

    Args:
        state: 当前 BiomniGraphState

    Returns:
        dict，包含更新后的 error 字段和 research_log
    """
    error = state.get("error")
    if not error:
        return {}

    error_code = error.get("code", "UNKNOWN")
    classification = ERROR_CATEGORIES.get(error_code, ERROR_CATEGORIES["UNKNOWN"])

    enriched_error = {
        **error,
        "category":  classification["category"],
        "severity":  classification["severity"],
        "retryable": error.get("retryable", classification["retryable"]),
        "classified_at": _now_iso(),
    }

    log_entry = {
        "t":       _now_iso(),
        "stage":   "error_classifier",
        "message": (
            f"[ErrorClassifier] code={error_code}，"
            f"category={classification['category']}，"
            f"severity={classification['severity']}，"
            f"retryable={enriched_error['retryable']}"
        ),
    }

    return {
        "error":        enriched_error,
        "research_log": [log_entry],
    }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
