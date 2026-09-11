# PPT Visual Art Director OS

面向高端商业演示的视觉艺术指导、信息设计与原生可编辑 PPTX 生产技能包。链路：**理解内容 → 判断设计意图 → 预测视觉问题 → 选择设计策略 → 生成高质量页面**——一次通过，而非生成后反复修复。

设计哲学与执行纪律以 `SKILL.md` 为唯一权威：高级感来自精准、克制、秩序、空间与细节。

## 核心能力

| 能力 | 说明 |
|---|---|
| 内容到视觉策略 | 受众/决策/张力/证据 → Strategy、Direction、Story Map |
| 页面级叙事 | 每页单一 insight、focus、reading order、energy、density |
| 视觉空间设计 | 背景/媒体/文字/图表/材质/光线共享同一空间假设 |
| 信息与数据设计 | 诚实图表，保留单位/期间/口径/来源/数据状态 |
| 原生可编辑输出 | `python-pptx` 生成可编辑对象 |
| 职责分层治理 | QA 判能不能交付；Critic 判有没有高级价值；智能层给风险预测 + 生成策略 |

## 目录结构

```text
ppt-visual-art-director-os/
├── SKILL.md                      # Core Brain：10 原则 / 决策框架 / P1–P5 / 模式 / 路由
├── CHANGELOG.md                  # 演进史与路线图（唯一档案）
├── README.md
├── requirements.txt
├── memory/design_dna.json        # 设计推理记忆（经验，非参数）
├── references/
│   ├── production-contract.md    # 运行时契约表（权威）
│   ├── design-intelligence.md    # 判断核心：内容→意义→策略→页面意图
│   ├── archive.md                # 备查附录：35 条微规则全文（不进入生成上下文）
│   ├── design-craft.md           # 品味手册（原则 + 刻度 + 案例）
│   ├── design-system.md          # 执行默认值：网格/层级/主题人格/证据/校准
├── scripts/
│   ├── intent_compiler.py        # 意图压缩层：需求 → Design Brief
│   ├── design_intelligence_rules.py  # 机器口径：风险目录/密度带/取舍表
│   ├── route.py  design_intelligence.py  layout_search.py  # 决策层
│   ├── compiler.py  primitives.py                          # 编译层（elements/charts 已并入）
│   ├── guard.py  qa.py  render_check.py                    # 验证层（normalizer 已并入 guard）
│   ├── asset_prompt.py  ghost.py  selftest.py
└── templates/
    ├── strategy_direction.yml    # Strategy/Direction 空白契约
    └── design_brief.yml          # Design Brief 模板（~500 tokens）
```

## 工作流

P1 内容理解 → P2 视觉策略（Strategy/Direction/Page Intent）→ P3 布局决策 → P4 关键细节优化（1 根因 = 1 轮）→ P5 质量检查。先 `intent_compiler` 产 Brief，再 `route` 定家族与预算，再写 spec。

```bash
python3 -m venv .venv && . .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 scripts/intent_compiler.py brief.yml --json   # 需求 → Design Brief
python3 scripts/route.py brief.yml --json             # 内容 → 家族 / 密度 / 资产预算
python3 scripts/guard.py build_mydeck.py --preflight  # 静态诊断（0.2s 级）
python3 scripts/compiler.py build_mydeck.py out.pptx  # 编译可编辑 PPTX
python3 scripts/qa.py build_mydeck.py out.pptx        # 默认 draft（零渲染）
python3 scripts/qa.py build_mydeck.py out.pptx --mode review    # 变化页 + Critic
python3 scripts/qa.py build_mydeck.py out.pptx --mode release   # 全量 + Manifest
python3 scripts/selftest.py
```

渲染证据需系统级依赖：LibreOffice（`soffice`）+ `poppler-utils`（`pdftoppm`）；缺失时自动降级为 `PREVIEW_ONLY`，不阻塞静态治理。

## 质量与发布门

QA 只判工程正确性（溢出/缺失/越界/重叠/数据/渲染），输出 PASS/FAIL/WARNING；Critic 只判设计价值（层级/节奏/焦点/一致/记忆点），主输出 `diagnosis`，分数是置信度。发布阻断项由 QA 持有：不可读、溢出、未声明遮挡、来源冲突、事实数据不完整、图表失真、编译失败、资产侵入安全区、渲染证据缺失。失败码与 Manifest 验收见 `references/production-contract.md`。

## 设计边界

不提供品牌资产授权，不核验第三方图片/字体/数据/商标许可，不访问外部账户。所有输出由责任人复核事实、版式、字体、素材、版权与软件兼容性。

## 许可证

MIT License（仅覆盖本项目代码与文档；第三方资产另遵其授权）。详见 [LICENSE.txt](LICENSE.txt)。
