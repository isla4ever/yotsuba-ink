# TokenHub 线上模型端标准自测报告

- 时间：20260522_233046
- 隔离 Wiki：codex_selftest/online_20260522_233046
- 服务模式：online
- TokenHub Base URL：https://tokenhub.tencentmaas.com/v1
- 质量阶段通过数：5
- Fail：4
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
| info_recommend | pass / 200 | 30.54 |  | 1308 |  | deepseek-v4-flash |
| summary | fail / 200 | 33.61 |  | 1551 |  | deepseek-v4-flash |
| outline | pass / 200 | 40.76 |  | 3039 |  | deepseek-v4-flash |
| detail_outline | fail / 500 | 74.22 |  |  |  |  |
| text_first_chapter_chapter_1 | pass / 200 | 35.32 | 2.97 | 4164 | 0 |  |
| text_non_first_chapter_chapter_2 | pass / 200 | 35.04 | 3.49 | 3895 | 0 |  |
| text_non_first_chapter_chapter_3 | pass / 200 | 34.25 | 3.42 | 4330 | 0 |  |

## 章节观察
- 第1章：长度 4164；开头：# 第一章 潮痕 雨停了半小时，雾港的街道还泛着水光。 林叙白站在旧档案馆三楼的窗前，指间的烟燃到了滤嘴也没抽一口。玻璃上凝着水雾，他把烟头摁灭在窗台上，转身看向桌上摊开的档案袋——牛皮纸边缘已经磨得发白，封口处的火漆早在三年前就被拆开了。 三年前那场事故的结案报告，一共四十七页，他读过不下二十遍。 但今天下午乔鸣潮发来的那张照片，让其中一页的内容突然变得不
- 第2章：长度 3895；开头：# 第二章 暗流 林叙白把烟从嘴角拿下来，盯着乔鸣潮看了三秒。 “备份系统。”他重复了一遍这个词，语气里没有疑问，只是在确认什么。“你上周整理旧件——谁给你开的权限？” 乔鸣潮没有立刻回答。他从外套内袋掏出一个信封，放在桌上，推到林叙白面前。信封没封口，边角被雨水洇湿了一小块。 林叙白没碰信封，先问：“你绕过审批了？” “雾港潮痕档案的系统权限三年前就锁死了
- 第3章：长度 4330；开头：# 第三章 镜像 雨在凌晨三点停了。 林叙白没睡。他坐在办公桌前，面前摊着三张A4纸和一部手机，屏幕上是乔鸣潮发来的最后一条消息：“机房监控我调出来了，发你邮箱，自己看。” 他看了。 监控画面是灰度影像，时间戳跳动着，从凌晨一点四十分到四点二十分。画面里，机房的门开了三次。第一次是一个穿连帽衫的身影，帽檐压得很低，看不清脸，在服务器机柜前停留了大约七分钟。第

## 初步结论
- 自测未完全通过，详见 issues.md。
- 后续优化重点：让细纲输出显式携带伏笔状态，正文 prompt 固化“前章事实-本章目标-本章回收-章末新增钩子”结构，降低模板化兜底污染。