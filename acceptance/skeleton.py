# # -*- coding: utf-8 -*-
# plan → build：逐页判断只在 plan.json 有一份完整记录，几何由作者决定。
# 作业顺序：受众/决定 → 结论/阻力 → 权重 → 焦点/空间/构图 → 字体/媒体/节奏。
# 完整竞争理由在 plan.json；此处只带着原文与为什么这样落笔的短备忘。
# 内容必须真实出现，不因骨架省略证据；能删就不加，不能用小字掩盖过载。
# 排版纪律（逐页默认，页内不再重复）: 结论按语义停顿断行，动词与对象相连、数字不与单位拆开；标题与支撑共用阅读轴，字距克制，装不下先删句而非压行距或缩字号。
# 留白：每处空白说得出保护什么；说不出的是事故。行长建议为非实测容量。
# 跨页锚（anchor：眉标 / 页码，≥4 页时由 plan 发）：落成 role=eyebrow / role=page_number 的元素，位置全稿一致。
# 字段契约 → references/contract.md（一次）；判断有真实缺口才回看 SKILL.md §2–3。
# 质量档: fast · 页数: 7
#   受众: 仓库维护者与设计作者 · 决策: 审查本地修改后安排目标 PowerPoint 验收 · 张力: 不能把自动测试通过误当作品视觉完成
#   视觉世界（由内容推导 · subject:paper_ink）: handmade paper ground, pigment settling into fiber, matte finish
#     纸/墨: #F4EDE7 / #12120F · 强调: #9C3B26 = 标记当前值/现状
#     光: even diffuse daylight, no visible source · 图表性格: layer map with hairline connectors
#     排版声音: austerity with human warmth：窄栏、大字阶、克制的粗体 · 字体: {'cn': 'Source Han Serif SC', 'latin': 'Georgia'}
#     为什么: register→受众与场合语域＝document（决定纸、字与克制程度）；subject→内容里的主题实体＝paper_ink（决定材质、光与强调色相）；regime→浅色纸面：文档语域下纸面托住信息
#   整套节奏: linear_structure → editorial → linear_structure → data_field → linear_structure → big_whitespace → editorial
# 无必要图像：不出图、不加载清单、不为填版造画面。
# 填完后一次收口：
#   python scripts/vao.py check <本文件> out.pptx --mode release --speed strict
SPEC = {
    "canvas": {"width": 1280, "height": 720, "grid_columns": 12, "grid_unit": 8},
    "theme": {
        "colors": {'background': '#F4EDE7', 'ink': '#12120F', 'muted': '#8B8883', 'primary': '#12120F', 'secondary': '#8B8883', 'accent': '#9C3B26'},
        "fonts": {'cn': 'Source Han Serif SC', 'latin': 'Georgia'},  # 世界排版语气；作者有依据时可覆盖
    },
    "slides": [
        # ── s01 · 角色:establish · 证据=structure · 媒体:none
        # 内容原文: "架构简单，判断不能简单 架构简单，\n判断不能简单。\n删掉重复劳动，保留真实证据。\n仓库审计样稿 · 可编辑对象 · 目标 PowerPoint 尚待验收"
        # 结论[extracted]: 架构简单，判断不能简单 · 理由: 标题；发布前请作者确认口径。
        # 权重: 主 「架构简单，判断不能简单」 / 关系的形状（层级/顺序）；次 —；删除 —
        # 焦点: structure_map（chart）· 构图: linear_structure · 主区: 关系与归属的共同阅读区
        # 排版: 主语 架构简单，判断不能简单 · 退后 无 · 行长≈38字；主体与职责/对象按成对关系对齐，必要限定贴近所属对象；层级只按明确归属表达，不把职责分工改成时间轴或推测汇报线。
        # 跨页节奏[open]：建立整套主张：先让观众知道要判断什么。
        # 必落元素: structure_map(chart)；claim_text(text) · 密度 balanced
        # 作者声明（原样生效）: asset='none'
        {
            "id": 's01',
            "anchor": {"eyebrow": "架构简单"},
            "source_zone": {"x": 48, "y": 672, "width": 1184, "height": 32},
            "elements": [  # TODO：按上面的判断落元素
            ],
        },
        # ── s02 · 角色:prove · 证据=proposition · 媒体:none
        # 内容原文: "相加为100不是共同分母 相加为 100，\n不等于同一个整体。\n60%\n缓解率\n40%\n不良反应发生率\n同一患者可同时满足两者。先问事件是否互斥，再决定能否画饼图。"
        # 结论[extracted]: 相加为100不是共同分母 · 理由: 标题 ＋ 数字「100」；发布前请作者确认口径。
        # 权重: 主 100；次 60% / 40%…；删除 100 的重复出现
        # 焦点: kpi_main（text）· 构图: editorial · 主区: 标题与导语区
        # 排版: 主语 100 · 退后 60% · 行长≈38字；主数字连同单位先读；说明、出处沿同一阅读轴退后。只有真实基期才画比较，用留白而非加字距或卡片填满画面。
        # 跨页节奏[turn]：主张或证据形态变化，阅读路径跟着内容转向。
        # 必落元素: kpi_main(text)；claim_text(text)；source(text)；witness_line(text) · 密度 balanced
        # 作者声明（原样生效）: asset='none'
        {
            "id": 's02',
            "anchor": {"eyebrow": "相加", "page_number": 2},
            "source_zone": {"x": 48, "y": 672, "width": 1184, "height": 32},
            "elements": [  # TODO：按上面的判断落元素
            ],
        },
        # ── s03 · 角色:explain · 证据=sequence · 媒体:none
        # 内容原文: "职责并列不是时间线 职责并列，\n不是先后顺序。\n青禾组\n负责\n质量测试\n澄海组\n负责\n项目交付\n没有已知上下级，就不补汇报线；没有时间轴，就不造流程。"
        # 结论[extracted]: 职责并列不是时间线 · 理由: 标题；发布前请作者确认口径。
        # 权重: 主 「职责并列不是时间线」 / 关系的形状（层级/顺序）；次 —；删除 —
        # 焦点: structure_map（chart）· 构图: linear_structure · 主区: 轴线上第一个与当前节点
        # 排版: 主语 职责并列不是时间线 · 退后 无 · 行长≈38字；节点→机制沿一条清楚的轴线排字；标签、解释共用文字边界，在语义节点断行，节点间距比容器与图标更能表达顺序。
        # 跨页节奏[turn]：主张或证据形态变化，阅读路径跟着内容转向。
        # 必落元素: structure_map(chart)；claim_text(text) · 密度 balanced
        # 作者声明（原样生效）: asset='none'
        {
            "id": 's03',
            "anchor": {"eyebrow": "职责", "page_number": 3},
            "source_zone": {"x": 48, "y": 672, "width": 1184, "height": 32},
            "elements": [  # TODO：按上面的判断落元素
            ],
        },
        # ── s04 · 角色:prove · 证据=series · 媒体:none
        # 内容原文: "新边界案例通过由7增至12 五个误判被消除。\n视觉质量仍需另验。\n12/12\n固定关系不变式\n不是独立盲评\n不是跨行业质量证明"
        # 结论[extracted]: 新边界案例通过由7增至12 · 理由: 标题 ＋ 数字「7/12」 ＋ 变化「增至」；发布前请作者确认口径。
        # 权重: 主 12；次 7 / 坐标轴与刻度；删除 12 的重复出现
        # 焦点: kpi_main（chart）· 构图: data_field · 主区: 上部结论带 + 中部数据场
        # 排版: 主语 12 · 退后 7 · 行长≈38字；终值与单位为主轴，基期退一层；可比数字才共享刻度/基线，期间与出处就近但不抢主值，勿用线框填空。
        # 跨页节奏[breathe]：信息密度变化来自证据体量；用疏密给前一页让出阅读时间。
        # 必落元素: kpi_main(chart)；claim_text(text)；source(text) · 密度 dense
        # 作者声明（原样生效）: asset='none'
        {
            "id": 's04',
            "anchor": {"eyebrow": "新边界案例通", "page_number": 4},
            "source_zone": {"x": 48, "y": 672, "width": 1184, "height": 32},
            "elements": [  # TODO：按上面的判断落元素
            ],
        },
        # ── s05 · 角色:explain · 证据=structure · 媒体:none
        # 内容原文: "调用链不增加模型或新模块 保持一条生产链。\nTHINK\nBUILD\nVERIFY\n主张与证据\n保留未知关系\n原生文字与图表\n作者决定几何\n硬门与字节凭证\n不代替视觉签署\n删除不可靠的隐式缓存；复用显式快照与已验摘要。"
        # 结论[extracted]: 作者决定几何 · 理由: 正文 ＋ 结论措辞「决定」 ＋ 短句可复述；发布前请作者确认口径。
        # 权重: 主 「作者决定几何」 / 关系的形状（层级/顺序）；次 —；删除 —
        # 焦点: structure_map（chart）· 构图: linear_structure · 主区: 关系与归属的共同阅读区
        # 排版: 主语 作者决定几何 · 退后 无 · 行长≈38字；主体与职责/对象按成对关系对齐，必要限定贴近所属对象；层级只按明确归属表达，不把职责分工改成时间轴或推测汇报线。
        # 跨页节奏[breathe]：信息密度变化来自证据体量；用疏密给前一页让出阅读时间。
        # 必落元素: structure_map(chart)；claim_text(text) · 密度 balanced
        # 作者声明（原样生效）: asset='none'
        {
            "id": 's05',
            "anchor": {"eyebrow": "作者决定几何", "page_number": 5},
            "source_zone": {"x": 48, "y": 672, "width": 1184, "height": 32},
            "elements": [  # TODO：按上面的判断落元素
            ],
        },
        # ── s06 · 角色:prove · 证据=number · 媒体:none
        # 内容原文: "数字与单位绑定不等于真实排版通过 186 公里，\n不能在单位前断开。\n186 公里\n不断行空格已写入原生文字；中文字体角色已绑定。\n真实断行、字体回退与投影可读性，须在目标 PowerPoint 检查。"
        # 结论[extracted]: 186 公里 · 理由: 首句 ＋ 数字「186 公里」 ＋ 短句可复述；发布前请作者确认口径。
        # 权重: 主 186 公里；次 186 公里；删除 —
        # 焦点: kpi_main（text）· 构图: big_whitespace · 主区: 主张或证据的唯一焦点区
        # 排版: 主语 186 公里 · 退后 186 公里 · 行长≈38字；主数字连同单位先读；说明、出处沿同一阅读轴退后。只有真实基期才画比较，用留白而非加字距或卡片填满画面。
        # 跨页节奏[breathe]：信息密度变化来自证据体量；用疏密给前一页让出阅读时间。
        # 必落元素: kpi_main(text)；claim_text(text)；source(text) · 密度 sparse
        # 作者声明（原样生效）: asset='none'
        {
            "id": 's06',
            "anchor": {"page_number": 6},
            "source_zone": {"x": 48, "y": 672, "width": 1184, "height": 32},
            "elements": [  # TODO：按上面的判断落元素
            ],
        },
        # ── s07 · 角色:summarize · 证据=proposition · 媒体:none
        # 内容原文: "保留目标软件验收 代码可以通过。\n作品必须被看见。\n下一步：打开、编辑、另存，再重开。\n目标 PowerPoint 未验证 · 独立视觉盲评未开展"
        # 结论[extracted]: 作品必须被看见 · 理由: 正文 ＋ 结论措辞「必须」 ＋ 短句可复述；发布前请作者确认口径。
        # 权重: 主 「作品必须被看见」；次 —；删除 —
        # 焦点: criteria_ask（text）· 构图: editorial · 主区: 标题与导语区
        # 排版: 主语 作品必须被看见 · 退后 无 · 行长≈38字；收束页的唯一落点：决定/动作/判据的字阶最大，对象与条件同行；理由与出处退一层，不与落点争字阶。
        # 跨页节奏[close]：回收开场的决定，不用新装饰或谢谢页稀释请求。
        # 必落元素: criteria_ask(text)；claim_text(text) · 密度 balanced
        # 作者声明（原样生效）: asset='none'
        {
            "id": 's07',
            "anchor": {"eyebrow": "作品必须", "page_number": 7},
            "source_zone": {"x": 48, "y": 672, "width": 1184, "height": 32},
            "elements": [  # TODO：按上面的判断落元素
            ],
        },
    ],
}

