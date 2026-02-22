# biomni/agent/nodes/execute_node.py  v2.4
"""
Execute 节点 v2.4。

核心变化（Fix-I）：
  - 在 run_skill 调用外层包裹 try/except Exception 全兜底
  - 捕获所有底层异常，转换为合法 Envelope 格式，确保 LangGraph 线程不崩溃
  - LLM 始终能收到对应 tool_call_id 的 ToolMessage（即使内容是错误信息）

红线六（v2.4）：run_skill 调用必须被 try/except Exception 包裹，
              底层异常必须转换为合法 Envelope，不允许裸露异常传播到 LangGraph 框架层。

异常分级处理策略：
  MemoryError   → EXECUTION_OOM      retryable=True
  TimeoutError  → EXECUTION_TIMEOUT  retryable=True
  Exception     → EXECUTION_CRASH    retryable=False
  SystemExit/KeyboardInterrupt → 不拦截，让其正常传播
"""

import traceback
from datetime import datetime, timezone

from langchain_core.messages import ToolMessage

from biomni.utils.tool_message_formatter import format_skill_output_to_string


def execute_skill(
    state: dict,
    tool_call: dict,
    skill_name: str,
    skill_args: dict,
    skill_runner,
) -> dict:
    """
    执行 Skill 并将结果封装为 ToolMessage 写入 messages。

    Fix-I：全异常防护层。
    run_skill 内部的任何 Exception（包括 MemoryError、OSError、ZeroDivisionError
    等底层异常）都必须在此处被拦截，转换为合法 Envelope，避免 LangGraph thread crash。

    不拦截 SystemExit / KeyboardInterrupt，这些是进程级信号，应让其正常传播。

    Args:
        state:        当前 BiomniGraphState
        tool_call:    LLM 发出的 tool_call 字典（含 id, name, args）
        skill_name:   Skill 名称（命名空间格式，如 "tcm.database.herb_query"）
        skill_args:   Skill 调用参数
        skill_runner: 可调用对象，接受 (skill_name, skill_args) 并返回 Envelope dict

    Returns:
        dict，包含 messages（ToolMessage）以及审计字段
    """
    tool_call_id = tool_call["id"]

    # ── Fix-I：全异常拦截（最外层，覆盖所有 Exception 子类）────────────────────
    try:
        skill_output = skill_runner(skill_name, skill_args)

    except MemoryError as e:
        # MemoryError 单独处理：可能是数据太大，建议减少输入规模重试
        skill_output = _make_crash_envelope(
            skill_name=skill_name,
            error_code="EXECUTION_OOM",
            exception=e,
            traceback_str=traceback.format_exc(),
            retryable=True,
            plan_correction_hint=(
                f"工具 {skill_name} 执行时内存溢出（MemoryError）。"
                "建议：减少输入数据规模（如降低 limit 参数或拆分批次）后重试。"
            ),
        )

    except TimeoutError as e:
        # TimeoutError：通常可重试，或建议拆分任务
        skill_output = _make_crash_envelope(
            skill_name=skill_name,
            error_code="EXECUTION_TIMEOUT",
            exception=e,
            traceback_str=traceback.format_exc(),
            retryable=True,
            plan_correction_hint=(
                f"工具 {skill_name} 执行超时。"
                "建议：减少输入数据规模或拆分为多个子任务后重试。"
            ),
        )

    except Exception as e:
        # 兜底：拦截所有其他 Exception 子类
        # 注意：MemoryError / TimeoutError 已在上面单独处理，此处为真正的兜底
        skill_output = _make_crash_envelope(
            skill_name=skill_name,
            error_code="EXECUTION_CRASH",
            exception=e,
            traceback_str=traceback.format_exc(),
            retryable=False,
            plan_correction_hint=(
                f"工具 {skill_name} 在执行时崩溃（{type(e).__name__}: {e}）。"
                "这通常是工具代码的 Bug，建议跳过此工具并尝试替代方案，"
                "或报告给工程团队修复后再使用。"
            ),
        )

    # ── 序列化（Fix-F + Fix-H：json.dumps + 硬截断） ─────────────────────────
    content_str = format_skill_output_to_string(skill_output)

    tm = ToolMessage(
        content=content_str,
        tool_call_id=tool_call_id,
        name=skill_name,
    )

    # ── 提取审计数据 ──────────────────────────────────────────────────────────
    full_log  = skill_output.get("outputs", {}).get("full_log", {})
    new_logs  = list(full_log.get("research_log", []))
    new_arts  = list(full_log.get("artifacts", []))
    new_prov  = list(full_log.get("provenance", []))
    ns_delta  = full_log.get("namespace_delta")
    status    = skill_output.get("outputs", {}).get("status", "ok")
    error     = skill_output.get("outputs", {}).get("error")

    new_logs.append({
        "t":       _now_iso(),
        "stage":   "tool_message_formatted",
        "message": (
            f"[{skill_name}] ToolMessage 生成完毕，"
            f"tool_call_id={tool_call_id}，"
            f"content_len={len(content_str)}，"
            f"truncated={len(content_str) >= 10_000}，"
            f"status={status}"
        ),
    })

    # ── 返回（所有字段由 BiomniGraphState Reducer 安全合并）──────────────────
    result: dict = {
        "messages":     [tm],
        "research_log": new_logs,
        "artifacts":    new_arts,
        "provenance":   new_prov,
        "status":       status,
    }
    if ns_delta:
        result["namespace_delta"] = ns_delta
    if error:
        result["error"] = error

    return result


# ─── 辅助函数 ──────────────────────────────────────────────────────────────────

def _make_crash_envelope(
    skill_name: str,
    error_code: str,
    exception: Exception,
    traceback_str: str,
    retryable: bool,
    plan_correction_hint: str,
) -> dict:
    """
    将原生异常转换为合法的 Envelope 格式字典。

    Fix-I 核心：无论 run_skill 内部发生什么，外层调用者总能拿到一个
    符合 Envelope Schema 的字典，而不是一个裸露的 Python Exception。
    这保证了后续的 format_skill_output_to_string 和 ToolMessage 生成能正常执行。
    """
    short_msg = f"{type(exception).__name__}: {str(exception)}"
    # traceback 太长不写入 summary_for_llm，只写入 full_log.research_log
    return {
        "outputs": {
            "status": "error",
            "summary_for_llm": {
                "result_brief": None,
                "structured_data": None,
                "artifact_refs": [],
                "next_step_hint": None,
                "error_brief": (
                    f"工具 {skill_name} 执行崩溃（{error_code}）：{short_msg}。"
                    f"{plan_correction_hint}"
                ),
            },
            "full_log": {
                "research_log": [{
                    "t":       _now_iso(),
                    "stage":   "warn",
                    "message": (
                        f"[{skill_name}] EXECUTION_CRASH 捕获，"
                        f"error_code={error_code}，"
                        f"exception={short_msg}，"
                        f"traceback（前 2000 字符）={traceback_str[:2000]}"
                    ),
                }],
                "artifacts": [],
                "provenance": [],
            },
            "error": {
                "code":                 error_code,
                "message":              short_msg,
                "retryable":            retryable,
                "mitigation":           plan_correction_hint,
                "fallback_action":      "retry_with_plan_correction" if retryable else "human_review",
                "plan_correction_hint": plan_correction_hint,
            },
        }
    }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
