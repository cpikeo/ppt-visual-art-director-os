# PPT Visual Art Director OS

一个 **Presentation Design Intelligence Skill**：把内容、受众与决策转成视觉策略与页面意图，
产出**原生可编辑 PPTX**，然后只做一次必要的交付验证。

不是模板库、不是设计系统、不是布局引擎。判断在 `SKILL.md` 与 `references/` 里，
执行在一条命令里。

当前版本 **7.0.0**（7.0 = 实战审核后的单生产契约：删掉零消费者计划镜像、收窄 QA、让 make 只做 check 兼容别名，并把设计判断收进 Just-in-Time 核心参考），
只删重复叙述与固定答案，不删事实、字段名与阻断码（225 项回归契约全过）；既有素材在
assets 阶段**自动登记**（字节在 = existing 状态如实写，保留规划身份与 prompt，
`asset_source` 只用于补版权/出处注记）；方向预览页数 ≤24 时自动全量（常规 deck 零采样
损失）；`plan_sha256` 改为稳定指纹（同输入重跑字节不变，跨进程可缓存）；
6.4.4 = 编辑化数据表达：单一信号色主题下系列色从「同色复用」改为同色相明度阶梯、accent 单占用（高亮不再与非高亮序列撞色）、预览不发明产物没有的边框与扇区色；钉值变化逐字节归因；
6.4.3 = 实战反馈修复：预览不画假图、资产 QC 相对底色与声明文字色、既有素材保留规划身份、补端到端生产链自检；
6.4.2 = 真实语料验证：五份真实稿 + 两组修订对照给出触发率/阻断率/修复后是否消失；QA 归属收口、px→pt 单源化，规则一条未删；
6.4.1 = 职责单源与触发率仪表：同一事实只留一个 owner；
6.4 = 执法面减法：引擎只在「事实」或「作者声明的刻度」时发声；
6.3 = 结构化减法：删掉写死的设计判断（家族 → 构图/叙事答案表）、
零消费者的计划字段与热路径上没人用的字节读取；同轮保持产物字节不变。
6.2 = 同一事实只产生一次：身份只有一个入口、凭证只有一种写法、一次运行只产出一份事实账本。
6.1 = 运行时减法：同一份事实只读一次、只量一次、只画一次、只写一次。6.0 = 结构化减法：
删掉无人消费的字段与层次、把用词与构图交还设计判断）。默认 `--speed fast`（两分钟交付档）：完整 PPT 收口
≤120s（不含外部出图），判定口径与 `--speed strict` 完全一致，差异只在证据预算
（QC 像素域、预览采样范围、缓存探测与压缩口径），并逐项写进报告。逐版变更见 `CHANGELOG.md`。

## 标准生产顺序（`run` 是标准入口；轮次由资产数量、QC 状态与根因修订决定）

**brief → plan+资产契约（一次调用）→ 按清单出图 → 填骨架 → check 收口**

图片提示词由 `vao.py run/assets` 内置的 `asset_prompt.py` 产生，不是先自由出图后补清单。
外部图片服务并未内置于技能包；执行者仍需调用实际的生成工具。

```bash
# 0) Python 3.10+ 环境
python3 -m venv .venv && . .venv/bin/activate
python3 -m pip install -r requirements.txt

# 1) 完成 brief 后，一次调用拿到 plan + 骨架 + 资产清单（无图项目去掉后两个参数，直接跳到 4）
python scripts/vao.py run brief.yml --plan-out plan.json --skeleton build_deck.py \
    --assets-out asset_manifest.json --assets-dir generated_assets

# 2) 用外部图片工具按清单 prompt / negative / ratio / safe_area 生成图片
#    保存到 generated_assets；名称按 expected_filename（也支持同名 JPEG）

# 3) 填完骨架（头注释即完整作业单）直接 release 收口；确需迭代构图才先 --mode draft
#    check 内部完成资产核验：缺图、待重试或阻断都退出 2，不编译
python scripts/vao.py check build_deck.py out.pptx --mode release \
    --assets-manifest asset_manifest.json --speed fast --deadline 120
```

`--speed fast`（默认）= 两分钟交付档；`--speed strict` = 全分辨率 QC + 全 deck 逐页预览的
全量证据档。`--deadline` 是本次调用的墙钟预算：到点即跳过可选证据并留痕，不无限重试。

- **无图片**：不必走资产步骤；`check` 显式记录跳过原因。
- **用户提供/授权/自制/复用的图片**：放到清单规划的文件名（`generated_assets/<expected_filename>`）
  即可——`assets` 阶段自动登记为 existing 并进入核验；要交代版权/出处时在 brief 的 slide 写
  `asset_source: {kind: provided, path, source}`（kind 可为 `provided / licensed / original / reuse`）。
  不强制生成，但仍经资产清单与 QC。
- **有图旧项目迁移**：重新 plan → assets；若旧图文件名与新规划一致则自动接管，否则复制成
  规划文件名（或在 slide 写 `asset_source`）。
- **自定义 QC 路径**：默认找清单同目录的 `asset_manifest.qc.json`，或用 `check --asset-qc-report` 指定。
- **流程边界**：发布通过证明本地文件证据一致，不证明外部模型按提示词执行，
  也不证明图片授权或艺术质量；不得以此替代人工设计判断。

详细契约见 `references/asset-workflow.md`；本次变更见 `CHANGELOG.md`。

## 唯一入口

| 命令 | 作用 |
|---|---|
| `vao.py plan` | brief → plan.json（家族/页意图/媒体闸门/工作契约）+ build 骨架；构图不查表代答 |
| `vao.py assets` | brief + plan → 去重后的批量资产清单（相同视觉需求只出一次图） |
| `vao.py check` | 资产核验 → normalize → guard → compile → 可选 ghost → 分组修复包（`spec`/`draft`/`release`） |
| `vao.py run` | 规划/清单准备，或检查已有编排稿；不能一次跳过出图与资产核验 |
| `vao.py make` | 兼容别名：转发到 `check`，不维护第二条生产链 |
| `vao.py preview` | 只出 ghost 方向预览（PIL，秒级） |
| `vao.py dna` | 经验记忆：`--check` 体检 / `--add` 写入一条（校验后才入库） |

## 目录

```text
ppt-visual-art-director-os/
├── SKILL.md                  # 技能本体：判断纪律 + 执行协议（Agent 只读这个入口）
├── references/
│   ├── design-judgment.md      # JIT 设计判断核心：焦点、留白、版式、影像、数据、节奏
│   ├── design-intelligence.md  # 历史/深度校准（按需，不默认预载）
│   ├── design-craft.md         # 历史品味案例（按需，不默认预载）
│   ├── design-system.md        # 精确 spec 字段与约束（只在写元素时读相关节）
│   ├── asset-workflow.md      # 资产链、迁移与跳过契约
│   └── production-contract.md  # 运行时契约（字段 / 模式 / 门槛 / 报告）
├── templates/brief.yml       # 唯一需求契约（人写的一页纸）
├── memory/design_dna.json    # 经验记忆（判断线索，不是参数表；写入走 `vao.py dna`）
└── scripts/
    ├── vao.py                # 唯一生产入口
    ├── pipeline.py route.py intent_compiler.py    # 规划层
    ├── design_intelligence.py design_intelligence_rules.py  # 判断/风险/色彩派生
    ├── compiler.py primitives.py compile_cache.py # 编译层（原生 PPTX）
    ├── guard.py qa.py        # 验证层（静态契约 + 交付判定，无评分无渲染）
    ├── ghost.py              # PIL 方向预览（替代外部渲染器）
    ├── asset_prompt.py       # 资产提示词翻译 + 资产 QC
    └── selftest.py           # 最小验证网（225 项，含判断层、端到端生产链、反退化与速度档检查）
```

## 设计上刻意不做的事

- **不调用 LibreOffice / soffice / poppler**：没有 PPTX→PDF→图像 的高成本链路；
  方向证据由 `ghost.py` 的确定性结构预览给出，产物是原生可编辑 PPTX。
- **不给作者判卷**：引擎只判工程事实（声明了有没有落、位置稳不稳、数据成立不成立）。
  用词、构图、家族写法是设计判断——`family: cover` 与 `page_family: COVER` 同样合法，
  眉标写引擎给的说法或你自己的说法都成立。规则不替作者决定内容怎么写。
- **不为架构完整而保留代码**：无人消费的字段与层次（`forecast_risk` / `empty_space_role` /
  `rhythm_stage` / `reading_order`）一律删除；判定层永不因此放松。
- **不提供布局引擎**：plan 只给家族、页意图、叙事动作、构图语法提案与预算；
  几何与构图由生成侧判断，提案可整体推翻。
- **不打审美分**：验证只回答"能不能交付"；有没有设计价值由 `design-craft.md` 的判断坐标回答。
- **不把 warning 变成对话**：非阻断项聚合留痕；阻断项一次性按根因分组修完。
- **不做加法优先的修补**：页面不够高级时先走减法链
  `删除 > 重组 > 排版 > 强化 > 装饰`，而不是先加元素。`Anti-Design` 列的是症状不是禁令，
  故意做出其中某一项，只要写清意图就成立。
- **不提供反模式黑名单式的风格宪章**：参照系（Apple Keynote / Pentagram / Swiss Typography /
  FT / Bloomberg / Kinfolk / Monocle / Wallpaper* / IDEO）只用来校准判断力——
  学它为什么这样决定，不学它长什么样。
- **不做逐脚本编排**：所有生产调用都从 `vao.py` 进入。

## 样张（assets/）

`assets/` 里是四副匿名化验证样张（整副 deck 的方向预览 contact sheet，PNG），覆盖四种
不同视觉世界：东方墨韵编辑 / 瑞士精密科技 / 安静极简 / 有机奢华。它们证明的是
跨风格的版式纪律——章节页全幅重置、数据页单一强调、锚点同位——而不是供复制的
版式截图。代码不引用它们：它们是给人目检的证据，不是流水线的输入。

| ![东方墨韵编辑](assets/1c2f20c6a78cd5c41dd344397e986f5b.png) | ![安静极简](assets/ffb347873654bd8176db4d7acbb3bd3d.png)  |
|:--:|:--:|
| 东方墨韵编辑 | 安静极简 |
| ![有机奢华](assets/bb423798bd14650761b3e744dfcd9905.png)| ![瑞士精密](assets/af927d8d95970a43eaec3f6cc67102aa.png)  |
|  有机奢华 | 瑞士精密 |

## 框架自检（开发者离线回归网，制作 PPT 时无需运行）

```bash
python scripts/selftest.py        # 225 项：交付链 / 生产链契约 / 契约拦截 / 判断层 / 反退化 / 静默失效缝 / 速度档
```

注意：**这是技能包本身的单元测试集，制作幻灯片时绝对不需要运行**。
演示文稿生成生产阶段只运行 `python scripts/vao.py check ...`（毫秒级几何与安全网验证，~700ms 极速完成）。

验证网只保四件事：交付链能跑通、契约还拦得住错、判断层没有静默退化
（每个家族都有专属叙事动作与构图语法、骨架与 plan 同源、验证不出分数）、
技能包没有退化成它反对的东西（外部渲染器、布局引擎、逐脚本 CLI、文档死引用），
以及**文档没有写出代码不认的词**（照着写会被静默忽略，这是最贵的文档债）。

## 许可

MIT（见 `LICENSE.txt`）。正文中提及的第三方品牌与作品仅作可观察设计行为的引证，
不含其商标、素材或任何授权暗示。
