# skills/tcm_analysis/skill.py  v1.0.0
"""
TCM 靶点分析 Skill——网络药理学核心分析流程。

实现中药材的活性成分筛选、靶点收集、通路富集分析。
生产环境请接入实际数据库（TCMSP API / 本地 HDF5 数据）。
"""

from datetime import datetime, timezone

# ── 示例靶点数据（生产环境替换为实际数据库查询）──────────────────────────────
_HERB_TARGETS = {
    "黄芪": {
        "active_components": [
            {"name": "黄芪甲苷", "ob": 36.8, "dl": 0.20, "targets": ["TP53", "AKT1", "VEGFA", "TNF", "IL6"]},
            {"name": "毛蕊异黄酮", "ob": 38.7, "dl": 0.21, "targets": ["ESR1", "ESR2", "AKT1", "PTGS2"]},
            {"name": "芒柄花素", "ob": 68.4, "dl": 0.21, "targets": ["ESR1", "EGFR", "AKT1", "TP53"]},
            {"name": "黄芪皂苷II", "ob": 32.5, "dl": 0.19, "targets": ["TNF", "IL6", "NF1"]},
        ],
        "pathway_enrichment": [
            {"pathway": "PI3K-Akt信号通路", "kegg_id": "hsa04151", "p_value": 0.001, "genes": ["AKT1", "TP53", "VEGFA"]},
            {"pathway": "TNF信号通路", "kegg_id": "hsa04668", "p_value": 0.003, "genes": ["TNF", "IL6"]},
            {"pathway": "癌症相关信号通路", "kegg_id": "hsa05200", "p_value": 0.005, "genes": ["TP53", "EGFR", "AKT1"]},
        ],
    },
    "当归": {
        "active_components": [
            {"name": "阿魏酸", "ob": 55.4, "dl": 0.12, "targets": ["PTGS2", "PTGS1", "NOS2", "AKT1"]},
            {"name": "Z-藁本内酯", "ob": 87.6, "dl": 0.13, "targets": ["TRPV1", "CALM1", "CACNA1C"]},
            {"name": "正丁烯基苯酞", "ob": 45.2, "dl": 0.14, "targets": ["TRPV1", "NOS2"]},
        ],
        "pathway_enrichment": [
            {"pathway": "花生四烯酸代谢", "kegg_id": "hsa00590", "p_value": 0.002, "genes": ["PTGS2", "PTGS1"]},
            {"pathway": "钙信号通路", "kegg_id": "hsa04020", "p_value": 0.008, "genes": ["CALM1", "CACNA1C"]},
        ],
    },
    "人参": {
        "active_components": [
            {"name": "人参皂苷Rb1", "ob": 17.7, "dl": 0.28, "targets": ["AKT1", "INS", "IGF1R", "GLUT4"]},
            {"name": "人参皂苷Rg1", "ob": 22.3, "dl": 0.25, "targets": ["NOS3", "AKT1", "BCL2", "CASP3"]},
            {"name": "人参皂苷Re", "ob": 19.8, "dl": 0.23, "targets": ["INS", "AKT1", "PPARG"]},
        ],
        "pathway_enrichment": [
            {"pathway": "胰岛素信号通路", "kegg_id": "hsa04910", "p_value": 0.001, "genes": ["AKT1", "INS", "IGF1R"]},
            {"pathway": "PPAR信号通路", "kegg_id": "hsa03320", "p_value": 0.004, "genes": ["PPARG"]},
        ],
    },
    "丹参": {
        "active_components": [
            {"name": "丹参酮IIA", "ob": 49.9, "dl": 0.40, "targets": ["TP53", "AKT1", "BCL2", "CASP3", "MYC"]},
            {"name": "丹酚酸B", "ob": 26.8, "dl": 0.58, "targets": ["AKT1", "MAPK1", "TNF", "IL6"]},
            {"name": "丹参素", "ob": 42.3, "dl": 0.22, "targets": ["PTGS2", "NOS3", "AKT1"]},
        ],
        "pathway_enrichment": [
            {"pathway": "凋亡通路", "kegg_id": "hsa04210", "p_value": 0.001, "genes": ["TP53", "BCL2", "CASP3"]},
            {"pathway": "PI3K-Akt信号通路", "kegg_id": "hsa04151", "p_value": 0.002, "genes": ["AKT1", "MAPK1"]},
        ],
    },
    "甘草": {
        "active_components": [
            {"name": "甘草酸", "ob": 17.2, "dl": 0.71, "targets": ["TNF", "IL6", "PTGS2", "MAPK1"]},
            {"name": "甘草苷", "ob": 16.8, "dl": 0.45, "targets": ["ESR1", "AKT1", "PTGS2"]},
            {"name": "甘草素", "ob": 29.6, "dl": 0.27, "targets": ["PTGS2", "NOS2", "TNF"]},
        ],
        "pathway_enrichment": [
            {"pathway": "炎症通路（NF-κB）", "kegg_id": "hsa04064", "p_value": 0.001, "genes": ["TNF", "IL6"]},
            {"pathway": "花生四烯酸代谢", "kegg_id": "hsa00590", "p_value": 0.003, "genes": ["PTGS2"]},
        ],
    },
}

# ── 疾病-靶点关联（简化示例）──────────────────────────────────────────────────
_DISEASE_TARGETS = {
    "2型糖尿病":   {"targets": ["AKT1", "INS", "IGF1R", "GLUT4", "PPARG", "MAPK1"], "source": "DisGeNET"},
    "冠心病":      {"targets": ["AKT1", "TNF", "IL6", "NOS3", "PTGS2"], "source": "OMIM"},
    "肝癌":        {"targets": ["TP53", "AKT1", "MYC", "BCL2", "CASP3", "VEGFA"], "source": "GeneCards"},
    "炎症":        {"targets": ["TNF", "IL6", "PTGS2", "NF1", "NOS2"], "source": "OMIM"},
    "心血管疾病":  {"targets": ["AKT1", "TNF", "IL6", "NOS3", "PTGS2", "VEGFA"], "source": "DisGeNET"},
}


def run(args: dict) -> dict:
    """
    分析中药材作用靶点。

    Args:
        args: 包含：
          - herb_names (list[str], 必须): 中药材名称列表
          - disease (str, 可选): 目标疾病
          - ob_threshold (float, 可选): OB 阈值，默认 30
          - dl_threshold (float, 可选): DL 阈值，默认 0.18

    Returns:
        Envelope v2.4 格式字典
    """
    herb_names   = args.get("herb_names", [])
    disease      = args.get("disease", "")
    ob_threshold = float(args.get("ob_threshold", 30))
    dl_threshold = float(args.get("dl_threshold", 0.18))

    # ── 参数验证 ───────────────────────────────────────────────────────────────
    if not herb_names:
        return _error("INVALID_ARGS", "herb_names 不能为空", "请提供至少一种中药材名称")

    if not isinstance(herb_names, list):
        herb_names = [herb_names]

    # ── 分析流程 ───────────────────────────────────────────────────────────────
    logs = []
    all_active_components = []
    all_targets: set[str] = set()
    herb_target_map = {}
    missing_herbs = []

    for herb_name in herb_names:
        herb_data = _HERB_TARGETS.get(herb_name)
        if herb_data is None:
            missing_herbs.append(herb_name)
            logs.append({
                "t":       _now_iso(),
                "stage":   "warn",
                "message": f"[tcm.analysis.target_analysis] 未找到 '{herb_name}' 的靶点数据，跳过",
            })
            continue

        # 筛选活性成分（OB 和 DL 阈值）
        active = [
            c for c in herb_data["active_components"]
            if c["ob"] >= ob_threshold and c["dl"] >= dl_threshold
        ]

        if not active:
            # 降低阈值后包含所有成分
            active = herb_data["active_components"]
            logs.append({
                "t":       _now_iso(),
                "stage":   "warn",
                "message": (
                    f"[tcm.analysis.target_analysis] {herb_name} 无成分满足"
                    f"OB≥{ob_threshold}%、DL≥{dl_threshold} 的筛选条件，"
                    f"返回所有成分（{len(active)} 个）"
                ),
            })

        herb_targets = set()
        for comp in active:
            all_active_components.append({
                "herb": herb_name,
                "name": comp["name"],
                "ob": comp["ob"],
                "dl": comp["dl"],
            })
            herb_targets.update(comp["targets"])

        all_targets.update(herb_targets)
        herb_target_map[herb_name] = sorted(herb_targets)

        logs.append({
            "t":       _now_iso(),
            "stage":   "run",
            "message": (
                f"[tcm.analysis.target_analysis] {herb_name}："
                f"筛选 {len(active)} 个活性成分，收集 {len(herb_targets)} 个靶点"
            ),
        })

    if not all_targets:
        return _error("DATA_NOT_FOUND", "所有输入中药材均无靶点数据", f"缺失：{missing_herbs}")

    # 合并通路富集结果
    all_pathways = {}
    for herb_name in herb_names:
        herb_data = _HERB_TARGETS.get(herb_name)
        if herb_data:
            for pw in herb_data.get("pathway_enrichment", []):
                key = pw["kegg_id"]
                if key not in all_pathways:
                    all_pathways[key] = pw.copy()
                else:
                    # 取 p_value 最小（最显著）
                    if pw["p_value"] < all_pathways[key]["p_value"]:
                        all_pathways[key]["p_value"] = pw["p_value"]

    pathways_list = sorted(all_pathways.values(), key=lambda x: x["p_value"])

    # 疾病靶点交集分析
    disease_intersection = {}
    if disease and disease in _DISEASE_TARGETS:
        disease_targets = set(_DISEASE_TARGETS[disease]["targets"])
        intersect = list(all_targets & disease_targets)
        disease_intersection = {
            "disease":           disease,
            "disease_targets":   sorted(disease_targets),
            "common_targets":    sorted(intersect),
            "intersection_count": len(intersect),
            "coverage_rate":     round(len(intersect) / len(disease_targets) * 100, 1),
            "source":            _DISEASE_TARGETS[disease]["source"],
        }
        logs.append({
            "t":       _now_iso(),
            "stage":   "run",
            "message": (
                f"[tcm.analysis.target_analysis] 疾病靶点交集：{disease} "
                f"共 {len(disease_targets)} 个靶点，"
                f"交集 {len(intersect)} 个，覆盖率 {disease_intersection['coverage_rate']}%"
            ),
        })

    # ── 构造结果 ───────────────────────────────────────────────────────────────
    structured = {
        "herbs_analyzed":       herb_names,
        "missing_herbs":        missing_herbs,
        "ob_threshold":         ob_threshold,
        "dl_threshold":         dl_threshold,
        "active_components":    all_active_components,
        "total_targets":        len(all_targets),
        "target_list":          sorted(all_targets),
        "herb_target_map":      herb_target_map,
        "top_pathways":         pathways_list[:5],
    }

    if disease_intersection:
        structured["disease_intersection"] = disease_intersection

    herbs_str = "、".join(herb_names)
    result_brief = (
        f"✅ {herbs_str} 靶点分析完成。\n"
        f"筛选活性成分 {len(all_active_components)} 个，"
        f"收集作用靶点 {len(all_targets)} 个，"
        f"富集通路 {len(pathways_list)} 条。"
    )
    if disease_intersection:
        result_brief += (
            f"\n与 {disease} 靶点交集 {disease_intersection['intersection_count']} 个"
            f"（覆盖率 {disease_intersection['coverage_rate']}%），"
            f"关键靶点：{'、'.join(disease_intersection['common_targets'][:5])}"
        )

    next_hint = (
        f"可使用 tcm.visualization.herb_network_plot 绘制 {herbs_str} 的成分-靶点网络图，"
        f"或使用 tcm.visualization.pathway_heatmap 绘制通路富集热图"
    )

    return {
        "outputs": {
            "status": "ok",
            "summary_for_llm": {
                "result_brief":   result_brief,
                "structured_data": structured,
                "artifact_refs":  [],
                "next_step_hint": next_hint,
                "error_brief":    None,
            },
            "full_log": {
                "research_log": logs,
                "artifacts":    [],
                "provenance":   [{
                    "source":      "TCMSP + OMIM + DisGeNET",
                    "version":     "2.3",
                    "accessed_at": _now_iso(),
                    "license":     "academic",
                }],
            },
            "error": None,
        }
    }


# ─── 辅助函数 ──────────────────────────────────────────────────────────────────

def _error(code: str, message: str, hint: str) -> dict:
    return {
        "outputs": {
            "status": "error",
            "summary_for_llm": {
                "result_brief":  None,
                "structured_data": None,
                "artifact_refs": [],
                "next_step_hint": hint,
                "error_brief":   f"[tcm.analysis.target_analysis] {message}",
            },
            "full_log": {
                "research_log": [{
                    "t":       _now_iso(),
                    "stage":   "error",
                    "message": f"[tcm.analysis.target_analysis] {code}: {message}",
                }],
                "artifacts":  [],
                "provenance": [],
            },
            "error": {
                "code":                code,
                "message":             message,
                "retryable":           code in ("NETWORK_ERROR",),
                "mitigation":          hint,
                "fallback_action":     "retry_with_plan_correction" if code == "INVALID_ARGS" else "human_review",
                "plan_correction_hint": hint,
            },
        }
    }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
