# skills/skill_loader.py  v2.4
"""
Skill Loader——热加载引擎。

关键能力（二）：Skill 热加载
  新数据库接入只需添加一个 Skill 文件夹，无需改动核心代码。

文件夹结构（每个 Skill 一个目录）：
  skills/
  ├── tcm_database/
  │   ├── skill.md          # Skill 自描述文件（必须）
  │   └── skill.py          # Python 实现（必须）
  ├── tcm_analysis/
  │   ├── skill.md
  │   └── skill.py
  └── ...

skill.md 必须包含以下 YAML frontmatter：
  ---
  name: "tcm.database.herb_query"
  category: "database"
  description: "查询中药材信息"
  when_to_use: "当用户需要查询某种中药材的成分、功效、禁忌时"
  version: "1.0.0"
  author: "Biomni Team"
  tags: ["tcm", "database", "herb"]
  requires: []
  ---

skill.py 必须暴露 run(args: dict) -> dict 函数，返回 Envelope 格式。
"""

import importlib.util
import os
import sys
from pathlib import Path

import yaml

from skills.skill_registry import SkillMeta, SkillRegistry


class SkillLoader:
    """
    Skill 热加载器。

    支持：
      - 初始化时扫描所有 Skill 目录
      - 运行时新增 Skill（热加载单个目录）
      - 运行时重载已有 Skill（更新后不重启）
    """

    def __init__(self, skills_root: str | Path, registry: SkillRegistry):
        """
        Args:
            skills_root: skills/ 根目录路径
            registry:    SkillRegistry 实例
        """
        self.skills_root = Path(skills_root)
        self.registry = registry

    def load_all(self) -> int:
        """
        扫描 skills_root 下的所有 Skill 目录并加载。

        跳过：
          - 以 _ 开头的目录（如 _schemas, _templates）
          - 没有 skill.md 的目录
          - 没有 skill.py 的目录

        Returns:
            成功加载的 Skill 数量
        """
        loaded = 0
        errors = []

        for entry in sorted(self.skills_root.iterdir()):
            if not entry.is_dir():
                continue
            if entry.name.startswith("_") or entry.name.startswith("."):
                continue

            try:
                self.load_skill_dir(entry)
                loaded += 1
            except Exception as e:
                errors.append(f"{entry.name}: {e}")

        if errors:
            print(f"[SkillLoader] 加载完成，{loaded} 个成功，{len(errors)} 个失败：")
            for err in errors:
                print(f"  ✗ {err}")
        else:
            print(f"[SkillLoader] 加载完成，共 {loaded} 个 Skill")

        return loaded

    def load_skill_dir(self, skill_dir: str | Path) -> SkillMeta:
        """
        加载单个 Skill 目录。

        Args:
            skill_dir: Skill 目录路径（需包含 skill.md 和 skill.py）

        Returns:
            加载成功的 SkillMeta

        Raises:
            FileNotFoundError: skill.md 或 skill.py 不存在
            ValueError: skill.md frontmatter 格式错误
        """
        skill_dir = Path(skill_dir)
        md_path = skill_dir / "skill.md"
        py_path = skill_dir / "skill.py"

        if not md_path.exists():
            raise FileNotFoundError(f"缺少 skill.md：{md_path}")
        if not py_path.exists():
            raise FileNotFoundError(f"缺少 skill.py：{py_path}")

        # 解析 skill.md frontmatter
        meta_dict = _parse_skill_md(md_path)

        # 动态加载 skill.py
        runner = _load_skill_py(py_path, meta_dict["name"])

        skill = SkillMeta(
            name=meta_dict["name"],
            category=meta_dict.get("category", "general"),
            description=meta_dict.get("description", ""),
            when_to_use=meta_dict.get("when_to_use", ""),
            input_schema=meta_dict.get("input_schema", {}),
            output_schema=meta_dict.get("output_schema", {}),
            tags=meta_dict.get("tags", []),
            version=meta_dict.get("version", "0.0.1"),
            author=meta_dict.get("author", "unknown"),
            requires=meta_dict.get("requires", []),
            skill_dir=str(skill_dir),
            runner=runner,
            enabled=meta_dict.get("enabled", True),
        )

        self.registry.register(skill)
        return skill

    def reload_skill(self, skill_name: str) -> SkillMeta | None:
        """
        重载已注册的 Skill（代码更新后热重载）。

        Args:
            skill_name: Skill 名称

        Returns:
            重载后的 SkillMeta，或 None（Skill 不存在）
        """
        existing = self.registry.get(skill_name)
        if not existing:
            print(f"[SkillLoader] Skill {skill_name} 未注册，无法重载")
            return None

        try:
            return self.load_skill_dir(existing.skill_dir)
        except Exception as e:
            print(f"[SkillLoader] 重载 {skill_name} 失败：{e}")
            return None

    def hot_add(self, skill_dir: str | Path) -> SkillMeta | None:
        """
        热添加新 Skill（运行时添加，无需重启）。

        Args:
            skill_dir: 新 Skill 的目录路径

        Returns:
            加载的 SkillMeta，或 None（失败）
        """
        try:
            meta = self.load_skill_dir(skill_dir)
            print(f"[SkillLoader] 热加载成功：{meta.name}")
            return meta
        except Exception as e:
            print(f"[SkillLoader] 热加载失败：{e}")
            return None


# ─── 内部工具函数 ──────────────────────────────────────────────────────────────

def _parse_skill_md(md_path: Path) -> dict:
    """
    解析 skill.md，提取 YAML frontmatter 和正文。

    YAML frontmatter 格式：
      ---
      name: "tcm.database.herb_query"
      category: "database"
      ...
      ---
      正文（LLM 可读的详细说明）
    """
    content = md_path.read_text(encoding="utf-8")
    lines = content.split("\n")

    # 查找 frontmatter 边界
    if lines[0].strip() != "---":
        raise ValueError(f"skill.md 必须以 '---' 开头（YAML frontmatter）：{md_path}")

    end_idx = None
    for i, line in enumerate(lines[1:], 1):
        if line.strip() == "---":
            end_idx = i
            break

    if end_idx is None:
        raise ValueError(f"skill.md 的 YAML frontmatter 未正确关闭（缺少第二个 '---'）：{md_path}")

    frontmatter_str = "\n".join(lines[1:end_idx])
    body = "\n".join(lines[end_idx + 1:]).strip()

    try:
        meta = yaml.safe_load(frontmatter_str) or {}
    except yaml.YAMLError as e:
        raise ValueError(f"skill.md frontmatter YAML 解析失败：{e}") from e

    # 验证必须字段
    required_fields = ["name", "category", "description"]
    for f in required_fields:
        if f not in meta:
            raise ValueError(f"skill.md 缺少必须字段 '{f}'：{md_path}")

    # 将正文作为 when_to_use 的补充（如果 frontmatter 中没有 when_to_use）
    if "when_to_use" not in meta and body:
        meta["when_to_use"] = body[:500]  # 截取前 500 字符

    return meta


def _load_skill_py(py_path: Path, skill_name: str):
    """
    动态加载 skill.py，提取 run 函数作为 runner。

    skill.py 必须定义 run(args: dict) -> dict 函数，
    返回 Envelope 格式的字典。

    Args:
        py_path:    skill.py 路径
        skill_name: Skill 名称（用于模块命名）

    Returns:
        可调用的 run 函数
    """
    # 构造唯一模块名（避免名称冲突）
    module_name = f"skill_module__{skill_name.replace('.', '__')}"

    # 移除已加载的同名模块（热重载支持）
    if module_name in sys.modules:
        del sys.modules[module_name]

    spec = importlib.util.spec_from_file_location(module_name, py_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"无法创建模块 spec：{py_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module

    try:
        spec.loader.exec_module(module)
    except Exception as e:
        del sys.modules[module_name]
        raise ImportError(f"加载 skill.py 失败：{e}") from e

    if not hasattr(module, "run"):
        raise AttributeError(f"skill.py 必须定义 run(args: dict) -> dict 函数：{py_path}")

    runner = getattr(module, "run")
    if not callable(runner):
        raise TypeError(f"skill.py 中的 run 不是可调用对象：{py_path}")

    return runner
