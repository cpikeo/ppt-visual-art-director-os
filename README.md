# PPT Visual Art Director OS

一个 **Presentation Design Intelligence Skill**：把内容、受众与决策转成视觉策略与页面意图，
产出**原生可编辑 PPTX**，然后只做一次必要的交付验证。

不是模板库、不是设计系统、不是布局引擎。判断在 `SKILL.md` 与 `references/` 里，
执行在一条命令里。

## 当前版本：5.5.0

5.5.0 是第四轮深度审计（跨域验证后的死层切除）：Phase 15 三域盲测（城市研究 /
品牌融资 / 科技发布，均 release PASS）证明判断发生在**起草时**，spec 级二审层
零消费——遂整体切除：`pre_critic`(414 行) + `risk_strategy`(140 行) + 9 个仅被
它们消费的私有 helper + 11 个孤儿常量（`FOCUS_LEAD`/`STATEMENT_SIZE`/`PANEL_*`/
`RHYTHM_INK_*` 等）+ primitives 的死几何函数群（`filled_panels`/`memory_anchor`/
`content_occupancy`/第二套 bg 判定）。plan 期 `forecast_risk`（三域生产真实消费）
与 guard 的 `--advisory` 诊断开关保留。design_intelligence.py 1369→645 行（-53%）。
生产路径行为零变化（三域 plan 字节级一致，仅删一句陈旧 note）。
回归 **148/148 PASS**，三域 bench 全链 release 回归 round 1/6 PASS。

5.4.x 系列叙事（5.4.9 输出 schema 减法、5.4.8 AST 可达性清零、5.4.7 死常量清理与摘要合并、5.4.6 运行时
契约减法、5.4.5 System 三层切分、5.4.4 Intelligence 减法收敛、5.4.3 Craft 减法
重构、5.4.2 契约语义收紧、5.4.1 SKILL 决策系统重构、5.4.0 声明优先级语义）
全文见 `CHANGELOG.md`。

5.3.0 是**轮次与提示词质量版**：出图提示词去矛盾（光照单一来源、静物动势抑制、
构图语法翻译、色名可读化、负向提示分层）、`run` 一次完成规划+资产契约、
骨架升级为「完整作业单」（正常流程免读 plan.json）、删除全部零消费镜像字段、
文档去重（SKILL.md -28%）。
逐条对照见 `CHANGELOG.md`（5.2.0 及更早的修复叙事也在其中）。

提示词与计划字段变更后，旧资产清单指纹自然失效：旧图可登记 reuse 迁移，旧 QC 不自动升级。
对生成图片有意裁切时，可在对应 brief slide 中写 `asset_allow_crop: true`。
最低分辨率与透明度检查不会替代人工设计判断。QC 和发布不通过清单隐式执行 Python brief；
本包不是不可信代码沙箱。

## 标准生产顺序（`run` 是标准入口；轮次由资产数量、QC 状态与根因修订决定）

**brief → plan+资产契约（一次调用）→ 按清单出图 → asset-qc → 填骨架 → release 收口**

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

# 3) 检查图片；缺文件、待重试或阻断时退出码为 2，不能继续编排
python scripts/vao.py asset-qc asset_manifest.json --phase draft

# 4) 填完骨架（头注释即完整作业单）直接 release 收口；确需迭代构图才先 --mode draft
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
│   ├── design-craft.md         # 品味手册：Director Kernel + 五判断 + 案例（数字住 guard/契约）
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
    └── selftest.py           # 最小验证网（155 项，含判断层与反退化检查）
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

`assets/` 里是四副匿名化验证样张（整副 deck 的方向预览 contact sheet，JPEG q90），覆盖四种
不同视觉世界：东方墨韵编辑 / 瑞士精密科技 / 安静极简 / 有机奢华。它们证明的是
跨风格的版式纪律——章节页全幅重置、数据页单一强调、锚点同位——而不是供复制的
版式截图。代码不引用它们：它们是给人目检的证据，不是流水线的输入。

## 框架自检（开发者离线回归网，制作 PPT 时无需运行）

```bash
python scripts/selftest.py        # 155 项：交付链 / 契约拦截 / 判断层 / 反退化 / 静默失效缝
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
