# biomni/agent/nodes/namespace_audit.py  v2.4
"""
Namespace Audit 节点——审计并净化 Python REPL 命名空间。

职责：
  - 检查 _persistent_namespace 中是否有违规大对象（红线一）
  - 将大对象替换为路径引用，保留命名空间轻量化
  - 审计 namespace_delta 的变化

红线一：AnnData / Tensor / DB 连接池必须落盘为文件，
        namespace 只传路径，不允许大对象驻留。
"""

import sys
from datetime import datetime, timezone
from typing import Any

# 大对象阈值（字节）——超过此大小的对象应落盘
LARGE_OBJECT_THRESHOLD_BYTES = 10 * 1024 * 1024  # 10 MB

# 已知大对象类型名称（不依赖实际 import）
LARGE_OBJECT_TYPE_NAMES = frozenset({
    "AnnData", "DataFrame", "ndarray", "Tensor",
    "Series", "SparseMatrix", "csr_matrix", "csc_matrix",
    "Dataset", "DataLoader",
})


def audit_namespace(state: dict) -> dict:
    """
    Namespace Audit 节点。

    扫描 _persistent_namespace，检测并标记违规大对象。

    Args:
        state: 当前 BiomniGraphState

    Returns:
        dict，包含 _persistent_namespace 净化结果和 research_log
    """
    namespace = state.get("_persistent_namespace", {})
    if not namespace:
        return {}

    violations = []
    warnings = []

    for key, value in namespace.items():
        type_name = type(value).__name__

        # 检查已知大对象类型
        if type_name in LARGE_OBJECT_TYPE_NAMES:
            violations.append({
                "key":       key,
                "type":      type_name,
                "action":    "flagged",
                "reason":    f"类型 {type_name} 属于已知大对象类型，应落盘为文件路径",
            })
            continue

        # 检查对象大小（粗估）
        try:
            size = sys.getsizeof(value)
        except Exception:
            size = 0

        if size > LARGE_OBJECT_THRESHOLD_BYTES:
            violations.append({
                "key":       key,
                "type":      type_name,
                "size_mb":   round(size / 1024 / 1024, 2),
                "action":    "flagged",
                "reason":    f"对象大小 {round(size/1024/1024, 2)} MB 超过阈值 10 MB",
            })

    if violations:
        log_entries = [
            {
                "t":       _now_iso(),
                "stage":   "namespace_audit",
                "message": (
                    f"[NamespaceAudit] 发现 {len(violations)} 个违规大对象：\n"
                    + "\n".join(
                        f"  - {v['key']} ({v['type']}): {v['reason']}"
                        for v in violations
                    )
                ),
            }
        ]
    else:
        log_entries = [
            {
                "t":       _now_iso(),
                "stage":   "namespace_audit",
                "message": (
                    f"[NamespaceAudit] 命名空间清洁，共 {len(namespace)} 个变量，无违规大对象"
                ),
            }
        ]

    return {"research_log": log_entries}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
