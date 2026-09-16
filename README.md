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
| 职责分层治理 | QA 判能不能交付；判断（人/AI + design-craft.md）判有没有设计价值；智能层给风险预测 + 生成策略 |

## 目录结构

```text
ppt-visual-art-director-os/
├── SKILL.md                      # Core Brain：10 原则 / 决策框架 / P1–P5 / 模式 / 路由
├── CHANGELOG.md                  # 演进史与路线图（唯一档案）
├── README.md
├── LICENSE.txt                   # MIT（第三方资产/字体/商标不受本许可覆盖）
├── requirements.txt
├── memory/design_dna.json        # 设计推理记忆（经验，非参数）
├── assets/                       # 示例资产（AI 生成，仅作演示，非模板）
├── references/
│   ├── production-contract.md    # 运行时契约表（权威）
│   ├── design-intelligence.md    # 判断核心：内容→意义→策略→页面意图
│   ├── archive.md                # 备查附录：35 条微规则全文（不进入生成上下文）
│   ├── design-craft.md           # 品味手册（原则 + 刻度 + 案例）
│   ├── design-system.md          # 执行默认值：网格/层级/主题人格/证据/校准
├── scripts/
│   ├── intent_compiler.py        # 意图压缩层：需求 → Design Brief
│   ├── design_intelligence_rules.py  # 机器口径：风险目录/密度带/取舍表
│   ├── route.py  pipeline.py  design_intelligence.py       # 决策层（pipeline 单进程汇合）
│   ├── layout_search.py
│   ├── compiler.py  primitives.py  compile_cache.py         # 编译层（elements/charts 已并入）
│   ├── guard.py  qa.py  render_check.py                    # 验证层（normalizer 已并入 guard）
│   ├── asset_prompt.py  ghost.py  selftest.py
└── templates/
    ├── strategy_direction.yml    # Strategy/Direction 空白契约
    └── design_brief.yml          # Design Brief 模板（~500 tokens）
```

## 示例资产（Sample Assets）

`assets/` 内 4 张示例资产（AI 生成，仅作演示，非模板、非规范）。版权归本仓库作者，随本包以 MIT 许可一并分发，可自由用于试跑出图体检。示例与正文中提及的第三方品牌、网站与作品（Apple、Pentagram、IDEO、McKinsey、Kinfolk 等）仅作**可观察设计行为的引证**，不含其商标、素材或任何授权暗示；文中案例均以通用描述指代，不指涉具体客户。它们覆盖不同的纸面/材质语言，可作 `asset_prompt.py --qc` 出图体检的输入示例——出图后跑一次定性体检（文字安全区 / 负空间 / 主体位置 / 亮度平衡 / 对比度，Issue + Suggestion，不打分）。阻断问题最多定向重出 1 次；`review/release` 不由资产 QC 自动触发，最终资格仍由 `qa.py --mode release` 与 Manifest 判定。

`asset_prompt.py` 是**通用**资产提示词组装器（13 个视觉家族），不是水墨专用；只有当资产卡选择水墨语言（subject/material/style 含水墨词，或 family ∈ song_elegance / zen_minimal）时，才自动注入水墨纪律闸门。`--qc IMAGE --phase draft --attempt 0` 会输出有界动作：阻断问题最多重出一次；`review/release` 只标记，不自动升级流程。

<p align="center">
  <img src="assets/1c2f20c6a78cd5c41dd344397e986f5b.png" alt="示例资产 1" height="240">
  <img src="assets/af927d8d95970a43eaec3f6cc67102aa.png" alt="示例资产 2" height="240">
  <img src="assets/bb423798bd14650761b3e744dfcd9905.png" alt="示例资产 3" height="240">
  <img src="assets/ffb347873654bd8176db4d7acbb3bd3d.png" alt="示例资产 4" height="240">
</p>

## 工作流

P1 内容理解 → P2 视觉策略（Strategy/Direction/Page Intent）→ P3 落地（骨架填充 + spec + 批量出图）→ P4 draft 验证 + 按 fix_plan 一轮修正 → P5 直接 release 收口。默认由 `pipeline.py` 单进程产 Brief/route/layout/risk 并把已决策字段序列化进 build 骨架；`spec`/`review` 是诊断与抽查工具，不是阶段门；独立脚本仅按需诊断。

```bash
python3 -m venv .venv && . .venv/bin/activate
python3 -m pip install -r requirements.txt
# R1 规划：同一进程完成 Brief/route/layout/risk；--skeleton 把已决策字段序列化进
# build 骨架（canvas/theme 种子/page_intent/source_zone 已填，elements 留空零预设）
python3 scripts/pipeline.py brief.yml --out plan.json --skeleton build_mydeck.py

# R2 一次性生成：Strategy/Direction/全量 spec 填入骨架；资产出图请求同轮批量发出
# R3 验证①：QA 内部已包含 Normalizer + Guard + Compile，零渲染；报告含 fix_plan
python3 scripts/qa.py build_mydeck.py out.pptx --mode draft
# R4 唯一修正轮：按 fix_plan 根因组一次改完（内嵌契约行，零文档回读）→ 复跑 draft

# R5 收口：方向确认后直接 release（全量渲染 + Manifest；页级缓存让修复复跑只重渲变化页）
python3 scripts/qa.py build_mydeck.py out.pptx --mode release
# 工具（非阶段门）：review=单页像素抽查 · spec=不写文件诊断 · ghost.py=零渲染看方向
```

上述是默认热路径，不要再串行执行 Guard/Compiler。仅需查看单层诊断或做安装/CI
回归时才单独调用：

```bash
python3 scripts/intent_compiler.py brief.yml --json
python3 scripts/route.py brief.yml --json
python3 scripts/guard.py build_mydeck.py --json
python3 scripts/compiler.py build_mydeck.py out.pptx
python3 scripts/selftest.py
```

`qa.py` 默认只做 Normalizer → Guard → Compile → 验证；设计风险建议不是默认步骤。
需要时显式加 `--advisory`（或兼容别名 `--risk`），修正链仍以 QA 的首个工程阻断项为主。

渲染证据需系统级依赖：LibreOffice（`soffice`）+ `poppler-utils`（`pdftoppm`）；缺失时自动降级为 `PREVIEW_ONLY`，不阻塞静态治理。

## 质量与发布门

QA 只判工程正确性（溢出/缺失/越界/重叠/数据/渲染），输出 PASS/FAIL/WARNING，不做审美评分。设计价值（层级/节奏/焦点/一致/记忆点）由判断层回答——人/AI 依据 `references/design-craft.md`；默认 `run_qa` 不运行设计建议，先做最小修正再立即验证。需要风险策略时显式使用 `--advisory`，它不是发布闸门。发布阻断项由 QA 持有：不可读、溢出、未声明遮挡、来源冲突、事实数据不完整、图表失真、编译失败、资产侵入安全区、渲染证据缺失。失败码与 Manifest 验收见 `references/production-contract.md`。

## 本地开发与测试

```bash
python -m pip install -r requirements.txt   # 只跑脚本的话，装依赖即可
python -m pip install -e .                  # 让 15 个脚本模块在任意目录可 import
python -m compileall -q scripts             # 语法自检
PYTHONPATH=scripts python scripts/selftest.py   # 回归套件：全 PASS 退 0，任一 FAIL 退 1
```

`selftest.py` **不需要 LibreOffice**：缺渲染器时相关用例自行降级，不会误报失败——所以它可以直接进 CI。
CI（`.github/workflows/ci.yml`）在 Linux 与 **Windows** 双平台 × Python 3.10/3.12/3.13 上跑回归，
外加一个 spec 档冒烟用例（把「spec 档不得拖入 python-pptx」这条红线钉在流水线上）。

`pyproject.toml` 只声明运行时依赖与**平铺的脚本模块**（它们之间是按顶层名互相 import 的），
不声明 packages：`pip install -e .` 与仓库内 `python scripts/qa.py` 走同一条导入路径，
不引入第二套。`references/` 与 `templates/` 是随仓库分发的生产资料，包内文档按相对路径互相引用，
因此不复制进 site-packages。

## 设计边界

不提供品牌资产授权，不核验第三方图片/字体/数据/商标许可，不访问外部账户。所有输出由责任人复核事实、版式、字体、素材、版权与软件兼容性。

## 许可证

MIT License（仅覆盖本项目代码与文档；第三方资产另遵其授权）。详见 [LICENSE.txt](LICENSE.txt)。
