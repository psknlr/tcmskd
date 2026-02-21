# biomni/utils/message_summarizer.py  v2.4
"""
历史摘要升级路径（Fix-J 方案二）。

当精准修剪（keep_rounds=10）依然不足以控制上下文时启用。
适用场景：长任务（>20轮），可接受信息有损压缩。

使用方式：
  在 configure_node.py 中，当 trim_stats["estimated_tokens"] > 30_000 时，
  替代 build_remove_messages 调用本模块的 summarize_and_trim。

关键约束：
  此操作会消耗 LLM Token（摘要本身有成本），仅在确实需要时调用。
  建议触发条件：estimated_tokens > 30_000（约 120K 上下文模型的 25%）
"""

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, RemoveMessage, SystemMessage

SUMMARY_PROMPT = """以下是你作为 AI 科研助手执行任务的历史记录摘要。
请将这段历史压缩为不超过 500 字的简洁摘要，重点保留：
1. 任务目标
2. 已完成的关键步骤和结论
3. 发现的重要数据或文件路径
4. 尚未解决的问题或待执行的步骤

历史记录：
{history}
"""

SUMMARY_MSG_ID = "history_summary_v2_4"


async def summarize_and_trim(
    messages: list[AnyMessage],
    llm,
    keep_recent_rounds: int = 3,
) -> dict:
    """
    调用 LLM 将旧历史压缩为摘要，然后用 RemoveMessage 删除旧消息。
    返回 {"messages": [SystemMessage(摘要) + RemoveMessage列表]}。

    注意：此操作会消耗 LLM Token（摘要本身有成本），仅在确实需要时调用。
    建议触发条件：estimated_tokens > 30_000（约 120K 上下文模型的 25%）

    Args:
        messages:           当前完整消息列表
        llm:                已配置的 LLM 实例（支持 ainvoke）
        keep_recent_rounds: 保留最近 N 轮不纳入摘要

    Returns:
        dict 格式：{"messages": [SystemMessage(摘要), RemoveMessage(...), ...]}
        可直接作为 LangGraph 节点的返回值
    """
    # 找出需要保留的最近 N 轮
    ai_rounds = [m for m in messages if isinstance(m, AIMessage) and getattr(m, "tool_calls", None)]
    keep_from_idx = 0
    if len(ai_rounds) > keep_recent_rounds:
        keep_round_start_msg = ai_rounds[-keep_recent_rounds]
        keep_from_idx = next(
            (i for i, m in enumerate(messages) if m.id == keep_round_start_msg.id),
            0
        )

    old_messages = messages[:keep_from_idx]
    if not old_messages:
        return {"messages": []}

    history_text = "\n".join(
        f"[{type(m).__name__}]: {m.content[:500]}"
        for m in old_messages
        if hasattr(m, "content") and isinstance(m.content, str)
    )

    # 调用 LLM 生成摘要
    summary_response = await llm.ainvoke([
        HumanMessage(content=SUMMARY_PROMPT.format(history=history_text))
    ])
    summary_text = f"【历史摘要】{summary_response.content}"

    # 用 RemoveMessage 删除旧消息，插入摘要
    remove_list = [
        RemoveMessage(id=m.id)
        for m in old_messages
        if m.id
    ]

    return {
        "messages": [
            SystemMessage(content=summary_text, id=SUMMARY_MSG_ID),
            *remove_list,
        ]
    }


def should_summarize(stats: dict, threshold_tokens: int = 30_000) -> bool:
    """
    判断是否应该触发摘要（而不仅仅是精准修剪）。

    Args:
        stats:            trim_stats() 返回的统计字典
        threshold_tokens: Token 数阈值，超过时建议摘要

    Returns:
        True 表示建议启用历史摘要
    """
    return stats.get("estimated_tokens", 0) > threshold_tokens
