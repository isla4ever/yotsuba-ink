# TokenHub 线上模型端标准自测报告

- 时间：20260522_153504
- 隔离 Wiki：codex_selftest/online_20260522_153504
- 服务模式：online
- TokenHub Base URL：https://tokenhub.tencentmaas.com/v1
- 质量阶段通过数：4
- Fail：5
- Warn：0

## 任务模型映射
```json
{
  "info_recommend": {
    "model": "deepseek-v4-flash",
    "reasoning_effort": "low",
    "max_tokens": 1800,
    "temperature": 0.58
  },
  "summary": {
    "model": "deepseek-v4-flash",
    "reasoning_effort": "low",
    "max_tokens": 1200,
    "temperature": 0.48
  },
  "outline": {
    "model": "deepseek-v4-flash",
    "reasoning_effort": "low",
    "max_tokens": 1600,
    "temperature": 0.46
  },
  "detail_outline": {
    "model": "deepseek-v4-pro",
    "reasoning_effort": "medium",
    "max_tokens": 2400,
    "temperature": 0.42
  },
  "text": {
    "model": "kimi-k2.6",
    "reasoning_effort": "medium",
    "max_tokens": 3600,
    "temperature": 1,
    "top_p": 0.95
  },
  "text_first_chapter": {
    "model": "kimi-k2.6",
    "reasoning_effort": "medium",
    "max_tokens": 4200,
    "temperature": 1,
    "top_p": 0.95
  },
  "text_non_first_chapter": {
    "model": "kimi-k2.6",
    "reasoning_effort": "medium",
    "max_tokens": 4200,
    "temperature": 1,
    "top_p": 0.95
  }
}
```

## 性能摘要
| 阶段 | 状态 | 耗时(s) | 首内容(s) | 长度 | 推理长度 | 模型 |
|---|---:|---:|---:|---:|---:|---|
| info_recommend | pass / 200 | 24.54 |  | 1308 |  | deepseek-v4-flash |
| summary | pass / 200 | 32.22 |  | 1034 |  | deepseek-v4-flash |
| outline | pass / 200 | 40.44 |  | 1432 |  | deepseek-v4-flash |
| detail_outline | pass / 200 | 88.22 |  | 1262 |  | deepseek-v4-pro |
| text_first_chapter_chapter_1 | fail / 200 | 251.41 | None | 0 | 6585 |  |
| text_non_first_chapter_chapter_2 | fail / 200 | 319.32 | None | 0 | 6410 |  |
| text_non_first_chapter_chapter_3 | fail / 200 | 285.95 | None | 0 | 6498 |  |

## 章节观察
- 第1章：长度 0；开头：
- 第2章：长度 0；开头：
- 第3章：长度 0；开头：

## 初步结论
- 自测未完全通过，详见 issues.md。
- 后续优化重点：让细纲输出显式携带伏笔状态，正文 prompt 固化“前章事实-本章目标-本章回收-章末新增钩子”结构，降低模板化兜底污染。