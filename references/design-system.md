# Design System

## Canonical priority

治理顺序固定为：**语义与事实 → 一页一焦点 → 可读性与对比 → 空间与重心 → 分组与对齐 → 跨页连续性 → 图表降噪 → 装饰与动效**。低层规则不得修复高层错误。

## Canvas and composition

默认画布为 1280×720、16:9；坐标与尺寸落在 8 单位网格。安全区由主题或项目覆盖，但页脚、来源和关键文字不得越界。每页必须声明 `focus`、`gravity_anchor`、`empty_space_role`、`energy` 和 `density`。留白是主动结构：它可以保护证据、建立权威、区分章节或承载情绪。

黄金比例、三分法、对称与非对称都只是候选构图工具。选择依据是内容关系、阅读距离和叙事节奏，而非数学崇拜。连续两页不得保持同样的密度、重心和版式模板；全套应形成建立、聚焦、展开、证据、收束的空间曲线。

## Hierarchy and typography

使用 L0 背景、L1 环境/媒体、L2 结构/标题、L3 主要内容/数据、L4 英雄结论。原则上每页只有一个 L4。默认最多两种字体家族、四级字号、三级字重。建议设计单位字号：Statement 52–80、Display 42–64、Title 30–42、Body 20–24、Caption 13–16；实际磅值由生产契约换算。

标题写洞察，不写“市场分析”“项目进展”等字段名。眉标只作为弱化导航，不与标题竞争。正文、图表标签、来源和限定条件分别承担语义角色。空间不足时减少词、减少类别或拆页，不自动压缩字号。

## Color direction

颜色同时承担三种明确职责：`brand` 表达品牌识别，`emotion` 建立感受，`hierarchy` 引导阅读。Direction 应记录 `color_intent: [brand, emotion, hierarchy]` 并说明当前页面哪一种职责优先。颜色同时承担情绪、层级、材质和注意力信号。主题至少提供 `background / surface / primary / secondary / accent / ink / muted`；引擎从基础色推导 panel、hairline、track、veil、ramp、series、on_dark、on_accent。Accent 默认不超过页面有效面积 5%，且每页只有一个主要强调点。优先同色相明度阶梯，不用新色相填补层级。

选择 `color_behavior` 时先确定感知目标：`quiet_neutral` 用低饱和与明度差建立安静权威；`single_signal` 用中性底与单一信号色建立决策焦点；`warm_material` 用环境色、材质与柔和对比建立人文触感；`dark_luminous` 以深底、受控亮面和单一光源建立产品舞台。不得把黑底、金色、渐变本身当作高级感。

## Background scene engine

背景是视觉叙事与阅读引导基础，不是空白填充。背景按需组织为 `Base → Image → Atmosphere/Light → Content Protection`；实现上可展开为 `Base Color → Image Layer → Overlay → Gradient Field → Light Field → Texture → Atmospheric Depth`。默认只启用最少层。每页必须回答场景、主焦点和文字安全区；答不出时回退 `solid_world`。Content Protection 只保护文字与主体可读性，不得把图片完全遮蔽；编译器 fallback 只属于渲染安全网，不能掩盖 Fill API 错误。

`solid_world` 适合数据、结论与高密度页面；`atmospheric` 适合章节、案例与环境叙事；`cinematic` 只适合少数高能量页面。背景不能与内容争夺注意力。禁止重模糊、HDR、无动机 glow、随机玻璃拟态、塑料纹理、背景文字和多层效果叠加。

## Image art direction

图片必须声明 `asset_function: context | emotion | proof | hero`、主体、镜头、光线、材质、构图方向、留白锚点、裁切策略和负面提示。优先级是相关性 > 构图 > 光线 > 材质 > 风格化效果。图片与文字应形成尺度、方向、语义或留白协同；无法提供信息价值时不用图。

图像不得烘焙文字、Logo、水印、数据或来源。`cover` 只在主体允许裁切时使用；文本区被主体侵入、主体丢失或图片改变了阅读重心时必须回退、重裁或换图。

## Card restraint

卡片不是默认容器。优先使用空间分组、发丝线、字体层级、留白关系和图片关系；只有数据模块、核心指标或特殊强调内容才允许使用面板/卡片。单页应限制卡片数量、面积、颜色和圆角，避免每条内容都被包进盒子。`rounded_rect` 超过 4 个或占主要结构时，判定为潜在 card wall；应删除容器、合并内容或改为编辑式分组。卡片不能同时承担所有层级，不能用圆角、阴影和高饱和填充制造“高级感”。

## Charts and data

准确 > 清晰 > 美观 > 装饰。趋势用折线，比较/排名用条形，构成最多五类，桥接用瀑布，定位用矩阵，阶段用时间轴或流程。一张图只回答一个关系；必须有单位、期间、比较口径、数据状态和来源。直接标注优先于图例，最多一个强调点、三种语义色、八个类别；不使用 3D、渐变柱、密集网格和装饰性仪表盘。

## Motion

动效服从内容、构图和现场节奏。全套最多两种姿态，默认 `still`，必要时使用 `reveal` 或 `progressive`。只有在改变阅读顺序、空间建立或数据理解时才使用动效。禁止炫技转场、粒子、无意义循环、大幅漂移。静态交付缺少动效环境时，内容与层级必须独立成立。

## Anti-design

卡片墙、平均九宫格、无意义边框、过度阴影、过度图标化、随机图库、竞赛性高亮、伪 3D、背景压字和为填空加细节均为反模式。修复时先删，再简化，再恢复空间，再重构重心，最后才替换媒体或微调装饰。
