# biomni/agent/nodes/configure_node.py  v2.4
"""
Configure 节点 v2.4。

职责：
  1. 每轮执行开始时的初始化和配置检查
  2. 工具检索（Tool Retriever）——根据当前任务动态选择工具
  3. Fix-J：Message History 修剪——防止 Context Window 膨胀
  4. 商业模式过滤——检查工具许可证

时机选择：configure 节点是每轮图执行的起点，在 LLM 调用之前执行。
这确保每次 LLM 调用时 messages 处于合理长度（Fix-J 的核心时机）。
"""

from datetime import datetime, timezone

from biomni.utils.message_trimmer import build_remove_messages, should_trim, trim_stats


def configure_node(state: dict, config: dict | None = None) -> dict:
    """
    Configure 节点 v2.4：每轮执行的配置和初始化。

    新增 Fix-J Message History 修剪逻辑：
      - 每轮执行，成本极低（纯 Python 操作）
      - 检查 messages 总字符数和轮次数
      - 超过阈值时触发 RemoveMessage 精准修剪
      - 保证 AIMessage + ToolMessage 配对完整性

    Args:
        state:  当前 BiomniGraphState
        config: LangGraph 运行时配置（可选）

    Returns:
        dict，包含需要更新的 State 字段
    """
    updates: dict = {}
    config = config or {}

    # 从 config 读取修剪参数（支持运行时覆盖）
    keep_rounds       = config.get("keep_rounds", 10)
    keep_first_human  = config.get("keep_first_n_human", 1)

    # ── Fix-J：Message History 修剪（每轮执行，成本极低）────────────────────
    messages = state.get("messages", [])
    stats = trim_stats(messages)

    if should_trim(messages):
        remove_msgs = build_remove_messages(
            messages=messages,
            keep_rounds=keep_rounds,
            keep_first_n_human=keep_first_human,
        )
        if remove_msgs:
            updates["messages"] = remove_msgs   # add_messages reducer 执行删除
            updates["research_log"] = [{
                "t":       _now_iso(),
                "stage":   "configure",
                "message": (
                    f"[MessageTrimmer] 触发历史修剪，"
                    f"修剪前：{stats['total_messages']} 条消息 / "
                    f"约 {stats['estimated_tokens']} Token，"
                    f"删除 {len(remove_msgs)} 条消息，"
                    f"保留最近 {keep_rounds} 轮"
                ),
            }]
        else:
            # 消息量超阈值但无可删轮次（可能全是 HumanMessage 或早期消息）
            updates["research_log"] = [{
                "t":       _now_iso(),
                "stage":   "configure",
                "message": (
                    f"[MessageTrimmer] 消息量超阈值（{stats['estimated_tokens']} Token），"
                    f"但无可删轮次（可能任务尚早，保护 HumanMessage 生效）。"
                    f"当前消息数：{stats['total_messages']}"
                ),
            }]
    else:
        updates["research_log"] = [{
            "t":       _now_iso(),
            "stage":   "configure",
            "message": (
                f"[Configure] 消息历史正常（{stats['total_messages']} 条 / "
                f"约 {stats['estimated_tokens']} Token），无需修剪"
            ),
        }]

    return updates


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
