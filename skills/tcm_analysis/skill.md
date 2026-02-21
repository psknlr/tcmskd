---
name: "tcm.analysis.target_analysis"
category: "analysis"
description: "分析中药材或方剂的作用靶点，识别关键靶点和相关信号通路"
when_to_use: "当用户需要进行中药网络药理学分析时使用，包括：1) 分析单味药的靶点谱；2) 分析复方的共同靶点；3) 识别与特定疾病相关的靶点；4) 发现潜在的作用机制"
version: "1.0.0"
author: "Biomni TCM Team"
tags: ["tcm", "analysis", "target", "network-pharmacology", "pathway"]
requires: ["tcm.database.herb_query"]
enabled: true
input_schema:
  type: "object"
  required: ["herb_names"]
  properties:
    herb_names:
      type: "array"
      items:
        type: "string"
      description: "中药材名称列表，可单味或多味"
    disease:
      type: "string"
      description: "目标疾病名称（可选，用于靶点-疾病关联分析）"
    ob_threshold:
      type: "number"
      default: 30
      description: "口服生物利用度阈值（%），用于筛选活性成分"
    dl_threshold:
      type: "number"
      default: 0.18
      description: "类药性阈值，用于筛选活性成分"
output_schema:
  type: "object"
  description: "靶点分析结果 Envelope，包含靶点列表和通路富集结果"
---

# tcm.analysis.target_analysis

中药网络药理学靶点分析 Skill。

## 分析流程

1. 根据 OB 和 DL 阈值筛选活性成分
2. 收集各活性成分对应的作用靶点
3. 构建成分-靶点网络
4. 进行通路富集分析（KEGG/GO）
5. 若提供疾病名称，进行靶点-疾病交集分析

## 数据来源

- TCMSP（成分-靶点数据）
- Swiss Target Prediction（靶点预测）
- OMIM/GeneCards（疾病靶点）
- KEGG（通路数据库）

## 使用时机

- "分析黄芪的靶点"
- "黄芪当归共同靶点有哪些？"
- "人参治疗糖尿病的可能靶点和通路"
- "复方黄芪汤的网络药理学分析"

## 组合示例

```python
# 先查询基本信息
herb_query_result = skills.run("tcm.database.herb_query", {"herb_name": "黄芪"})
# 再进行靶点分析
target_result = skills.run("tcm.analysis.target_analysis", {
    "herb_names": ["黄芪", "当归"],
    "disease": "2型糖尿病",
    "ob_threshold": 30,
    "dl_threshold": 0.18
})
```
