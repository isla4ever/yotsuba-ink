# Phase 26 UI 工作台视觉与交互规范

> 状态：八阶段 Artifact 信息架构已实现；本文件固定 2026-08-11 人物星图与全阶段视觉精修方向。原型图只表达布局、密度和视觉层级，生产语义始终以 `stage-artifact-contract.md`、TypeScript 合同和后端 read model 为权威。

## 1. 产品取舍

人物阶段采用 **3D 星图关系网**，不采用 3D 地球。

- 每个大星点对应一名已登记角色，连线对应 `CharacterBibleArtifact.relationships`；点击节点只同步选中档案。
- 3D 坐标、相机、节点尺寸和颜色均由确定性代码投影，可删除重建，不写入 Artifact。
- 关系拖拽只改变浏览视角，不能修改关系语义；人物、关系、弧线和首次出现窗口仍由名册、档案表单和关系矩阵编辑。
- 桌面默认星图，移动端默认名册；无 WebGL 时名册保持完整可用。
- 地球投影只适合带真实经纬度的地点网络。人物关系没有该语义，因此本阶段拒绝 `react-globe.gl` 依赖。

视觉基调是冷黑、石墨金属、中性白、青色状态与少量琥珀警告。星图是唯一高表现力区域；其余表单保持安静、紧凑和可扫描。禁止全紫/全蓝、持续自动旋转、发光边框堆叠、嵌套卡片和营销页式大标题。

## 2. 八阶段环扣

| 阶段 | 主编辑面 | 辅助投影 | 用户在此决定 | 明确不显示 |
| --- | --- | --- | --- | --- |
| `info` | 创作契约表单 | Source Pack、世界规则摘要、就绪度 | 前提、承诺、声音与人物职责需求 | 完整人物档案、质量分、原始 JSON |
| `characters` | 星图 / 分层名册 + 人物档案 | 关系矩阵、弧线、出现窗口、NPC 槽位 | 冻结人物职责、关系与弧线 | 地理地球、拖图写关系、后续阶段自由加人 |
| `summary` | 因果故事脊柱 | 高潮、结局、人物结局对账 | 全书因果和人物结局是否成立 | 重复 synopsis、自评分、全量人物编辑 |
| `outline` | 分卷节拍表 | 体量、人物窗口、线程窗口 | 卷目标、转折和卷末状态 | 新人物输入、章节正文、Wiki 写回 |
| `detail` | 章节/场景施工表 | 义务、handoff、引用覆盖 | 每章目的、场景转折和跨章交接 | Detail v1/v2/v3、Canon/Wiki 假写回 |
| `text` | 正文编辑器 | 审稿、Evidence、写回状态抽屉 | 接受、人工编辑或定向修订 | 原始 Graph State、自动删改、正文 RAG |
| `cover` | 可执行视觉 Brief | 候选资产、选择和生成回执 | Brief 与正式封面资产 | Provider payload、创作运行观察堆叠 |
| `export` | 交付清单与格式选择 | 校验、不可变回执、下载 | 章节版本、封面、元数据和格式 | 模型配置、正文生成入口 |

信息从 `info.cast_requirements` 进入 `characters`，冻结人物 id 后才能进入 `summary/outline/detail/text`；`summary` 的结局承诺进入 `outline`，卷窗口进入 `detail`，章节 handoff 顺序进入 `text`，已接受正文版本和封面资产最终进入 `export`。保存当前稿只更新候选草稿，确认按钮才通过 LangGraph decision 提交。

## 3. 人物星图交互

桌面布局：窄名册 rail、主星图、选中人物档案三列；关系矩阵与 NPC 槽位在下方使用横向账本。`星图 / 名册` 是视图分段控件，不改变运行状态。

星图运行约束：

- 使用有限 `warmupTicks/cooldownTicks`；稳定后暂停 render loop，指针进入或相机过渡时才恢复。
- 无自动旋转。静态深空点云只创建一次，卸载时从 scene 移除并显式 dispose geometry/material。
- 星点本体不常驻叠加 3D 文字 Sprite；姓名由左侧分层名册、节点 hover 和右侧选中档案显示，避免透视深度与密集关系造成文字遮挡。
- 点击节点同步名册与档案；背景点击不丢失正式选择；相机适配、缩放和聚焦不改变 Artifact。
- 390px 默认名册；用户主动进入星图时只展示全宽画布和工具栏，不把三列表单压成不可用窄列。

## 4. 原型图

以下图片由修复后的仓库指定 `gpt-image-gen` Skill 生成，用于视觉层级审阅。图片中的示例书名、示例内容和模型生成文字不是生产字段定义。

| 阶段 | 原型 |
| --- | --- |
| 创作立项 | [info.png](../assets/phase-26-ui-prototypes/info.png) |
| 人物编排 | [characters-star-map.png](../assets/phase-26-ui-prototypes/characters-star-map.png) |
| 全书梗概 | [summary.png](../assets/phase-26-ui-prototypes/summary.png) |
| 分卷大纲 | [outline.png](../assets/phase-26-ui-prototypes/outline.png) |
| 章节施工图 | [detail.png](../assets/phase-26-ui-prototypes/detail.png) |
| 正文 | [text.png](../assets/phase-26-ui-prototypes/text.png) |
| 封面 | [cover.png](../assets/phase-26-ui-prototypes/cover.png) |
| 导出 | [export.png](../assets/phase-26-ui-prototypes/export.png) |

原型不得驱动新增 Artifact 键。字段、格式选项、状态与按钮若和生产合同冲突，一律以生产合同为准，并在浏览器真实组件验收中纠正。

## 5. 验收门

1. 组件合同测试证明星图是只读投影，节点选择与档案同步，Artifact 不出现坐标字段。
2. 1440x900、1728x1100 与 390x844 无页面横向溢出；关系/NPC 宽表只在自身容器滚动。
3. 3D canvas 非空、首帧正确取景、点击可选中、缩放/适配有效；稳定后动画暂停，退出人物页后 WebGL 资源销毁。
4. 名册、表单和所有命令有键盘焦点与可访问名称；`prefers-reduced-motion` 下相机过渡为 0。
5. console 0 error / 0 warning；生产构建、CSS audit/split、全量测试和 closure audit 通过。
6. 本地服务验收后停止并确认端口关闭；只有提交推送成功后才允许恢复冻结文本 Provider 的真实链路测试。
