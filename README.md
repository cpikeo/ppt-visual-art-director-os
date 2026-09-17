# PPT Visual Art Director OS

一个 **Presentation Design Intelligence Skill**：把内容、受众与决策转成视觉策略与页面意图，
产出**原生可编辑 PPTX**，然后只做一次必要的交付验证。

不是模板库、不是设计系统、不是布局引擎。判断在 `SKILL.md` 与 `references/` 里，
执行在一条命令里。

```bash
# 0) 环境（Python 3.10+）
python3 -m venv .venv && . .venv/bin/activate
python3 -m pip install -r requirements.txt
#    或 pip install -e .（把 scripts/*.py 装成模块，便于 import；生产入口仍是 scripts/vao.py）

# R1 规划：brief → plan.json + build 骨架
python scripts/vao.py plan templates/brief.yml --out plan.json --skeleton build_deck.py

# R2 填骨架（策略/方向/全量 elements）——一次性写完

# R3 验证①：归一化 → Guard → 编译 → 修复包（单进程，零外部渲染器）
python scripts/vao.py check build_deck.py out.pptx --mode draft

# R4 若被阻断：按 fix_plan 根因组一次改完，复跑同一条命令
# R5 收口：结构判定 + 方向预览证据 + Release Manifest
python scripts/vao.py check build_deck.py out.pptx --mode release
```

## 唯一入口

| 命令 | 作用 |
|---|---|
| `vao.py plan` | brief → plan.json（家族/页意图/叙事动作/构图语法提案/媒体闸门）+ build 骨架 |
| `vao.py assets` | brief + plan → 去重后的批量资产清单（相同视觉需求只出一次图） |
| `vao.py asset-qc` | 资产体检：文字安全区 / 负空间 / 主体位置 / 亮度平衡 / 对比度 |
| `vao.py check` | normalize → guard → compile → ghost 预览 → 分组修复包（`spec`/`draft`/`release`） |
| `vao.py run` | plan + check 在一个进程里完成 |
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
    └── selftest.py           # 最小验证网（53 项，含判断层与反退化检查）
```

## 设计上刻意不做的事

- **不调用 LibreOffice / soffice / poppler**：没有 PPTX→PDF→图像 的高成本链路；
  方向证据由 `ghost.py` 的确定性结构预览给出，产物是原生可编辑 PPTX。
- **不提供布局引擎**：plan 只给家族、页意图、叙事动作、构图语法提案与预算；
  几何与构图由生成侧判断，提案可整体推翻。
- **不打审美分**：验证只回答"能不能交付"；有没有设计价值由 `design-craft.md` 的判断坐标回答。
- **不把 warning 变成对话**：非阻断项聚合留痕；阻断项一次性按根因分组修完。
- **不做逐脚本编排**：所有生产调用都从 `vao.py` 进入。

## 自检

```bash
python scripts/selftest.py        # 53 项：交付链 / 契约拦截 / 判断层 / 反退化
```

验证网只保四件事：交付链能跑通、契约还拦得住错、判断层没有静默退化
（每个家族都有专属叙事动作与构图语法、骨架与 plan 同源、验证不出分数）、
技能包没有退化成它反对的东西（外部渲染器、布局引擎、逐脚本 CLI、文档死引用），
以及**文档没有写出代码不认的词**（照着写会被静默忽略，这是最贵的文档债）。

## 许可

MIT（见 `LICENSE.txt`）。正文中提及的第三方品牌与作品仅作可观察设计行为的引证，
不含其商标、素材或任何授权暗示。
