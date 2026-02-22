# biomni/utils/tool_message_formatter.py  v2.3+
"""
Skill 输出格式化工具（Fix-F + Fix-H）。

职责：
  1. 将 Skill 返回的 Envelope dict 序列化为字符串（Fix-F：json.dumps 只在此处执行一次）
  2. 将最终字符串硬截断到 MAX_CONTENT_CHARS 字符（Fix-H：物理硬截断）
  3. 确保 ToolMessage.content 始终是字符串（LangChain 要求）

红线四：ToolMessage.content 必须是字符串，序列化只在此函数执行一次。
        Skill 实现层不做任何序列化。
"""

import json

# ── 配置常量（Fix-H 硬截断阈值）────────────────────────────────────────────────
MAX_CONTENT_CHARS = 10_000  # 约 2,500 Token（英文 4 字符/token）
TRUNCATION_NOTICE = "\n\n... [内容已截断，超出 {limit} 字符限制。完整内容请通过 artifacts 引用获取] ..."


def format_skill_output_to_string(envelope: dict) -> str:
    """
    将 Skill Envelope 转换为 ToolMessage.content 字符串。

    处理流程：
      1. 提取 summary_for_llm（LLM 消费的精简视图）
      2. json.dumps 序列化（Fix-F：唯一序列化点）
      3. 物理硬截断（Fix-H：MAX_CONTENT_CHARS）

    Args:
        envelope: Skill 返回的完整 Envelope 字典

    Returns:
        字符串，长度 <= MAX_CONTENT_CHARS
    """
    if not isinstance(envelope, dict):
        # 防御性处理：非预期类型
        raw = str(envelope)
        return _truncate(raw)

    outputs = envelope.get("outputs", {})

    # ── 优先使用 summary_for_llm（LLM 消费视图） ────────────────────────────
    summary = outputs.get("summary_for_llm")
    if summary is not None:
        payload = _build_payload_from_summary(summary, outputs)
    else:
        # 降级：无 summary_for_llm 时使用完整 outputs（去除 full_log 减小体积）
        payload = {k: v for k, v in outputs.items() if k != "full_log"}

    # ── Fix-F：唯一序列化点 ───────────────────────────────────────────────────
    try:
        content_str = json.dumps(payload, ensure_ascii=False, default=_json_fallback)
    except (TypeError, ValueError):
        # 序列化失败时降级为 str()
        content_str = str(payload)

    # ── Fix-H：物理硬截断 ─────────────────────────────────────────────────────
    return _truncate(content_str)


def _build_payload_from_summary(summary: dict, outputs: dict) -> dict:
    """
    从 summary_for_llm 构建传给 LLM 的精简 payload。

    结构：
      {
        "status":         "ok" | "error",
        "result_brief":   str | None,
        "structured_data": dict | list | None,
        "artifact_refs":  list,
        "next_step_hint": str | None,
        "error_brief":    str | None  (仅 status=error 时存在)
      }
    """
    payload: dict = {
        "status":         outputs.get("status", "ok"),
        "result_brief":   summary.get("result_brief"),
        "structured_data": summary.get("structured_data"),
        "artifact_refs":  summary.get("artifact_refs", []),
        "next_step_hint": summary.get("next_step_hint"),
    }

    # 错误信息
    error_brief = summary.get("error_brief")
    if error_brief:
        payload["error_brief"] = error_brief

    # 顶层 error 对象（含 retryable / mitigation）
    top_error = outputs.get("error")
    if top_error:
        payload["error"] = top_error

    # 清理 None 值减小体积（保留 False / 0 / [] 等有意义的空值）
    payload = {k: v for k, v in payload.items() if v is not None}

    return payload


def _truncate(content: str) -> str:
    """物理硬截断（Fix-H）：确保 content 不超过 MAX_CONTENT_CHARS 字符。"""
    if len(content) <= MAX_CONTENT_CHARS:
        return content
    notice = TRUNCATION_NOTICE.format(limit=MAX_CONTENT_CHARS)
    cut_at = MAX_CONTENT_CHARS - len(notice)
    return content[:cut_at] + notice


def _json_fallback(obj):
    """json.dumps 的 default 处理器：将不可序列化对象转为字符串。"""
    try:
        return repr(obj)
    except Exception:
        return "<unserializable>"
