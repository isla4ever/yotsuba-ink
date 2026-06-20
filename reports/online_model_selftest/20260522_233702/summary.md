# TokenHub 线上模型端标准自测报告

- 时间：20260522_233702
- 隔离 Wiki：codex_selftest/online_20260522_233702
- 服务模式：online
- TokenHub Base URL：https://tokenhub.tencentmaas.com/v1
- 质量阶段通过数：6
- Fail：3
- Warn：0

## 任务模型映射
```json
{
  "info_recommend": {
    "model": "deepseek-v4-flash",
    "reasoning_effort": "low",
    "thinking": "enabled",
    "max_tokens": 1800,
    "temperature": 0.38,
    "top_p": 0.9,
    "stream": false
  },
  "summary": {
    "model": "deepseek-v4-flash",
    "reasoning_effort": "low",
    "thinking": "enabled",
    "max_tokens": 1200,
    "temperature": 0.38,
    "top_p": 0.9,
    "stream": false
  },
  "outline": {
    "model": "deepseek-v4-flash",
    "reasoning_effort": "low",
    "thinking": "enabled",
    "max_tokens": 1600,
    "temperature": 0.38,
    "top_p": 0.9,
    "stream": false
  },
  "detail_outline": {
    "model": "deepseek-v4-pro",
    "reasoning_effort": "low",
    "thinking": "enabled",
    "max_tokens": 2400,
    "temperature": 0.38,
    "top_p": 0.9,
    "stream": false
  },
  "text": {
    "model": "deepseek-v4-flash",
    "reasoning_effort": "low",
    "thinking": "disabled",
    "max_tokens": 3600,
    "temperature": 0.64,
    "top_p": 0.9,
    "stream": true
  },
  "text_first_chapter": {
    "model": "deepseek-v4-flash",
    "reasoning_effort": "low",
    "thinking": "disabled",
    "max_tokens": 4200,
    "temperature": 0.64,
    "top_p": 0.9,
    "stream": true
  },
  "text_non_first_chapter": {
    "model": "deepseek-v4-flash",
    "reasoning_effort": "low",
    "thinking": "disabled",
    "max_tokens": 4200,
    "temperature": 0.64,
    "top_p": 0.9,
    "stream": true
  }
}
```

## 性能摘要
| 阶段 | 状态 | 耗时(s) | 首内容(s) | 长度 | 推理长度 | 模型 |
|---|---:|---:|---:|---:|---:|---|
| info_recommend | pass / 200 | 29.15 |  | 1308 |  | deepseek-v4-flash |
| summary | fail / 500 | 22.46 |  |  |  |  |
| outline | pass / 200 | 53.46 |  | 1639 |  | deepseek-v4-flash |
| detail_outline | pass / 200 | 32.26 |  | 1248 |  | deepseek-v4-pro |
| text_first_chapter_chapter_1 | pass / 200 | 35.23 | 6.73 | 3472 | 0 |  |
| text_non_first_chapter_chapter_2 | pass / 200 | 45.49 | 4.38 | 4137 | 0 |  |
| text_non_first_chapter_chapter_3 | pass / 200 | 57.73 | 8.17 | 6674 | 0 |  |

## 章节观察
- 第1章：长度 3472；开头：# 第一章 雨从傍晚六点开始下，到夜里十一点还没停。 林叙白站在旧城档案馆对面的骑楼下，风衣领子竖到最高，雨水顺着帽檐滴成一条断续的线。他盯着三楼那扇窗户——档案室的灯不该亮着，这个点连值班保安都只在一楼巡逻，整栋楼的照明系统在晚上九点后会自动切到节能模式，只保留走廊应急灯。 但那扇窗透出的光不是应急灯的冷白色，是暖黄，像有人开了台灯。 林叙白看了眼手机，十
- 第2章：长度 4137；开头：# 第二章 雨砸在铁皮屋顶上，像有人从高处往下倾倒碎石。 林叙白站在临港旧货码头废弃调度室的门口，雨水从破损的屋檐灌下来，在他脚边汇成一条浑浊的细流。他抬手抹了一把脸上的水，目光落在屋内唯一的光源上——乔鸣潮蹲在一只倒扣的木箱旁，老式手电筒搁在箱面上，锥形的光柱打在他面前摊开的港区巡逻地图上。 地图缺了一角，边缘被水渍浸得发软，墨绿色的线条在潮湿的纸面上洇开
- 第3章：长度 6674；开头：# 第三章 旧档案馆的地下文献修复室藏在主楼最底层，要穿过三道防火门和一条被管道占据的走廊才能抵达。林叙白推开最后一道铁门时，日光灯管的镇流器正发出低频的嗡鸣，像某种被困在墙壁里的生物在持续呻吟。 空气中是纸张霉变和化学药水混合的气味，浓得几乎能尝出苦味。墙壁上每隔两米挂着一只活性炭包，有些已经发黑发硬，像干瘪的器官标本。修复室不大，四张长桌拼成矩形，桌上堆

## 初步结论
- 自测未完全通过，详见 issues.md。
- 后续优化重点：让细纲输出显式携带伏笔状态，正文 prompt 固化“前章事实-本章目标-本章回收-章末新增钩子”结构，降低模板化兜底污染。