# skills/__init__.py  v2.4
"""
Skill Router 包——每个 Skill 是独立的能力单元。

架构精髓（OpenClaw 移植）：
  每个数据库查询、分析流程、出图模板封装为独立 Skill
  （Markdown 定义 + Python 实现），Skill 之间可组合、可自我生成。

关键能力：
  (1) Skill 自描述：每个 Skill 目录包含 skill.md，让 Agent 理解何时调用哪个能力
  (2) Skill 热加载：新数据库接入只需添加一个 Skill 文件夹，无需改动核心代码
  (3) 自我进化：Agent 可根据用户反馈自动生成新 Skill 并注册
"""

from skills.skill_registry import SkillRegistry
from skills.skill_loader import SkillLoader

__all__ = ["SkillRegistry", "SkillLoader"]
