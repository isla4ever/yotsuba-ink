# TokenHub 线上模型端标准自测报告

- 时间：20260522_232332
- 隔离 Wiki：codex_selftest/online_20260522_232332
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
| info_recommend | pass / 200 | 23.03 |  | 1308 |  | deepseek-v4-flash |
| summary | pass / 200 | 23.61 |  | 292 |  | deepseek-v4-flash |
| outline | pass / 200 | 41.65 |  | 1372 |  | deepseek-v4-flash |
| detail_outline | pass / 200 | 75.64 |  | 1263 |  | deepseek-v4-pro |
| text_first_chapter_chapter_1 | pass / 200 | 45.17 | 8.89 | 4604 | 752 |  |
| text_non_first_chapter_chapter_2 | pass / 200 | 53.22 | 13.75 | 4639 | 1222 |  |
| text_non_first_chapter_chapter_3 | pass / 200 | 75.33 | 14.91 | 6794 | 1134 |  |

## 章节观察
- 第1章：长度 4604；开头：# 雾港潮痕档案 ## 第一章 雨砸在旧档案馆的铁皮屋顶上，像有人在天上倾倒碎石子。 林叙白把湿透的伞靠在墙角，甩了甩袖口的水珠，从大衣内袋掏出证件递给值班台后面的老头。老头戴着老花镜，目光从镜框上方翻出来，扫了他一眼，又落回证件照片上，足足比对了五秒。 “林叙白。”老头念出名字时的语气像是在念一具尸体的编号，“三号阅览室，E区，提前预约的。你晚了四十分钟。
- 第2章：长度 4639；开头：# 第二章 雨势在凌晨三点转为连绵的毛毛细雨，海港都市的滨海旧仓库区笼罩在一片灰蒙蒙的水雾里。林叙白把车停在距离坐标点两百米外的废弃岗亭旁，熄火后没有立刻下车，而是先透过挡风玻璃观察了一分钟。 锈蚀的集装箱以各种角度堆叠在水泥地上，像被巨人随手丢弃的积木。有几盏路灯坏了，剩下的光线昏黄而稀薄，在湿漉漉的地面上投出破碎的光斑。程见深发来的坐标指向深处一个蓝色集
- 第3章：长度 6794；开头：# 第三章 雨落在行政档案总库的玻璃幕墙上，被冷光切割成无数条垂直的水线。 林叙白站在侧门入口的雨棚下，看着乔鸣潮把工作证贴在读卡器上。绿灯亮起的瞬间，门锁发出一声低沉的嗡鸣。乔鸣潮推开门，侧身让他先进，动作自然得像进出自家办公室。 “审查组的工牌我用的是真信息改的——”乔鸣潮压低声音，“万一被拦，你就说是市审计局派来复查冻结期流程的，话少说，档案编号记住三

## 初步结论
- 自测链路跑通。
- 后续优化重点：让细纲输出显式携带伏笔状态，正文 prompt 固化“前章事实-本章目标-本章回收-章末新增钩子”结构，降低模板化兜底污染。