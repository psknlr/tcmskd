# skills/skill_router.py  v2.4
"""
Skill Router——将 LLM tool_call 路由到对应 Skill 执行。

职责：
  - 接收 LangGraph execute_node 的调用请求
  - 在 SkillRegistry 中查找对应 Skill
  - 调用 Skill runner（skill.py 中的 run 函数）
  - 返回 Envelope 格式结果

这是 execute_node.py 中 skill_runner 参数的默认实现。
"""

from skills.skill_registry import SkillRegistry


class SkillRouter:
    """
    Skill 路由器——LangGraph execute_node 的 skill_runner 实现。

    使用方式：
        router = SkillRouter(registry)
        result = router(skill_name, skill_args)  # 返回 Envelope dict

    支持传入 execute_node.execute_skill 作为 skill_runner 参数。
    """

    def __init__(self, registry: SkillRegistry):
        self.registry = registry

    def __call__(self, skill_name: str, skill_args: dict) -> dict:
        """
        路由并执行 Skill。

        Args:
            skill_name: Skill 名称（命名空间格式）
            skill_args: 调用参数

        Returns:
            Envelope 格式字典（符合 envelope_v2.4.json schema）

        Raises:
            可能被 execute_node.execute_skill 的 try/except 捕获（Fix-I）
        """
        runner = self.registry.get_runner(skill_name)

        if runner is None:
            # Skill 不存在或已禁用
            skill = self.registry.get(skill_name)
            if skill is not None and not skill.enabled:
                return _make_disabled_envelope(skill_name)
            return _make_not_found_envelope(skill_name, self.registry)

        # 调用 Skill runner（skill.py 中的 run 函数）
        # 注意：此处不捕获异常，异常由 execute_node.execute_skill 的 Fix-I 层捕获
        result = runner(skill_args)

        # 验证返回格式
        if not isinstance(result, dict) or "outputs" not in result:
            return _make_invalid_output_envelope(skill_name, result)

        return result


def _make_not_found_envelope(skill_name: str, registry: SkillRegistry) -> dict:
    """Skill 不存在时的错误 Envelope。"""
    available = [s.name for s in registry.list_all(enabled_only=True)][:10]
    return {
        "outputs": {
            "status": "error",
            "summary_for_llm": {
                "result_brief": None,
                "structured_data": None,
                "artifact_refs": [],
                "next_step_hint": f"可用的 Skill 包括：{', '.join(available)}",
                "error_brief": (
                    f"Skill '{skill_name}' 未找到。"
                    f"请检查 Skill 名称是否正确，或查看可用 Skill 列表。"
                ),
            },
            "full_log": {
                "research_log": [],
                "artifacts": [],
                "provenance": [],
            },
            "error": {
                "code":                "TOOL_NOT_FOUND",
                "message":             f"Skill '{skill_name}' 未在注册中心找到",
                "retryable":           False,
                "mitigation":          f"请使用正确的 Skill 名称，可用列表：{available}",
                "fallback_action":     "human_review",
                "plan_correction_hint": f"Skill '{skill_name}' 不存在，请从可用列表中选择：{available}",
            },
        }
    }


def _make_disabled_envelope(skill_name: str) -> dict:
    """Skill 已禁用时的错误 Envelope。"""
    return {
        "outputs": {
            "status": "error",
            "summary_for_llm": {
                "result_brief": None,
                "structured_data": None,
                "artifact_refs": [],
                "next_step_hint": "请联系管理员启用此 Skill，或使用替代 Skill",
                "error_brief": f"Skill '{skill_name}' 当前已禁用，无法执行。",
            },
            "full_log": {
                "research_log": [],
                "artifacts": [],
                "provenance": [],
            },
            "error": {
                "code":                "PERMISSION_DENIED",
                "message":             f"Skill '{skill_name}' 已被禁用",
                "retryable":           False,
                "mitigation":          "请联系管理员启用此 Skill",
                "fallback_action":     "human_review",
                "plan_correction_hint": f"Skill '{skill_name}' 已禁用，请尝试其他替代方案",
            },
        }
    }


def _make_invalid_output_envelope(skill_name: str, actual_output) -> dict:
    """Skill 返回非 Envelope 格式时的错误 Envelope。"""
    return {
        "outputs": {
            "status": "error",
            "summary_for_llm": {
                "result_brief": None,
                "structured_data": None,
                "artifact_refs": [],
                "next_step_hint": "Skill 实现存在 Bug，请联系开发者修复",
                "error_brief": (
                    f"Skill '{skill_name}' 返回了非法格式（缺少 'outputs' 字段）。"
                    "这是 Skill 实现的 Bug。"
                ),
            },
            "full_log": {
                "research_log": [],
                "artifacts": [],
                "provenance": [],
            },
            "error": {
                "code":                "SCHEMA_VIOLATION",
                "message":             f"Skill '{skill_name}' 返回非 Envelope 格式",
                "retryable":           False,
                "mitigation":          "Skill 实现需修复，确保返回含 'outputs' 字段的字典",
                "fallback_action":     "human_review",
                "plan_correction_hint": "此 Skill 存在实现 Bug，请跳过并使用替代方案",
            },
        }
    }
