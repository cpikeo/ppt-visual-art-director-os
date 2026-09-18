# PPT Visual Art Director OS

一个 **Presentation Design Intelligence Skill**：把内容、受众与决策转成视觉策略与页面意图，
产出**原生可编辑 PPTX**，然后只做一次必要的交付验证。

不是模板库、不是设计系统、不是布局引擎。判断在 `SKILL.md` 与 `references/` 里，
执行在一条命令里。

## 当前本地修复版：5.2.0

5.2.0 是**用实战返工换速度**：一次 11 页真实交付暴露的 15 个问题里，4 个是静默失效
（不报错、结果错、每次都逼人回源码找口径）。这次只修根因 ——
**`SKILL.md` / `design-craft.md` / `design-intelligence.md` 一个字都没改**，
不增命令、不增模块、不增规则。

修的是这四处：介质判定看错了层（`ink_gate_active` 认方向族名而不是资产声明）、
13 个色彩族名送不进 `design_direction`、deck 级 `visual_world` 会污染单张图的介质、
「主体贴边」被拿来判氛围图；另外让 ghost 预览认多序列图表、brief 模板补上
`material`/`lighting`/`texture`/`asset_color` 这些一直生效却没写出来的旋钮、
删掉 6 个零消费字段、报错直接给出权威位置。回归 **139/139 PASS**。
逐条对照见 `CHANGELOG.md`。

5.1.2 补的是**判断层**：Anti-Design 主动避免清单、统一的减法链
（`删除 > 重组 > 排版 > 强化 > 装饰`）、以及把 Apple Keynote / Pentagram / FT / Bloomberg /
Kinfolk / Monocle 这类参照系明确成「校准判断力的标尺，不是可复制的版式」。
同时修掉两个静默失效缺陷：非 UTF-8 码页 Windows 上 selftest 直接崩溃（回归网根本起不来）、
M-09 用例因宿主静默降级 symlink 而失效。

5.1.1 处理了深度审计的 3 个 P1、11 个 P2。变更集中在现有模块：不增加命令、服务或依赖。
**删除危险的共享图片适配缓存，保留整份 PPT 编译缓存；核验后的图片 bytes 快照同时供编译与预览使用。**
详细修复编号与迁移要求见 `CHANGELOG.md`。

旧项目需重新建立计划/清单并运行 QC，旧图可登记 reuse；旧 QC 不自动升级。
对生成图片有意裁切时，可在对应 brief slide 中写 `asset_allow_crop: true`。
最低分辨率与透明度检查不会替代人工设计判断。明确的可信 Python 入口仍执行代码，
但 QC 和发布不再通过清单隐式执行 Python brief；本包不是不可信代码沙箱。

## 标准生产顺序（v5.1.1）

**brief → plan → assets → 按清单出图 → asset-qc → PPT 编排 → release**

图片提示词通过 `vao.py assets` 调用 `asset_prompt.py` 产生，不是先自由出图后补清单。
外部图片服务并未内置于技能包；执行者仍需调用实际的生成工具。

```bash
# 0) Python 3.10+ 环境
python3 -m venv .venv && . .venv/bin/activate
python3 -m pip install -r requirements.txt

# 1) 完成 brief：页面意图、主体、图片比例与文字留白
python scripts/vao.py plan brief.yml --out plan.json --skeleton build_deck.py

# 2) 必须引用已保存、与当前 brief 匹配的 plan
python scripts/vao.py assets brief.yml --plan plan.json --out asset_manifest.json --assets-dir generated_assets

# 3) 用外部图片工具按清单 prompt / negative / ratio / safe_area 生成图片
#    保存到 generated_assets；名称按 expected_filename（也支持同名 JPEG）

# 4) 检查图片；缺文件、待重试或阻断时退出码为 2，不能继续编排
python scripts/vao.py asset-qc asset_manifest.json --phase draft

# 5) QC 成功后填充骨架；图片元素使用 asset_id
python scripts/vao.py check build_deck.py out.pptx --mode draft --assets-manifest asset_manifest.json

# 6) 发布：核对当前图片、QC、清单与计划，再编译/预览/发布
python scripts/vao.py check build_deck.py out.pptx --mode release --assets-manifest asset_manifest.json
```

- **无图片**：不必走资产步骤；`check` 显式记录跳过原因。
- **用户提供/授权/自制/复用的图片**：在 brief 的 slide 中填写
  `asset_source: {kind: provided, path: /path/to/image.jpg, source: "用户提供，授权待核实"}`。
  不强制生成，但仍经资产清单与 QC。`kind` 也可为 `licensed / original / reuse`。
- **有图旧项目迁移**：重新 plan → assets，既有图登记为 reuse；保留新骨架的
  `asset_workflow.plan_sha256` 与 `plan_path` 并为图片填入 `asset_id`，QC 通过后再检查。
- **自定义 QC 路径**：`asset-qc --out` 后，给 `check --asset-qc-report` 同一路径。
- **流程边界**：发布通过证明本地文件证据一致，不证明外部模型按提示词执行，
  也不证明图片授权或艺术质量；不得以此替代人工设计判断。

详细契约见 `references/asset-workflow.md`；本次变更见 `CHANGELOG.md`。

## 唯一入口

| 命令 | 作用 |
|---|---|
| `vao.py plan` | brief → plan.json（家族/页意图/叙事动作/构图语法提案/媒体闸门）+ build 骨架 |
| `vao.py assets` | brief + plan → 去重后的批量资产清单（相同视觉需求只出一次图） |
| `vao.py asset-qc` | 图片体检 + 清单/文件指纹凭证；retry/missing/block 均退出 2 / 对比度 |
| `vao.py check` | normalize → guard → compile → ghost 预览 → 分组修复包（`spec`/`draft`/`release`） |
| `vao.py run` | 规划/清单准备，或检查已有编排稿；不能一次跳过出图与 QC |
| `vao.py preview` | 只出 ghost 方向预览（PIL，秒级） |
| `vao.py dna` | 经验记忆：`--check` 体检 / `--add` 写入一条（校验后才入库） |
| `vao.py doctor` | 环境自检 |

## 目录

```text
ppt-visual-art-director-os/
├── SKILL.md                  # 技能本体：判断纪律 + 执行协议（Agent 只读这个入口）
├── references/
│   ├── design-intelligence.md  # 内容 → 意义 → 策略 → 页面意图
│   ├── design-craft.md         # 品味手册：审查坐标系 + 原则 + 案例
│   ├── design-system.md        # 执行默认值与首轮值 + Spec 字段速查
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
    └── selftest.py           # 最小验证网（139 项，含判断层与反退化检查）
```

## 设计上刻意不做的事

- **不调用 LibreOffice / soffice / poppler**：没有 PPTX→PDF→图像 的高成本链路；
  方向证据由 `ghost.py` 的确定性结构预览给出，产物是原生可编辑 PPTX。
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

`assets/` 里是四副匿名化验证样张（整副 deck 的方向预览 contact sheet），覆盖四种
不同视觉世界：东方墨韵编辑 / 瑞士精密科技 / 安静极简 / 有机奢华。它们证明的是
跨风格的版式纪律——章节页全幅重置、数据页单一强调、锚点同位——而不是供复制的
版式截图。代码不引用它们：它们是给人目检的证据，不是流水线的输入。

## 框架自检（开发者离线回归网，制作 PPT 时无需运行）

```bash
python scripts/selftest.py        # 139 项：交付链 / 契约拦截 / 判断层 / 反退化 / 静默失效缝
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
