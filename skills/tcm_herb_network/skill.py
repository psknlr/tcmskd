# skills/tcm_herb_network/skill.py  v1.0.0
"""
TCM 中药材相似度分析 Skill。

基于共同靶点和活性成分的 Jaccard 相似系数计算中药材相似度。
"""

from datetime import datetime, timezone
from itertools import combinations

# ── 共享数据（与 tcm_analysis/skill.py 共享）──────────────────────────────────
_HERB_DATA = {
    "黄芪":  {"targets": {"TP53", "AKT1", "VEGFA", "TNF", "IL6", "ESR1", "EGFR"},
              "components": {"黄芪甲苷", "毛蕊异黄酮", "芒柄花素", "黄芪皂苷II"}},
    "当归":  {"targets": {"PTGS2", "PTGS1", "NOS2", "AKT1", "TRPV1", "CALM1", "CACNA1C"},
              "components": {"阿魏酸", "Z-藁本内酯", "正丁烯基苯酞"}},
    "人参":  {"targets": {"AKT1", "INS", "IGF1R", "GLUT4", "NOS3", "BCL2", "CASP3", "PPARG"},
              "components": {"人参皂苷Rb1", "人参皂苷Rg1", "人参皂苷Re"}},
    "甘草":  {"targets": {"TNF", "IL6", "PTGS2", "MAPK1", "ESR1", "AKT1", "NOS2"},
              "components": {"甘草酸", "甘草苷", "甘草素"}},
    "丹参":  {"targets": {"TP53", "AKT1", "BCL2", "CASP3", "MYC", "MAPK1", "TNF", "IL6", "NOS3", "PTGS2"},
              "components": {"丹参酮IIA", "丹酚酸B", "丹参素"}},
}


def run(args: dict) -> dict:
    """
    计算中药材相似度。

    Args:
        args: 包含：
          - herb_names (list[str], 必须): 至少 2 种中药材
          - similarity_method (str, 可选): 相似度方法

    Returns:
        Envelope v2.4 格式字典，包含相似度矩阵
    """
    herb_names        = args.get("herb_names", [])
    similarity_method = args.get("similarity_method", "combined")

    # ── 参数验证 ───────────────────────────────────────────────────────────────
    if not isinstance(herb_names, list) or len(herb_names) < 2:
        return _error("INVALID_ARGS", "herb_names 至少需要 2 种中药材", "请提供至少 2 种中药材名称")

    # ── 计算相似度矩阵 ─────────────────────────────────────────────────────────
    logs = []
    similarity_pairs = []
    missing = [h for h in herb_names if h not in _HERB_DATA]

    if missing:
        logs.append({
            "t":       _now_iso(),
            "stage":   "warn",
            "message": f"[tcm.analysis.herb_similarity] 未找到以下中药材数据：{missing}",
        })

    valid_herbs = [h for h in herb_names if h in _HERB_DATA]
    if len(valid_herbs) < 2:
        return _error("DATA_NOT_FOUND", "有效中药材不足 2 种", f"可用中药材：{list(_HERB_DATA.keys())}")

    for ha, hb in combinations(valid_herbs, 2):
        data_a = _HERB_DATA[ha]
        data_b = _HERB_DATA[hb]

        target_sim = _jaccard(data_a["targets"], data_b["targets"])
        comp_sim   = _jaccard(data_a["components"], data_b["components"])

        if similarity_method == "jaccard_targets":
            final_sim = target_sim
        elif similarity_method == "jaccard_components":
            final_sim = comp_sim
        else:  # combined
            final_sim = round(target_sim * 0.6 + comp_sim * 0.4, 4)

        common_targets    = sorted(data_a["targets"] & data_b["targets"])
        common_components = sorted(data_a["components"] & data_b["components"])

        similarity_pairs.append({
            "herb_a":           ha,
            "herb_b":           hb,
            "similarity":       final_sim,
            "target_similarity":     target_sim,
            "component_similarity":  comp_sim,
            "common_targets":        common_targets,
            "common_components":     common_components,
            "common_target_count":   len(common_targets),
            "common_component_count": len(common_components),
        })

        logs.append({
            "t":       _now_iso(),
            "stage":   "run",
            "message": (
                f"[tcm.analysis.herb_similarity] {ha} vs {hb}："
                f"综合相似度={final_sim}，靶点相似度={target_sim}，成分相似度={comp_sim}"
            ),
        })

    # 排序（相似度从高到低）
    similarity_pairs.sort(key=lambda x: x["similarity"], reverse=True)

    top_pair = similarity_pairs[0]
    result_brief = (
        f"✅ {len(valid_herbs)} 种中药材相似度分析完成。\n"
        f"最相似配对：{top_pair['herb_a']} & {top_pair['herb_b']}（相似度 {top_pair['similarity']}），"
        f"共同靶点 {top_pair['common_target_count']} 个，"
        f"共同活性成分 {top_pair['common_component_count']} 个。\n"
        f"计算方法：{similarity_method}"
    )

    return {
        "outputs": {
            "status": "ok",
            "summary_for_llm": {
                "result_brief":   result_brief,
                "structured_data": {
                    "similarity_pairs":    similarity_pairs,
                    "herbs_analyzed":      valid_herbs,
                    "missing_herbs":       missing,
                    "similarity_method":   similarity_method,
                    "most_similar_pair":   f"{top_pair['herb_a']} & {top_pair['herb_b']} ({top_pair['similarity']})",
                    "least_similar_pair":  (
                        f"{similarity_pairs[-1]['herb_a']} & {similarity_pairs[-1]['herb_b']}"
                        f" ({similarity_pairs[-1]['similarity']})"
                    ) if len(similarity_pairs) > 1 else None,
                },
                "artifact_refs":  [],
                "next_step_hint": "可使用 tcm.visualization.herb_network_plot 将相似度关系可视化为网络图",
                "error_brief":    None,
            },
            "full_log": {
                "research_log": logs,
                "artifacts":    [],
                "provenance":   [],
            },
            "error": None,
        }
    }


# ─── 辅助函数 ──────────────────────────────────────────────────────────────────

def _jaccard(set_a: set, set_b: set) -> float:
    """计算两个集合的 Jaccard 相似系数。"""
    if not set_a and not set_b:
        return 1.0
    union = set_a | set_b
    if not union:
        return 0.0
    return round(len(set_a & set_b) / len(union), 4)


def _error(code: str, message: str, hint: str) -> dict:
    return {
        "outputs": {
            "status": "error",
            "summary_for_llm": {
                "result_brief":  None,
                "structured_data": None,
                "artifact_refs": [],
                "next_step_hint": hint,
                "error_brief":   f"[tcm.analysis.herb_similarity] {message}",
            },
            "full_log": {
                "research_log": [{
                    "t":       _now_iso(),
                    "stage":   "error",
                    "message": f"[tcm.analysis.herb_similarity] {code}: {message}",
                }],
                "artifacts":  [],
                "provenance": [],
            },
            "error": {
                "code":                code,
                "message":             message,
                "retryable":           code == "INVALID_ARGS",
                "mitigation":          hint,
                "fallback_action":     "retry_with_plan_correction" if code == "INVALID_ARGS" else "human_review",
                "plan_correction_hint": hint,
            },
        }
    }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
