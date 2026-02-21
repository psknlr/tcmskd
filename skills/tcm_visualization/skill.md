---
name: "tcm.visualization.herb_network_plot"
category: "visualization"
description: "绘制中药材的成分-靶点网络图，支持 PNG/SVG 格式输出"
when_to_use: "当用户需要可视化中药材的作用网络时使用，包括：1) 绘制单味药的成分-靶点网络；2) 绘制多味药的共同靶点网络；3) 叠加疾病靶点的三层网络图（药材-成分-靶点-疾病）"
version: "1.0.0"
author: "Biomni TCM Team"
tags: ["tcm", "visualization", "network", "plot", "graph"]
requires: ["tcm.analysis.target_analysis"]
enabled: true
input_schema:
  type: "object"
  required: ["herb_names"]
  properties:
    herb_names:
      type: "array"
      items:
        type: "string"
      description: "中药材名称列表"
    target_data:
      type: "object"
      description: "由 tcm.analysis.target_analysis 返回的靶点分析结果（可选，避免重复查询）"
    output_format:
      type: "string"
      enum: ["png", "svg", "both"]
      default: "png"
      description: "输出图片格式"
    output_path:
      type: "string"
      default: "./workspace/network_plot.png"
      description: "输出文件路径"
    layout:
      type: "string"
      enum: ["spring", "circular", "shell", "kamada_kawai"]
      default: "spring"
      description: "网络布局算法"
    max_nodes:
      type: "integer"
      default: 50
      description: "最大显示节点数（超过时截取最重要的节点）"
output_schema:
  type: "object"
  description: "网络图输出 Envelope，包含图片文件路径"
---

# tcm.visualization.herb_network_plot

中药材成分-靶点网络可视化 Skill。

## 可视化层次

**三层网络结构**：
```
中药材 (Herb)
    ↓
活性成分 (Active Component)
    ↓
作用靶点 (Target Gene)
    ↓ (可选)
疾病 (Disease)
```

## 节点颜色编码

- 橙色：中药材节点
- 蓝色：活性成分节点
- 绿色：靶点基因节点
- 红色（可选）：疾病节点

## 输出格式

- PNG：适合报告和展示
- SVG：适合高质量印刷和进一步编辑

## 依赖

运行此 Skill 前，建议先运行 `tcm.analysis.target_analysis` 获取靶点数据，
可将结果直接传入 `target_data` 参数避免重复查询。

## 使用时机

- "帮我画一个黄芪的靶点网络图"
- "用网络图展示黄芪当归的共同靶点"
- "绘制复方的成分-靶点-疾病三层网络"
