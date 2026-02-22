# biomni/utils/message_trimmer.py  v2.4
"""
Message History 精准修剪工具（Fix-J）。

设计原则：
1. 以"轮次（Round）"为基本删除单元，一轮 = 1个AIMessage + 其所有对应ToolMessage
2. 删除时保证配对完整性，绝不出现孤立的 AIMessage 或 ToolMessage
3. 始终保留第一条 HumanMessage（任务原始指令），防止 LLM 丢失任务背景
4. 使用 RemoveMessage(id=...) 官方 API，通过 add_messages reducer 执行删除

关键约束（v2.4 规范第二章 2.2）：
  删除消息时，必须同时删除 AIMessage 和其所有对应的 ToolMessage，
  不能只删其中一类。
"""

from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    HumanMessage,
    RemoveMessage,
    ToolMessage,
)

# ── 配置常量（可通过环境变量覆盖）────────────────────────────────────────────
DEFAULT_MAX_ROUNDS = 10           # 保留最近 N 轮（1轮 = 1个AIMessage + 对应ToolMessage）
DEFAULT_MAX_TOTAL_CHARS = 40_000  # 总字符数软上限（超过时触发修剪）
DEFAULT_KEEP_FIRST_N_HUMAN = 1    # 始终保留前 N 条 HumanMessage


def should_trim(
    messages: list[AnyMessage],
    max_total_chars: int = DEFAULT_MAX_TOTAL_CHARS,
    max_rounds: int = DEFAULT_MAX_ROUNDS,
) -> bool:
    """
    判断是否需要触发修剪。
    基于两个维度：消息总字符数 OR AI消息数（轮次代理）。
    """
    total_chars = sum(
        len(m.content) if isinstance(m.content, str) else 0
        for m in messages
    )
    ai_message_count = sum(1 for m in messages if isinstance(m, AIMessage))
    return total_chars > max_total_chars or ai_message_count > max_rounds * 2


def build_remove_messages(
    messages: list[AnyMessage],
    keep_rounds: int = DEFAULT_MAX_ROUNDS,
    keep_first_n_human: int = DEFAULT_KEEP_FIRST_N_HUMAN,
) -> list[RemoveMessage]:
    """
    构建 RemoveMessage 列表，删除旧轮次，保留最近 keep_rounds 轮。

    算法：
    1. 识别所有"轮次"：每个带 tool_calls 的 AIMessage 及其后续配对 ToolMessage 构成一轮
    2. 确定需要保留的轮次（最近 keep_rounds 轮）
    3. 需要删除的轮次：返回其所有消息（AIMessage + 所有配对 ToolMessage）的 RemoveMessage
    4. 始终保留前 keep_first_n_human 条 HumanMessage（任务原始指令）

    Args:
        messages:            当前 messages 列表（完整历史）
        keep_rounds:         保留的最近轮次数
        keep_first_n_human:  始终保留的 HumanMessage 数量

    Returns:
        RemoveMessage 列表，直接作为 {"messages": remove_list} 返回给 LangGraph
    """
    # ── 1. 识别所有轮次 ────────────────────────────────────────────────────────
    rounds: list[list[AnyMessage]] = []   # 每个元素是一轮的所有消息
    i = 0
    while i < len(messages):
        msg = messages[i]
        if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
            # 收集这一轮：AIMessage + 所有对应的 ToolMessage
            tool_call_ids = {tc["id"] for tc in msg.tool_calls}
            round_messages: list[AnyMessage] = [msg]
            i += 1
            while i < len(messages) and isinstance(messages[i], ToolMessage):
                if messages[i].tool_call_id in tool_call_ids:
                    round_messages.append(messages[i])
                    tool_call_ids.discard(messages[i].tool_call_id)
                i += 1
            rounds.append(round_messages)
        else:
            i += 1

    # ── 2. 确定需要删除的轮次（超出 keep_rounds 的旧轮次）────────────────────
    rounds_to_delete = rounds[:-keep_rounds] if len(rounds) > keep_rounds else []
    if not rounds_to_delete:
        return []   # 无需修剪

    # ── 3. 收集要删除的消息 ID ────────────────────────────────────────────────
    ids_to_delete: set[str] = set()
    for round_msgs in rounds_to_delete:
        for m in round_msgs:
            if m.id:
                ids_to_delete.add(m.id)

    # ── 4. 保护前 N 条 HumanMessage（任务原始指令不可删） ─────────────────────
    human_count = 0
    protected_ids: set[str] = set()
    for m in messages:
        if isinstance(m, HumanMessage):
            human_count += 1
            if human_count <= keep_first_n_human and m.id:
                protected_ids.add(m.id)

    ids_to_delete -= protected_ids

    # ── 5. 生成 RemoveMessage 列表 ────────────────────────────────────────────
    return [RemoveMessage(id=msg_id) for msg_id in ids_to_delete]


def trim_stats(messages: list[AnyMessage]) -> dict:
    """
    返回当前 messages 的统计信息，供 configure 节点决策和日志记录。
    """
    total_chars = sum(
        len(m.content) if isinstance(m.content, str) else 0
        for m in messages
    )
    return {
        "total_messages":    len(messages),
        "total_chars":       total_chars,
        "estimated_tokens":  total_chars // 4,  # 粗估（英文约4字符/token，中文约2字符/token）
        "ai_message_count":   sum(1 for m in messages if isinstance(m, AIMessage)),
        "tool_message_count": sum(1 for m in messages if isinstance(m, ToolMessage)),
        "human_message_count":sum(1 for m in messages if isinstance(m, HumanMessage)),
    }
