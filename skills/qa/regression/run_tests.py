# skills/qa/regression/run_tests.py  v2.4
"""
回归测试运行器——验证 Fix-I 和 Fix-J 的实际行为。

运行方式：
  python skills/qa/regression/run_tests.py

或通过 pytest：
  pytest skills/qa/regression/run_tests.py -v
"""

import sys
import traceback
from pathlib import Path
from unittest.mock import patch

# 确保项目根目录在 sys.path 中
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 检查可选依赖（langchain_core 需要单独安装）
try:
    import langchain_core  # noqa: F401
    HAS_LANGCHAIN = True
except ImportError:
    HAS_LANGCHAIN = False


def _skip_no_langchain(test_fn):
    """装饰器：langchain_core 未安装时跳过该测试。"""
    def wrapper():
        if not HAS_LANGCHAIN:
            print(
                f"⚠️  {test_fn.__name__} 已跳过"
                "（需要 langchain_core，运行 pip install langchain-core langgraph）"
            )
            return
        test_fn()
    wrapper.__name__ = test_fn.__name__
    return wrapper


# ── Fix-I 测试 ─────────────────────────────────────────────────────────────────

@_skip_no_langchain
def test_exception_guard_zero_division():
    """
    EXCEPTION-GUARD-01: run_skill 抛出 ZeroDivisionError 时，
    execute_skill 返回合法 ToolMessage 而非崩溃。
    """
    from langchain_core.messages import ToolMessage
    from biomni.agent.nodes.execute_node import execute_skill

    def crashing_runner(skill_name, skill_args):
        raise ZeroDivisionError("division by zero in ADMET scoring")

    tool_call = {"id": "call_001", "name": "tcm.database.herb_query", "args": {}}
    result = execute_skill(
        state={},
        tool_call=tool_call,
        skill_name="tcm.database.herb_query",
        skill_args={"herb_name": "黄芪"},
        skill_runner=crashing_runner,
    )

    # 断言
    assert isinstance(result, dict), "返回值必须是 dict"
    assert "messages" in result, "返回值必须包含 messages"
    assert len(result["messages"]) == 1, "必须有且只有 1 条 ToolMessage"

    tm = result["messages"][0]
    assert isinstance(tm, ToolMessage), f"消息必须是 ToolMessage，实际：{type(tm)}"
    assert tm.tool_call_id == "call_001", "tool_call_id 必须与输入匹配"
    assert isinstance(tm.content, str), "content 必须是字符串（Fix-F）"
    assert len(tm.content) <= 10_000, "content 不能超过 10,000 字符（Fix-H）"
    assert "EXECUTION_CRASH" in tm.content, "content 必须包含错误码 EXECUTION_CRASH"

    assert result.get("status") == "error", "status 必须是 error"
    assert result.get("error", {}).get("code") == "EXECUTION_CRASH"
    assert result.get("error", {}).get("retryable") is False, "ZeroDivisionError 不可重试"
    assert result.get("error", {}).get("fallback_action") == "human_review"

    research_log = result.get("research_log", [])
    assert any("ZeroDivisionError" in log.get("message", "") for log in research_log), \
        "research_log 必须记录 ZeroDivisionError"

    print("✅ EXCEPTION-GUARD-01 通过")


@_skip_no_langchain
def test_exception_guard_memory_error():
    """
    EXCEPTION-GUARD-OOM-01: MemoryError 被识别为 EXECUTION_OOM，
    retryable=true，附带减少输入规模的建议。
    """
    from langchain_core.messages import ToolMessage
    from biomni.agent.nodes.execute_node import execute_skill

    def oom_runner(skill_name, skill_args):
        raise MemoryError("unable to allocate 8GB array for target matrix")

    tool_call = {"id": "call_002", "name": "tcm.analysis.target_analysis", "args": {}}
    result = execute_skill(
        state={},
        tool_call=tool_call,
        skill_name="tcm.analysis.target_analysis",
        skill_args={"herb_names": ["黄芪", "当归"]},
        skill_runner=oom_runner,
    )

    tm = result["messages"][0]
    assert isinstance(tm, ToolMessage)
    assert tm.tool_call_id == "call_002"
    assert "EXECUTION_OOM" in tm.content
    assert "内存溢出" in tm.content
    assert "减少输入数据规模" in tm.content

    assert result.get("error", {}).get("code") == "EXECUTION_OOM"
    assert result.get("error", {}).get("retryable") is True, "MemoryError 应该可以重试"
    assert result.get("error", {}).get("fallback_action") == "retry_with_plan_correction"

    print("✅ EXCEPTION-GUARD-OOM-01 通过")


@_skip_no_langchain
def test_exception_guard_timeout_error():
    """
    TimeoutError 被识别为 EXECUTION_TIMEOUT，retryable=true。
    """
    from biomni.agent.nodes.execute_node import execute_skill

    def timeout_runner(skill_name, skill_args):
        raise TimeoutError("API call timed out after 60 seconds")

    result = execute_skill(
        state={},
        tool_call={"id": "call_003", "name": "tcm.database.herb_query", "args": {}},
        skill_name="tcm.database.herb_query",
        skill_args={"herb_name": "黄芪"},
        skill_runner=timeout_runner,
    )

    assert result.get("error", {}).get("code") == "EXECUTION_TIMEOUT"
    assert result.get("error", {}).get("retryable") is True
    print("✅ EXCEPTION-GUARD-TIMEOUT-01 通过")


def test_no_bare_except_in_execute_node():
    """
    CI Gate Fix-I：execute_node.py 不允许 bare except: 或 except BaseException:
    """
    execute_node_path = PROJECT_ROOT / "biomni" / "agent" / "nodes" / "execute_node.py"
    content = execute_node_path.read_text(encoding="utf-8")

    assert "except:" not in content, \
        "execute_node.py 不允许 bare except:，应使用 except Exception as e:"
    assert "except BaseException" not in content, \
        "execute_node.py 不允许捕获 BaseException，SystemExit/KeyboardInterrupt 应正常传播"
    assert "except Exception as" in content, \
        "execute_node.py 必须包含 except Exception as e: 兜底"

    print("✅ CI-Gate-Fix-I-01 通过：execute_node.py 异常拦截规范合规")


# ── Fix-J 测试 ─────────────────────────────────────────────────────────────────

@_skip_no_langchain
def test_message_trim_pairing_integrity():
    """
    MSG-TRIM-PAIRING-01: 修剪旧轮次时，AIMessage 和其所有对应 ToolMessage
    必须同时删除，不出现孤立消息。
    """
    from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage, ToolMessage
    from biomni.utils.message_trimmer import build_remove_messages

    # 构造测试消息历史（5 轮）
    messages = [
        HumanMessage(content="分析黄芪和当归的靶点并绘制网络图", id="h1"),
        # 第1轮（2个 tool_calls）
        AIMessage(content="", id="ai1", tool_calls=[
            {"id": "c1", "name": "tcm.database.herb_query", "args": {"herb_name": "黄芪"}},
            {"id": "c2", "name": "tcm.database.herb_query", "args": {"herb_name": "当归"}},
        ]),
        ToolMessage(content='{"status":"ok"}', id="tm1", tool_call_id="c1", name="tcm.database.herb_query"),
        ToolMessage(content='{"status":"ok"}', id="tm2", tool_call_id="c2", name="tcm.database.herb_query"),
        # 第2轮
        AIMessage(content="", id="ai2", tool_calls=[
            {"id": "c3", "name": "tcm.analysis.target_analysis", "args": {}},
        ]),
        ToolMessage(content='{"status":"ok"}', id="tm3", tool_call_id="c3", name="tcm.analysis.target_analysis"),
        # 第3轮
        AIMessage(content="", id="ai3", tool_calls=[
            {"id": "c4", "name": "tcm.analysis.herb_similarity", "args": {}},
        ]),
        ToolMessage(content='{"status":"ok"}', id="tm4", tool_call_id="c4", name="tcm.analysis.herb_similarity"),
        # 第4轮
        AIMessage(content="", id="ai4", tool_calls=[
            {"id": "c5", "name": "tcm.visualization.herb_network_plot", "args": {}},
        ]),
        ToolMessage(content='{"status":"ok"}', id="tm5", tool_call_id="c5", name="tcm.visualization.herb_network_plot"),
        # 第5轮（2个 tool_calls）
        AIMessage(content="", id="ai5", tool_calls=[
            {"id": "c6", "name": "tcm.database.herb_query", "args": {"herb_name": "人参"}},
            {"id": "c7", "name": "tcm.database.herb_query", "args": {"herb_name": "丹参"}},
        ]),
        ToolMessage(content='{"status":"ok"}', id="tm6", tool_call_id="c6", name="tcm.database.herb_query"),
        ToolMessage(content='{"status":"ok"}', id="tm7", tool_call_id="c7", name="tcm.database.herb_query"),
    ]

    remove_msgs = build_remove_messages(messages, keep_rounds=3, keep_first_n_human=1)

    # 收集被删除的 ID
    deleted_ids = {rm.id for rm in remove_msgs}

    # 断言：应删除第1、2轮（共5条消息）
    assert "ai1" in deleted_ids, "ai1（第1轮）应被删除"
    assert "tm1" in deleted_ids, "tm1（第1轮 ToolMessage）应被删除"
    assert "tm2" in deleted_ids, "tm2（第1轮 ToolMessage）应被删除"
    assert "ai2" in deleted_ids, "ai2（第2轮）应被删除"
    assert "tm3" in deleted_ids, "tm3（第2轮 ToolMessage）应被删除"

    # 断言：保留最近3轮（第3、4、5轮）
    preserved = ["ai3", "tm4", "ai4", "tm5", "ai5", "tm6", "tm7"]
    for msg_id in preserved:
        assert msg_id not in deleted_ids, f"{msg_id}（最近3轮）不应被删除"

    # 断言：保留 HumanMessage
    assert "h1" not in deleted_ids, "HumanMessage h1 不应被删除（keep_first_n_human=1）"

    # 断言：配对完整性——删除 ai1 时，tm1 和 tm2 也必须被删除
    assert all(tm_id in deleted_ids for tm_id in ["tm1", "tm2"]), \
        "配对完整性违规：删除 ai1 时，其对应 ToolMessage（tm1, tm2）也必须被删除"

    # 断言：所有删除对象都是 RemoveMessage
    assert all(isinstance(rm, RemoveMessage) for rm in remove_msgs), \
        "所有删除对象必须是 RemoveMessage 实例"

    # 断言：删除数量正确（5条）
    assert len(remove_msgs) == 5, f"应删除 5 条消息，实际删除 {len(remove_msgs)} 条"

    print("✅ MSG-TRIM-PAIRING-01 通过")


@_skip_no_langchain
def test_should_trim_threshold():
    """
    should_trim 阈值测试：超过字符数或轮次数时触发修剪。
    """
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
    from biomni.utils.message_trimmer import should_trim

    # 未超阈值
    messages_small = [
        HumanMessage(content="短消息", id="h1"),
        AIMessage(content="短回复", id="ai1", tool_calls=[]),
    ]
    assert not should_trim(messages_small, max_total_chars=40_000), \
        "小消息不应触发修剪"

    # 超字符数阈值
    long_content = "x" * 41_000
    messages_large = [
        HumanMessage(content=long_content, id="h2"),
    ]
    assert should_trim(messages_large, max_total_chars=40_000), \
        "超过字符数阈值应触发修剪"

    print("✅ MSG-TRIM-THRESHOLD-01 通过")


@_skip_no_langchain
def test_trim_no_remove_when_within_limit():
    """
    当消息历史未超过限制时，build_remove_messages 应返回空列表。
    """
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
    from biomni.utils.message_trimmer import build_remove_messages

    messages = [
        HumanMessage(content="查询黄芪", id="h1"),
        AIMessage(content="", id="ai1", tool_calls=[{"id": "c1", "name": "tcm.database.herb_query", "args": {}}]),
        ToolMessage(content='{"status":"ok"}', id="tm1", tool_call_id="c1"),
    ]

    remove_msgs = build_remove_messages(messages, keep_rounds=10)
    assert remove_msgs == [], f"未超限制时应返回空列表，实际：{remove_msgs}"
    print("✅ MSG-TRIM-NO-REMOVE-01 通过")


# ── Skill 系统测试 ────────────────────────────────────────────────────────────

def test_skill_registry_register_and_get():
    """Skill 注册和获取功能测试。"""
    from skills.skill_registry import SkillRegistry, SkillMeta

    registry = SkillRegistry()

    def dummy_runner(args): return {"outputs": {"status": "ok"}}

    skill = SkillMeta(
        name="test.skill.dummy",
        category="test",
        description="测试 Skill",
        when_to_use="测试时使用",
        input_schema={},
        output_schema={},
        tags=["test"],
        version="1.0.0",
        author="test",
        requires=[],
        skill_dir="/tmp/test_skill",
        runner=dummy_runner,
    )

    registry.register(skill)
    assert "test.skill.dummy" in registry
    assert registry.get("test.skill.dummy") is not None
    assert registry.get_runner("test.skill.dummy") is dummy_runner

    registry.disable("test.skill.dummy")
    assert registry.get_runner("test.skill.dummy") is None  # 禁用后不可路由

    registry.enable("test.skill.dummy")
    assert registry.get_runner("test.skill.dummy") is dummy_runner  # 重新启用

    print("✅ SKILL-REGISTRY-01 通过")


def test_tcm_database_skill():
    """TCM 数据库 Skill 功能测试。"""
    import importlib.util
    from pathlib import Path

    skill_py = PROJECT_ROOT / "skills" / "tcm_database" / "skill.py"
    spec = importlib.util.spec_from_file_location("tcm_db_skill", skill_py)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # 正常查询
    result = module.run({"herb_name": "黄芪"})
    assert result["outputs"]["status"] == "ok"
    assert result["outputs"]["summary_for_llm"]["structured_data"]["herb_name"] == "黄芪"

    # 空名称
    error_result = module.run({"herb_name": ""})
    assert error_result["outputs"]["status"] == "error"
    assert error_result["outputs"]["error"]["code"] == "INVALID_ARGS"

    # 不存在的药材
    not_found = module.run({"herb_name": "火星草药"})
    assert not_found["outputs"]["status"] == "error"
    assert not_found["outputs"]["error"]["code"] == "DATA_NOT_FOUND"

    print("✅ TCM-DATABASE-SKILL-01 通过")


# ── 主入口 ─────────────────────────────────────────────────────────────────────

def run_all_tests():
    """运行所有回归测试。"""
    tests = [
        test_exception_guard_zero_division,
        test_exception_guard_memory_error,
        test_exception_guard_timeout_error,
        test_no_bare_except_in_execute_node,
        test_message_trim_pairing_integrity,
        test_should_trim_threshold,
        test_trim_no_remove_when_within_limit,
        test_skill_registry_register_and_get,
        test_tcm_database_skill,
    ]

    passed = 0
    failed = 0
    errors = []

    print("=" * 60)
    print("Biomni v2.4 回归测试运行器")
    print("=" * 60)

    for test_fn in tests:
        try:
            test_fn()
            passed += 1
        except Exception as e:
            failed += 1
            errors.append((test_fn.__name__, str(e), traceback.format_exc()))
            print(f"❌ {test_fn.__name__} 失败：{e}")

    print("\n" + "=" * 60)
    print(f"结果：{passed} 通过 / {failed} 失败（共 {len(tests)} 个测试）")
    print("=" * 60)

    if errors:
        print("\n失败详情：")
        for name, msg, tb in errors:
            print(f"\n[{name}]")
            print(tb)
        sys.exit(1)
    else:
        print("✅ 所有测试通过！")


if __name__ == "__main__":
    run_all_tests()
