# skills/tcm_visualization/skill.py  v1.0.0
"""
TCM 网络图可视化 Skill。

绘制中药材成分-靶点网络图，使用 NetworkX + Matplotlib。
生产环境可替换为 Pyvis（交互式）或 Cytoscape 导出。
"""

import os
from datetime import datetime, timezone


def run(args: dict) -> dict:
    """
    绘制中药材成分-靶点网络图。

    Args:
        args: 包含：
          - herb_names (list[str], 必须): 中药材名称
          - target_data (dict, 可选): 预先计算的靶点分析结果
          - output_format (str, 可选): "png" | "svg" | "both"
          - output_path (str, 可选): 输出文件路径
          - layout (str, 可选): 网络布局算法
          - max_nodes (int, 可选): 最大节点数

    Returns:
        Envelope v2.4 格式字典，包含生成图片的路径
    """
    herb_names    = args.get("herb_names", [])
    target_data   = args.get("target_data")
    output_format = args.get("output_format", "png")
    output_path   = args.get("output_path", "./workspace/network_plot.png")
    layout        = args.get("layout", "spring")
    max_nodes     = int(args.get("max_nodes", 50))

    # ── 参数验证 ───────────────────────────────────────────────────────────────
    if not herb_names:
        return _error("INVALID_ARGS", "herb_names 不能为空", "请提供至少一种中药材名称")

    if not isinstance(herb_names, list):
        herb_names = [herb_names]

    # ── 导入依赖（延迟导入，避免环境未安装时影响注册）────────────────────────
    try:
        import matplotlib
        matplotlib.use("Agg")  # 非交互模式（无 GUI）
        import matplotlib.pyplot as plt
        import networkx as nx
    except ImportError as e:
        return _error(
            "EXECUTION_CRASH",
            f"缺少依赖库：{e}",
            "请安装 matplotlib 和 networkx：pip install matplotlib networkx",
        )

    # ── 构建网络数据 ───────────────────────────────────────────────────────────
    logs = []
    G = nx.Graph()
    node_colors: dict[str, str] = {}
    node_sizes: dict[str, int] = {}

    # 从 target_data 或内置数据构建网络
    _HERB_TARGETS = _get_default_targets()

    for herb_name in herb_names:
        # 添加药材节点
        G.add_node(herb_name)
        node_colors[herb_name] = "#FF8C00"  # 橙色：药材
        node_sizes[herb_name] = 800

        herb_data = None
        # 优先使用传入的 target_data
        if target_data and isinstance(target_data, dict):
            herb_target_map = target_data.get("outputs", {}).get(
                "summary_for_llm", {}
            ).get("structured_data", {}).get("herb_target_map", {})
            if herb_name in herb_target_map:
                for target in herb_target_map[herb_name][:max_nodes // len(herb_names)]:
                    comp_node = f"comp_{herb_name[:2]}"  # 简化：合并成分节点
                    G.add_node(comp_node)
                    node_colors[comp_node] = "#4169E1"  # 蓝色：成分
                    node_sizes[comp_node] = 400
                    G.add_edge(herb_name, comp_node)
                    G.add_node(target)
                    node_colors[target] = "#228B22"  # 绿色：靶点
                    node_sizes[target] = 300
                    G.add_edge(comp_node, target)
                continue

        # 使用内置数据
        herb_data = _HERB_TARGETS.get(herb_name)
        if herb_data is None:
            logs.append({
                "t":       _now_iso(),
                "stage":   "warn",
                "message": f"[tcm.visualization.herb_network_plot] 未找到 '{herb_name}' 的数据，跳过",
            })
            continue

        nodes_added = 0
        for comp in herb_data["active_components"]:
            if nodes_added >= max_nodes:
                break
            comp_name = comp["name"]
            G.add_node(comp_name)
            node_colors[comp_name] = "#4169E1"  # 蓝色：成分
            node_sizes[comp_name] = 400
            G.add_edge(herb_name, comp_name)

            for target in comp["targets"][:5]:
                G.add_node(target)
                node_colors[target] = "#228B22"  # 绿色：靶点
                node_sizes[target] = 300
                G.add_edge(comp_name, target)
                nodes_added += 1

    if G.number_of_nodes() == 0:
        return _error("DATA_NOT_FOUND", "无法构建网络（没有有效节点）", "请检查中药材名称")

    logs.append({
        "t":       _now_iso(),
        "stage":   "run",
        "message": (
            f"[tcm.visualization.herb_network_plot] 网络构建完成："
            f"{G.number_of_nodes()} 个节点，{G.number_of_edges()} 条边"
        ),
    })

    # ── 绘图 ───────────────────────────────────────────────────────────────────
    plt.figure(figsize=(14, 10))
    plt.title(
        f"{'、'.join(herb_names)} 成分-靶点网络图",
        fontsize=14, fontweight="bold", pad=20
    )

    # 计算布局
    pos_fn = {
        "spring":       lambda g: nx.spring_layout(g, seed=42, k=2.0),
        "circular":     nx.circular_layout,
        "shell":        nx.shell_layout,
        "kamada_kawai": nx.kamada_kawai_layout,
    }.get(layout, lambda g: nx.spring_layout(g, seed=42))
    pos = pos_fn(G)

    # 绘制节点和边
    node_list = list(G.nodes())
    colors_list = [node_colors.get(n, "#CCCCCC") for n in node_list]
    sizes_list  = [node_sizes.get(n, 200)        for n in node_list]

    nx.draw_networkx_nodes(G, pos, nodelist=node_list,
                           node_color=colors_list, node_size=sizes_list, alpha=0.85)
    nx.draw_networkx_edges(G, pos, alpha=0.4, edge_color="#888888", width=1.2)
    nx.draw_networkx_labels(G, pos, font_size=8, font_color="black")

    # 图例
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor="#FF8C00", label="中药材"),
        Patch(facecolor="#4169E1", label="活性成分"),
        Patch(facecolor="#228B22", label="靶点基因"),
    ]
    plt.legend(handles=legend_elements, loc="upper right", fontsize=10)
    plt.axis("off")
    plt.tight_layout()

    # ── 保存文件 ───────────────────────────────────────────────────────────────
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    saved_paths = []
    formats = ["png", "svg"] if output_format == "both" else [output_format]
    for fmt in formats:
        base = os.path.splitext(output_path)[0]
        save_path = f"{base}.{fmt}"
        plt.savefig(save_path, format=fmt, dpi=150 if fmt == "png" else None,
                    bbox_inches="tight", facecolor="white")
        saved_paths.append(save_path)
        logs.append({
            "t":       _now_iso(),
            "stage":   "run",
            "message": f"[tcm.visualization.herb_network_plot] 图片已保存：{save_path}",
        })

    plt.close()

    # ── 构造 Envelope ─────────────────────────────────────────────────────────
    herbs_str = "、".join(herb_names)
    artifact_refs = [
        {
            "id":   f"net_plot_{i}",
            "type": "plot",
            "path": p,
            "desc": f"{herbs_str} 成分-靶点网络图（{os.path.splitext(p)[1]}）",
        }
        for i, p in enumerate(saved_paths)
    ]

    artifacts = [
        {
            "id":          f"art_net_{i}",
            "type":        "plot",
            "path":        p,
            "skill":       "tcm.visualization.herb_network_plot",
            "description": f"{herbs_str} 网络图",
            "created_at":  _now_iso(),
            "size_bytes":  os.path.getsize(p) if os.path.exists(p) else 0,
        }
        for i, p in enumerate(saved_paths)
    ]

    return {
        "outputs": {
            "status": "ok",
            "summary_for_llm": {
                "result_brief": (
                    f"✅ {herbs_str} 成分-靶点网络图已生成。\n"
                    f"网络包含 {G.number_of_nodes()} 个节点（药材/成分/靶点）"
                    f"和 {G.number_of_edges()} 条连接边。\n"
                    f"输出文件：{', '.join(saved_paths)}"
                ),
                "structured_data": {
                    "nodes":      G.number_of_nodes(),
                    "edges":      G.number_of_edges(),
                    "herb_nodes": len(herb_names),
                    "saved_paths": saved_paths,
                },
                "artifact_refs":  artifact_refs,
                "next_step_hint": "图片已保存，可继续使用 tcm.visualization.pathway_heatmap 绘制通路富集热图",
                "error_brief":    None,
            },
            "full_log": {
                "research_log": logs,
                "artifacts":    artifacts,
                "provenance":   [],
                "namespace_delta": {
                    "new_vars":      [],
                    "new_artifacts": saved_paths,
                    "updated_vars":  [],
                },
            },
            "error": None,
        }
    }


# ─── 辅助函数 ──────────────────────────────────────────────────────────────────

def _get_default_targets() -> dict:
    """返回默认靶点数据（与 tcm_analysis/skill.py 保持一致）。"""
    return {
        "黄芪": {"active_components": [
            {"name": "黄芪甲苷", "targets": ["TP53", "AKT1", "VEGFA", "TNF", "IL6"]},
            {"name": "毛蕊异黄酮", "targets": ["ESR1", "ESR2", "AKT1", "PTGS2"]},
            {"name": "芒柄花素", "targets": ["ESR1", "EGFR", "AKT1", "TP53"]},
        ]},
        "当归": {"active_components": [
            {"name": "阿魏酸", "targets": ["PTGS2", "PTGS1", "NOS2", "AKT1"]},
            {"name": "Z-藁本内酯", "targets": ["TRPV1", "CALM1", "CACNA1C"]},
        ]},
        "丹参": {"active_components": [
            {"name": "丹参酮IIA", "targets": ["TP53", "AKT1", "BCL2", "CASP3", "MYC"]},
            {"name": "丹酚酸B", "targets": ["AKT1", "MAPK1", "TNF", "IL6"]},
        ]},
        "人参": {"active_components": [
            {"name": "人参皂苷Rb1", "targets": ["AKT1", "INS", "IGF1R", "GLUT4"]},
            {"name": "人参皂苷Rg1", "targets": ["NOS3", "AKT1", "BCL2", "CASP3"]},
        ]},
        "甘草": {"active_components": [
            {"name": "甘草酸", "targets": ["TNF", "IL6", "PTGS2", "MAPK1"]},
            {"name": "甘草苷", "targets": ["ESR1", "AKT1", "PTGS2"]},
        ]},
    }


def _error(code: str, message: str, hint: str) -> dict:
    return {
        "outputs": {
            "status": "error",
            "summary_for_llm": {
                "result_brief":  None,
                "structured_data": None,
                "artifact_refs": [],
                "next_step_hint": hint,
                "error_brief":   f"[tcm.visualization.herb_network_plot] {message}",
            },
            "full_log": {
                "research_log": [{
                    "t":       _now_iso(),
                    "stage":   "error",
                    "message": f"[tcm.visualization.herb_network_plot] {code}: {message}",
                }],
                "artifacts":  [],
                "provenance": [],
            },
            "error": {
                "code":                code,
                "message":             message,
                "retryable":           code in ("EXECUTION_TIMEOUT", "NETWORK_ERROR"),
                "mitigation":          hint,
                "fallback_action":     "retry_with_plan_correction" if code == "INVALID_ARGS" else "human_review",
                "plan_correction_hint": hint,
            },
        }
    }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
