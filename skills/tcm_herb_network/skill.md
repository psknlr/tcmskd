---
name: "tcm.analysis.herb_similarity"
category: "analysis"
description: "计算中药材之间的相似度，基于共同活性成分和靶点的 Jaccard 相似系数"
when_to_use: "当用户需要分析中药材之间的相关性或寻找功能相似的替代药材时使用。适用于：1) 计算两味中药的相似度；2) 在一组中药中找出最相似的配对；3) 基于功效相似性推荐替代药材"
version: "1.0.0"
author: "Biomni TCM Team"
tags: ["tcm", "analysis", "similarity", "jaccard", "clustering"]
requires: ["tcm.database.herb_query", "tcm.analysis.target_analysis"]
enabled: true
input_schema:
  type: "object"
  required: ["herb_names"]
  properties:
    herb_names:
      type: "array"
      items:
        type: "string"
      minItems: 2
      description: "中药材名称列表（至少 2 种）"
    similarity_method:
      type: "string"
      enum: ["jaccard_targets", "jaccard_components", "combined"]
      default: "combined"
      description: "相似度计算方法：基于靶点/成分/综合"
output_schema:
  type: "object"
  description: "相似度矩阵和配对相似度列表"
---

# tcm.analysis.herb_similarity

中药材相似度分析 Skill。

## 相似度计算方法

**Jaccard 相似系数**：
```
similarity(A, B) = |A ∩ B| / |A ∪ B|
```

- `jaccard_targets`：基于共同作用靶点
- `jaccard_components`：基于共同活性成分
- `combined`：靶点相似度 × 0.6 + 成分相似度 × 0.4

## 使用时机

- "黄芪和人参有多相似？"
- "帮我分析这五味药材的亲缘关系"
- "有没有功效类似黄芪的其他中药？"
- "复方中黄芪和当归是否具有协同效应？"
