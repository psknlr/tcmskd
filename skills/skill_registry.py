# skills/skill_registry.py  v2.4
"""
Skill Registry——技能注册中心。

职责：
  - 维护所有已加载 Skill 的索引
  - 提供按名称、类别、标签查询 Skill 的接口
  - 支持热注册（运行时添加新 Skill）
  - 支持 Skill 卸载（热更新时移除旧版本）

命名规范：Skill 名称采用命名空间格式，例如：
  "tcm.database.herb_query"
  "tcm.analysis.network_analysis"
  "tcm.visualization.herb_network_plot"
"""

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable


@dataclass
class SkillMeta:
    """Skill 元数据——描述一个技能的所有信息。"""

    name: str                   # 命名空间格式，如 "tcm.database.herb_query"
    category: str               # 类别，如 "database" | "analysis" | "visualization"
    description: str            # 简短描述（LLM 用于路由决策）
    when_to_use: str            # 何时调用（详细说明，来自 skill.md）
    input_schema: dict          # 输入参数 Schema（JSON Schema 格式）
    output_schema: dict         # 输出格式说明
    tags: list[str]             # 标签列表（用于语义检索）
    version: str                # Skill 版本
    author: str                 # 作者
    requires: list[str]         # 依赖的其他 Skill 名称
    skill_dir: str              # Skill 文件夹路径
    runner: Callable | None = None  # 实际执行函数（Python 实现）
    loaded_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    enabled: bool = True


class SkillRegistry:
    """
    Skill 注册中心。

    线程安全设计：所有写操作使用 RLock 保护。
    """

    def __init__(self):
        self._skills: dict[str, SkillMeta] = {}
        self._lock = threading.RLock()

    # ── 注册 / 注销 ─────────────────────────────────────────────────────────────

    def register(self, skill: SkillMeta) -> None:
        """注册一个 Skill（热注册，运行时可调用）。"""
        with self._lock:
            if skill.name in self._skills:
                old_version = self._skills[skill.name].version
                print(
                    f"[SkillRegistry] 覆盖已存在的 Skill：{skill.name} "
                    f"（{old_version} → {skill.version}）"
                )
            self._skills[skill.name] = skill
            print(f"[SkillRegistry] 注册 Skill：{skill.name} v{skill.version}")

    def unregister(self, name: str) -> bool:
        """注销一个 Skill（热卸载）。"""
        with self._lock:
            if name in self._skills:
                del self._skills[name]
                print(f"[SkillRegistry] 注销 Skill：{name}")
                return True
            return False

    def enable(self, name: str) -> bool:
        """启用一个已注册但被禁用的 Skill。"""
        with self._lock:
            if name in self._skills:
                self._skills[name].enabled = True
                return True
            return False

    def disable(self, name: str) -> bool:
        """禁用一个 Skill（不删除，只是不可路由）。"""
        with self._lock:
            if name in self._skills:
                self._skills[name].enabled = False
                return True
            return False

    # ── 查询 ────────────────────────────────────────────────────────────────────

    def get(self, name: str) -> SkillMeta | None:
        """按名称获取 Skill 元数据。"""
        with self._lock:
            return self._skills.get(name)

    def get_runner(self, name: str) -> Callable | None:
        """获取 Skill 的执行函数。"""
        with self._lock:
            skill = self._skills.get(name)
            return skill.runner if skill and skill.enabled else None

    def list_all(self, enabled_only: bool = True) -> list[SkillMeta]:
        """列出所有已注册 Skill。"""
        with self._lock:
            skills = list(self._skills.values())
            if enabled_only:
                skills = [s for s in skills if s.enabled]
            return skills

    def list_by_category(self, category: str) -> list[SkillMeta]:
        """按类别过滤 Skill。"""
        with self._lock:
            return [s for s in self._skills.values() if s.category == category and s.enabled]

    def list_by_tag(self, tag: str) -> list[SkillMeta]:
        """按标签过滤 Skill。"""
        with self._lock:
            return [s for s in self._skills.values() if tag in s.tags and s.enabled]

    def search(self, query: str) -> list[SkillMeta]:
        """
        简单关键词搜索（name / description / tags / when_to_use）。
        生产环境建议替换为向量检索。
        """
        query_lower = query.lower()
        with self._lock:
            results = []
            for skill in self._skills.values():
                if not skill.enabled:
                    continue
                # 关键词匹配
                searchable = " ".join([
                    skill.name,
                    skill.description,
                    skill.when_to_use,
                    " ".join(skill.tags),
                ])
                if query_lower in searchable.lower():
                    results.append(skill)
            return results

    def to_tool_descriptions(self, enabled_only: bool = True) -> str:
        """
        将所有 Skill 转换为 LLM 工具描述字符串。
        格式与 biomni 现有 textify_api_dict 输出兼容。
        """
        skills = self.list_all(enabled_only=enabled_only)
        lines = []
        for s in skills:
            lines.append(f"## {s.name}")
            lines.append(f"**描述**: {s.description}")
            lines.append(f"**使用时机**: {s.when_to_use}")
            if s.tags:
                lines.append(f"**标签**: {', '.join(s.tags)}")
            lines.append(f"**版本**: {s.version}")
            lines.append("")
        return "\n".join(lines)

    def stats(self) -> dict:
        """返回注册中心统计信息。"""
        with self._lock:
            all_skills = list(self._skills.values())
            return {
                "total":    len(all_skills),
                "enabled":  sum(1 for s in all_skills if s.enabled),
                "disabled": sum(1 for s in all_skills if not s.enabled),
                "categories": list({s.category for s in all_skills}),
            }

    def __len__(self) -> int:
        with self._lock:
            return len(self._skills)

    def __contains__(self, name: str) -> bool:
        with self._lock:
            return name in self._skills

    def __repr__(self) -> str:
        stats = self.stats()
        return (
            f"<SkillRegistry total={stats['total']} "
            f"enabled={stats['enabled']} "
            f"categories={stats['categories']}>"
        )


# ── 全局单例注册中心（在进程内共享）──────────────────────────────────────────────
_global_registry: SkillRegistry | None = None


def get_global_registry() -> SkillRegistry:
    """获取全局 Skill 注册中心单例。"""
    global _global_registry
    if _global_registry is None:
        _global_registry = SkillRegistry()
    return _global_registry
