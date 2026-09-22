# PPT Visual Art Director OS

一个 **Presentation Design Intelligence Skill**：把内容、受众与决策转成视觉策略与页面意图，
产出**原生可编辑 PPTX**，然后只做一次必要的交付验证。

不是模板库、不是设计系统、不是布局引擎。判断在 `SKILL.md` 与 `references/` 里，
执行在一条命令里。版本以 `pyproject.toml` 为准，逐版变更见 `CHANGELOG.md`。

## 标准生产顺序（`run` 是标准入口；轮次由资产数量、QC 状态与根因修订决定）

**brief → plan+资产契约（一次调用）→ 按清单出图 → 填骨架 → check 收口**

图片提示词由 `vao.py run/assets` 内置的 `asset_prompt.py` 产生，不是先自由出图后补清单。
外部图片服务并未内置于技能包；执行者仍需调用实际的生成工具。

```bash
# 0) Python 3.10+ 环境
python3 -m venv .venv && . .venv/bin/activate
python3 -m pip install -r requirements.txt

# 1) 完成 brief 后，一次调用拿到 plan + 骨架 + 资产清单（无图项目去掉后两个参数，直接跳到 3）
python scripts/vao.py run brief.yml --plan-out plan.json --skeleton build_deck.py \
    --assets-out asset_manifest.json --assets-dir generated_assets

# 2) 用外部图片工具按清单 prompt / negative / ratio / safe_area 生成图片
#    保存到 generated_assets；名称按 expected_filename（也支持同名 JPEG）

# 3) 填完骨架（头注释即完整作业单）直接 release 收口；确需迭代构图才先 --mode draft
#    check 内部完成资产核验：缺图、待重试或阻断都退出 2，不编译
python scripts/vao.py check build_deck.py out.pptx --mode release \
    --assets-manifest asset_manifest.json --speed fast --deadline 120
```

- **无图片**：不必走资产步骤；`check` 显式记录跳过原因。
- **用户提供/授权/自制/复用的图片**：放到清单规划的文件名即可——`assets` 阶段自动登记为
  existing 并进入核验；要交代版权/出处时在 brief 里写 `asset_source`。
- **流程边界**：发布通过证明本地文件证据一致，不证明外部模型按提示词执行，
  也不证明图片授权或艺术质量；不得以此替代人工设计判断。

资产链、迁移与绕过契约 → `references/asset-workflow.md`；运行时契约 → `references/production-contract.md`。

## 唯一入口

| 命令 | 作用 |
|---|---|
| `vao.py run` | brief → plan + 骨架 + 资产清单（标准入口），或检查已有编排稿 |
| `vao.py check` | 资产核验 → normalize → guard → compile → 可选 ghost → 分组修复包（`spec`/`draft`/`release`） |
| `vao.py plan` / `assets` | 规划 / 资产清单的单段重跑 |
| `vao.py preview` | 只出 ghost 方向预览（PIL，秒级） |
| `vao.py dna` | 经验记忆：`--check` 体检 / `--add` 写入一条（校验后才入库） |

`make` 是 `check` 的兼容别名，不维护第二条生产链。`assets` 默认只打印紧凑摘要；
`--show-prompts` 才把完整 prompt/negative 打到终端，`--json` 供机器消费。

## 设计上刻意不做的事

- **不调用 LibreOffice / soffice / poppler**：方向证据由 `ghost.py` 的确定性结构预览给出，
  产物是原生可编辑 PPTX。
- **不给作者判卷**：引擎只判工程事实；构图、用词、家族写法是设计判断，规则不代答。
- **不为架构完整而保留代码**：无人消费的字段与层次一律删除；判定层永不因此放松。
- **不打审美分**：验证只回答"能不能交付"；有没有设计价值由 `references/design-craft.md` 回答。
- **不把 warning 变成对话**：非阻断项聚合留痕；阻断项一次性按根因分组修完。
- **不做加法优先的修补**：页面不够高级时先走减法链 `删除 > 重组 > 排版 > 强化 > 装饰`。
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
python scripts/selftest.py        # 交付链 / 生产链契约 / 契约拦截 / 判断层 / 反退化 / 静默失效缝 / 速度档
```

注意：**这是技能包本身的单元测试集，制作幻灯片时绝对不需要运行**。
演示文稿生成生产阶段只运行 `python scripts/vao.py check ...`（毫秒级几何与安全网验证）。

验证网只保四件事：交付链能跑通、契约还拦得住错、判断层没有静默退化，
以及**文档没有写出代码不认的词**（照着写会被静默忽略，这是最贵的文档债）。

## 许可

MIT（见 `LICENSE.txt`）。正文中提及的第三方品牌与作品仅作可观察设计行为的引证，
不含其商标、素材或任何授权暗示。
