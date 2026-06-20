# TokenHub 线上模型端标准自测报告

- 时间：20260522_191946
- 隔离 Wiki：codex_selftest/online_20260522_191946
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
    "max_tokens": 1800,
    "temperature": 0.58,
    "top_p": 0.95
  },
  "summary": {
    "model": "deepseek-v4-flash",
    "reasoning_effort": "low",
    "max_tokens": 1200,
    "temperature": 0.48,
    "top_p": 0.95
  },
  "outline": {
    "model": "deepseek-v4-flash",
    "reasoning_effort": "low",
    "max_tokens": 1600,
    "temperature": 0.46,
    "top_p": 0.95
  },
  "detail_outline": {
    "model": "deepseek-v4-pro",
    "reasoning_effort": "low",
    "max_tokens": 2400,
    "temperature": 0.42,
    "top_p": 0.95
  },
  "text": {
    "model": "deepseek-v4-flash",
    "reasoning_effort": "low",
    "max_tokens": 3600,
    "temperature": 0.32,
    "top_p": 0.95
  },
  "text_first_chapter": {
    "model": "deepseek-v4-flash",
    "reasoning_effort": "low",
    "max_tokens": 4200,
    "temperature": 0.32,
    "top_p": 0.95
  },
  "text_non_first_chapter": {
    "model": "deepseek-v4-flash",
    "reasoning_effort": "low",
    "max_tokens": 4200,
    "temperature": 0.32,
    "top_p": 0.95
  }
}
```

## 性能摘要
| 阶段 | 状态 | 耗时(s) | 首内容(s) | 长度 | 推理长度 | 模型 |
|---|---:|---:|---:|---:|---:|---|
| info_recommend | pass / 200 | 61.03 |  | 1308 |  | deepseek-v4-flash |
| summary | pass / 200 | 23.55 |  | 432 |  | deepseek-v4-flash |
| outline | pass / 200 | 37.9 |  | 1572 |  | deepseek-v4-flash |
| detail_outline | pass / 200 | 91.5 |  | 1580 |  | deepseek-v4-pro |
| text_first_chapter_chapter_1 | pass / 200 | 59.55 | 9.82 | 6990 | 814 |  |
| text_non_first_chapter_chapter_2 | pass / 200 | 75.62 | 18.63 | 6865 | 1887 |  |
| text_non_first_chapter_chapter_3 | pass / 200 | 58.64 | 12.9 | 4774 | 969 |  |

## 章节观察
- 第1章：长度 6990；开头：# 雾港潮痕档案 ## 第一章 灰潮失录 雨在傍晚六点十七分准时落下来。 林叙白站在旧档案馆门口的雨棚下，看着雨水沿着铸铁排水管的裂缝淌成一条细线，砸在台阶上溅起灰白色的水花。海港都市的六月总是这样，雨来得毫无预兆，空气里混着咸腥和铁锈的气味，像是有什么东西正在这座城市的皮肤下层缓慢腐烂。 手机震动了一下。 他没有立刻看，而是先把手里的烟按灭在墙角的铁皮垃圾
- 第2章：长度 6865；开头：# 雾港潮痕档案 ## 第二章 裂痕索引 林叙白推开档案科的门时，灯还亮着。 三排铁皮档案柜整整齐齐地立在房间里，日光灯发出嗡嗡的低频震动，空气中的灰尘在光柱里缓慢旋转。一切看起来没有任何异常——桌上的茶杯还冒着热气，显示器停留在档案查询系统的登录界面，光标一闪一闪地等着谁输密码。 但值班的人不在。 林叙白站在门口，没有立刻进去。他的目光快速扫过房间：椅子被
- 第3章：长度 4774；开头：# 雾港潮痕档案 ## 第三章 灰潮失录 深夜的旧档案馆外围，雨刚停。 林叙白绕过停车场栅栏时鞋底踩进积水，水花溅上裤脚，他没低头去看。手机屏幕的蓝光在他手里亮着又熄灭，熄灭又亮起——乔鸣潮发来的定位在屏幕上闪烁，距离他还有不到两百米，位于档案馆西侧那扇常年锁死的铁门背后。 那是他们已经废弃五年以上的消防通道。 林叙白停下脚步，把手机的屏幕亮度调到最低，看了

## 初步结论
- 自测链路跑通。
- 后续优化重点：让细纲输出显式携带伏笔状态，正文 prompt 固化“前章事实-本章目标-本章回收-章末新增钩子”结构，降低模板化兜底污染。