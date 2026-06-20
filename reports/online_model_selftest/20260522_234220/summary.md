# TokenHub 线上模型端标准自测报告

- 时间：20260522_234220
- 隔离 Wiki：codex_selftest/online_20260522_234220
- 服务模式：online
- TokenHub Base URL：https://tokenhub.tencentmaas.com/v1
- 质量阶段通过数：7
- Fail：0
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
| info_recommend | pass / 200 | 25.53 |  | 1308 |  | deepseek-v4-flash |
| summary | pass / 200 | 13.65 |  | 375 |  | deepseek-v4-flash |
| outline | pass / 200 | 51.7 |  | 2722 |  | deepseek-v4-flash |
| detail_outline | pass / 200 | 44.92 |  | 1295 |  | deepseek-v4-pro |
| text_first_chapter_chapter_1 | pass / 200 | 18.02 | 3.23 | 2895 | 0 |  |
| text_non_first_chapter_chapter_2 | pass / 200 | 36.62 | 4.42 | 4572 | 0 |  |
| text_non_first_chapter_chapter_3 | pass / 200 | 39.66 | 6.06 | 4850 | 0 |  |

## 章节观察
- 第1章：长度 2895；开头：# 第一章 雨落在海港都市的废弃码头时，声音是不一样的。 不是那种砸在柏油路面上的清脆碎裂，而是落在铁皮棚顶、积水洼地和生锈集装箱上的沉闷回响——像有什么东西被反复碾压，却始终碾不碎。 林叙白站在三号仓库的屋檐下，外套肩膀已经湿透了。他没有往里躲，只是盯着手机屏幕上那条未读消息，拇指悬在屏幕上方，迟迟没有点开。 加密信息。 发件人显示为空。 他知道这意味着什
- 第2章：长度 4572；开头：# 第二章 旧档案馆地下层的空气常年带着一股纸霉和金属混合的气味，像被时间腌透了。 林叙白推开档案修复室的门时，周叙川正坐在工作台前，台灯的光圈把他的手和面前那本摊开的日志照得雪亮，周围全是暗的。他戴着白色棉质手套，镊子尖夹着一片几乎透明的修复纸，动作慢得像在拆弹。 “你提前了。”周叙川没抬头，声音平静得像在说今天天气不错。 “你也没关门。”林叙白把沾着雨水
- 第3章：长度 4850；开头：# 第三章 废弃潮汐实验站的楼梯踩上去像踩在一层随时会塌的锈壳上。 乔鸣潮打着手电走在前面，光束在铁质台阶上切出一块块明暗交错的格子。空气里盐分和机油的味道混在一起，越往下越浓，像有什么东西在底层腐烂了很久。她另一只手攥着许照临留下的那张便签纸——纸条是从档案修复室的门缝里塞出来的，上面只有一行字：潮汐站B3，别告诉林叙白。 她当然没听。 但她也没让林叙白跟

## 初步结论
- 自测链路跑通。
- 后续优化重点：让细纲输出显式携带伏笔状态，正文 prompt 固化“前章事实-本章目标-本章回收-章末新增钩子”结构，降低模板化兜底污染。