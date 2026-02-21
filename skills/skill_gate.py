# skills/skill_gate.py  v2.4
"""
CI Gate——在合并前自动验证 Skill 和 Agent 代码的合规性。

验证内容：
  Fix-I（v2.4 新增）：execute_node.py 必须包含异常拦截规范
  Fix-J（v2.4 新增）：message_trimmer.py 逻辑正确性
  所有 Skill 文件夹必须包含 skill.md 和 skill.py
  所有 Skill 的 skill.md 必须包含必须字段
  所有 Skill 的 skill.py 必须暴露 run 函数
  不允许危险代码模式

运行方式：
  python skills/skill_gate.py
"""

import re
import sys
from pathlib import Path

SKILLS_ROOT   = Path(__file__).parent
PROJECT_ROOT  = SKILLS_ROOT.parent
EXECUTE_NODE  = PROJECT_ROOT / "biomni" / "agent" / "nodes" / "execute_node.py"
MSG_TRIMMER   = PROJECT_ROOT / "biomni" / "utils" / "message_trimmer.py"

FORBIDDEN_PATTERNS = [
    r"\bos\.system\s*\(",
    r"\bsubprocess\.(run|Popen|call|check_output)\s*\(",
]

REQUIRED_SKILL_MD_FIELDS = ["name", "category", "description"]


def check_all() -> bool:
    """运行所有 CI Gate 检查，返回 True 表示全部通过。"""
    all_passed = True
    print("=" * 60)
    print("Biomni v2.4 CI Gate")
    print("=" * 60)

    checks = [
        check_execute_node_fix_i,
        check_message_trimmer_fix_j,
        check_all_skills,
    ]

    for check_fn in checks:
        passed = check_fn()
        if not passed:
            all_passed = False

    print("\n" + "=" * 60)
    if all_passed:
        print("✅ 所有 CI Gate 检查通过")
    else:
        print("❌ CI Gate 检查失败，请修复后再合并")
    print("=" * 60)

    return all_passed


def check_execute_node_fix_i() -> bool:
    """Fix-I：验证 execute_node.py 的异常拦截规范。"""
    print("\n[Fix-I] 检查 execute_node.py 异常拦截规范...")
    passed = True

    if not EXECUTE_NODE.exists():
        print(f"  ❌ 文件不存在：{EXECUTE_NODE}")
        return False

    content = EXECUTE_NODE.read_text(encoding="utf-8")

    # 必须包含 except Exception as 兜底
    if not re.search(r"except\s+Exception\s+as", content):
        print("  ❌ execute_skill 必须包含 except Exception as e: 兜底（Fix-I）")
        passed = False
    else:
        print("  ✅ 包含 except Exception as e: 兜底")

    # 不允许 bare except:
    if re.search(r"except\s*:", content):
        print("  ❌ 不允许 bare except:，应使用 except Exception as e:")
        passed = False
    else:
        print("  ✅ 无 bare except:")

    # 不允许 except BaseException
    if re.search(r"except\s+BaseException", content):
        print("  ❌ 不允许捕获 BaseException，SystemExit/KeyboardInterrupt 应正常传播")
        passed = False
    else:
        print("  ✅ 无 except BaseException")

    # 必须包含 _make_crash_envelope 函数
    if "_make_crash_envelope" not in content:
        print("  ❌ 缺少 _make_crash_envelope 函数（Fix-I 要求）")
        passed = False
    else:
        print("  ✅ 包含 _make_crash_envelope 函数")

    # 必须包含 EXECUTION_OOM 处理
    if "EXECUTION_OOM" not in content:
        print("  ❌ 缺少 EXECUTION_OOM 错误码处理（MemoryError 分级）")
        passed = False
    else:
        print("  ✅ 包含 EXECUTION_OOM 处理")

    return passed


def check_message_trimmer_fix_j() -> bool:
    """Fix-J：验证 message_trimmer.py 的关键函数存在。"""
    print("\n[Fix-J] 检查 message_trimmer.py...")
    passed = True

    if not MSG_TRIMMER.exists():
        print(f"  ❌ 文件不存在：{MSG_TRIMMER}")
        return False

    content = MSG_TRIMMER.read_text(encoding="utf-8")

    # 必须包含 build_remove_messages 函数
    if "def build_remove_messages" not in content:
        print("  ❌ 缺少 build_remove_messages 函数（Fix-J 要求）")
        passed = False
    else:
        print("  ✅ 包含 build_remove_messages 函数")

    # 必须使用 RemoveMessage
    if "RemoveMessage" not in content:
        print("  ❌ 未使用 RemoveMessage（Fix-J 官方 API）")
        passed = False
    else:
        print("  ✅ 使用 RemoveMessage")

    # 必须包含配对完整性逻辑（注释或代码中）
    if "tool_call_ids" not in content and "tool_calls" not in content:
        print("  ❌ 缺少 AIMessage + ToolMessage 配对完整性逻辑")
        passed = False
    else:
        print("  ✅ 包含配对完整性逻辑")

    # 必须包含 HumanMessage 保护逻辑
    if "HumanMessage" not in content or "keep_first" not in content:
        print("  ❌ 缺少 HumanMessage 保护逻辑（keep_first_n_human）")
        passed = False
    else:
        print("  ✅ 包含 HumanMessage 保护逻辑")

    return passed


def check_all_skills() -> bool:
    """验证所有 Skill 文件夹的规范性。"""
    print("\n[Skill] 检查所有 Skill 文件夹...")
    all_passed = True

    skill_dirs = [
        d for d in SKILLS_ROOT.iterdir()
        if d.is_dir() and not d.name.startswith("_") and not d.name.startswith(".")
        and d.name not in ("qa",)
    ]

    if not skill_dirs:
        print("  ℹ️  未发现 Skill 文件夹")
        return True

    for skill_dir in sorted(skill_dirs):
        passed = check_single_skill(skill_dir)
        if not passed:
            all_passed = False

    return all_passed


def check_single_skill(skill_dir: Path) -> bool:
    """验证单个 Skill 文件夹的规范性。"""
    name = skill_dir.name
    passed = True

    # 检查必须文件
    md_path = skill_dir / "skill.md"
    py_path = skill_dir / "skill.py"

    if not md_path.exists():
        print(f"  ❌ {name}: 缺少 skill.md")
        return False
    if not py_path.exists():
        print(f"  ❌ {name}: 缺少 skill.py")
        return False

    # 检查 skill.md frontmatter
    md_content = md_path.read_text(encoding="utf-8")
    lines = md_content.split("\n")
    if lines[0].strip() == "---":
        try:
            end_idx = lines.index("---", 1)
            frontmatter_str = "\n".join(lines[1:end_idx])
            import yaml
            meta = yaml.safe_load(frontmatter_str) or {}
            for field in REQUIRED_SKILL_MD_FIELDS:
                if field not in meta:
                    print(f"  ❌ {name}/skill.md: 缺少必须字段 '{field}'")
                    passed = False
        except Exception as e:
            print(f"  ❌ {name}/skill.md: YAML 解析失败：{e}")
            passed = False
    else:
        print(f"  ❌ {name}/skill.md: 必须以 '---' 开头（YAML frontmatter）")
        passed = False

    # 检查 skill.py 包含 run 函数
    py_content = py_path.read_text(encoding="utf-8")
    if not re.search(r"^def run\s*\(", py_content, re.MULTILINE):
        print(f"  ❌ {name}/skill.py: 缺少 run(args: dict) -> dict 函数")
        passed = False

    # 检查危险代码模式
    for pattern in FORBIDDEN_PATTERNS:
        if re.search(pattern, py_content):
            print(f"  ❌ {name}/skill.py: 检测到危险代码模式：{pattern}")
            passed = False

    if passed:
        print(f"  ✅ {name}: 规范验证通过")

    return passed


if __name__ == "__main__":
    ok = check_all()
    sys.exit(0 if ok else 1)
