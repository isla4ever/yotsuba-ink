# Issues

- [fail] summary: 出现污染：```
- [fail] detail_outline: HTTP 500: Internal Server Error
- [fail] detail_outline: 细纲不能解析为至少 3 章列表
- [fail] detail_outline: 缺少伏笔/钩子/线索

# Optimization Backlog

- 修复/压缩细纲归一化里的硬兜底模板，优先保留模型有效输出，只在解析失败时做结构修复。
- 为章节连续性增加机器可读状态：上一章新增线索、本章必须回收、未解决问题。
- 对正文输出增加后验检查：承接上一章关键名词、人物动机不漂移、章末钩子不空泛。