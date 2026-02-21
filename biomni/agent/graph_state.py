# biomni/agent/graph_state.py  v2.4
"""
BiomniGraphState — 全局 Agent 状态定义。

设计原则（v2.3-v2.4 稳定版）：
- 所有字段的 Reducer 仅在此处定义，Skill 实现层不允许重定义（红线三）
- 禁止出现 append 后需要清空的临时字段（红线五）
- messages 使用 add_messages reducer，支持 RemoveMessage 删除（Fix-J）
- 大对象禁止写入 _persistent_namespace，只存路径（红线一）
"""

import operator
from typing import Annotated, Any, Optional

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class BiomniGraphState(dict):
    """
    Biomni Agent 全局状态（TypedDict-compatible dict）。

    字段说明：
      messages            : LangGraph 消息列表，使用 add_messages reducer
                            支持 RemoveMessage 用于 Fix-J 精准修剪
      research_log        : 审计日志（追加合并），每个节点追加，永不清空
      artifacts           : 产物引用列表（文件路径、图表路径等），追加合并
      provenance          : 溯源记录列表，追加合并
      status              : 当前执行状态（"ok" | "error" | "retrying"）
      error               : 最近一次错误的 Envelope error 对象（可覆盖）
      _persistent_namespace: 运行时 Python REPL 命名空间（只存基础类型，禁止大对象）
      namespace_delta     : 最新一次工具执行对 namespace 的变化（可覆盖）
      conversation_summary: Fix-J 升级路径——旧历史的 LLM 压缩摘要（可选）
    """

    # ── messages：支持 add_messages（追加）和 RemoveMessage（删除）────────────
    messages: Annotated[list[AnyMessage], add_messages]

    # ── 审计日志：只追加，永不覆盖 ────────────────────────────────────────────
    research_log: Annotated[list[dict], operator.add]
    artifacts:    Annotated[list[dict], operator.add]
    provenance:   Annotated[list[dict], operator.add]

    # ── 可覆盖字段：最新状态 ──────────────────────────────────────────────────
    status:    str             # "ok" | "error" | "retrying"
    error:     Optional[dict]  # Envelope error 对象

    # ── Python REPL 命名空间（红线一：只允许基础类型，禁止 AnnData/Tensor）────
    _persistent_namespace: dict[str, Any]
    namespace_delta:       Optional[dict]

    # ── Fix-J 升级路径（可选）────────────────────────────────────────────────
    conversation_summary: Optional[str]


def make_initial_state() -> dict:
    """
    创建初始 Agent State，所有字段初始化为安全默认值。
    在 LangGraph 图创建时调用。
    """
    return {
        "messages":             [],
        "research_log":         [],
        "artifacts":            [],
        "provenance":           [],
        "status":               "ok",
        "error":                None,
        "_persistent_namespace": {},
        "namespace_delta":      None,
        "conversation_summary": None,
    }
