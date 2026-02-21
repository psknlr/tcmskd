# biomni/agent/nodes/artifact_store.py  v2.4
"""
Artifact Store 节点——管理工具产出的文件和数据产物。

职责：
  - 收集工具执行产生的文件（图表、CSV、报告等）
  - 生成产物引用（artifact_ref），供 LLM 在后续步骤中引用
  - 防止大对象写入 namespace（红线一）

产物引用格式：
  {
    "id":          str,    # 唯一标识符
    "type":        str,    # "file" | "plot" | "report" | "dataframe"
    "path":        str,    # 文件系统路径（相对于 workspace）
    "skill":       str,    # 生成该产物的 Skill 名称
    "description": str,    # 产物描述（LLM 可理解）
    "created_at":  str,    # ISO 时间戳
    "size_bytes":  int,    # 文件大小（可选）
  }
"""

import os
from datetime import datetime, timezone


def store_artifacts(state: dict, workspace_path: str = "./workspace") -> dict:
    """
    Artifact Store 节点。

    扫描最新工具执行产出的 artifacts，验证文件存在性，
    并将有效产物引用合并到 state.artifacts。

    Args:
        state:          当前 BiomniGraphState
        workspace_path: 工作区根路径

    Returns:
        dict，包含 artifacts 更新和 research_log
    """
    # 从 namespace_delta 中提取新产物
    ns_delta = state.get("namespace_delta") or {}
    new_artifact_paths = ns_delta.get("new_artifacts", [])

    if not new_artifact_paths:
        return {}

    validated_artifacts = []
    skipped = []

    for art_info in new_artifact_paths:
        if isinstance(art_info, str):
            # 简单路径格式
            art_path = art_info
            art_type = _infer_type(art_path)
            art_desc = f"产物文件：{os.path.basename(art_path)}"
            skill_name = "unknown"
        elif isinstance(art_info, dict):
            art_path  = art_info.get("path", "")
            art_type  = art_info.get("type", _infer_type(art_path))
            art_desc  = art_info.get("description", f"产物文件：{os.path.basename(art_path)}")
            skill_name = art_info.get("skill", "unknown")
        else:
            continue

        # 验证文件存在性（防止幽灵引用）
        full_path = os.path.join(workspace_path, art_path) if not os.path.isabs(art_path) else art_path
        if not os.path.exists(full_path):
            skipped.append(art_path)
            continue

        size_bytes = os.path.getsize(full_path)
        validated_artifacts.append({
            "id":          f"art_{_now_ts()}_{len(validated_artifacts)}",
            "type":        art_type,
            "path":        art_path,
            "skill":       skill_name,
            "description": art_desc,
            "created_at":  _now_iso(),
            "size_bytes":  size_bytes,
        })

    if not validated_artifacts and not skipped:
        return {}

    log_entry = {
        "t":       _now_iso(),
        "stage":   "artifact_store",
        "message": (
            f"[ArtifactStore] 验证产物 {len(validated_artifacts)} 个，"
            f"跳过（文件不存在）{len(skipped)} 个"
            + (f"，跳过路径：{skipped}" if skipped else "")
        ),
    }

    return {
        "artifacts":    validated_artifacts,
        "research_log": [log_entry],
    }


def _infer_type(path: str) -> str:
    """根据文件扩展名推断产物类型。"""
    ext = os.path.splitext(path)[1].lower()
    type_map = {
        ".png": "plot", ".jpg": "plot", ".jpeg": "plot", ".svg": "plot", ".pdf": "report",
        ".csv": "dataframe", ".tsv": "dataframe", ".xlsx": "dataframe", ".parquet": "dataframe",
        ".json": "file", ".txt": "file", ".md": "report", ".html": "report",
    }
    return type_map.get(ext, "file")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _now_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
