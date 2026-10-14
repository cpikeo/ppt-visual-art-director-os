# PPT Visual Art Director OS

**内容 → 逐页判断 → 原生可编辑 PPTX。** 单入口、一次判断、一次收口。

它是 Skill / 设计智能，不是设计系统、组件库、模板引擎或样式预设。它做的是**判断**：
这一页要让观众记住什么、为什么这样呈现、哪些东西必须删除。判断基准全部在 [SKILL.md](SKILL.md)。

```
THINK（plan：判断一次做完）→ BUILD（作者落元素）→ VERIFY（check：一次收口）
```

## 快速开始

```bash
pip install -r requirements.txt          # Python 3.10+；无系统级依赖
python scripts/vao.py plan brief.yml --out plan.json --skeleton build.py
# 作者按骨架原文与判断落元素（有图时按 asset_manifest.json 出图并写 asset_id）
python scripts/vao.py check build.py out.pptx --mode release --speed strict
python scripts/selftest.py               # 核心自检
```

brief 模板见 [templates/brief.yml](templates/brief.yml)。

## 结构

```
scripts/
  vao.py              唯一入口（plan / check / qc）
  intelligence.py     设计判断：判断链、视觉世界推导、骨架生成
  assets.py           资产必要性 → 提示词 → 清单 → 像素 QC → 链核验
  verify.py           硬错误 Guard → PASS / BLOCK → 发布清单
  compiler.py         确定性 PPTX 编译（含编译缓存）
  primitives.py       最小原语（身份 / 字节 / 几何 / 颜色 / 文本测量）
  ghost.py            PIL 结构预览（关键页取证）
  selftest.py         核心自检
references/           contract.md（字段与失败码）、assets.md（资产链）
```

Context 按需读取：判断校准读 `SKILL.md §2–3`；写 spec 读 `references/contract.md`；
判定需要图像时才读 `references/assets.md`。`plan` 本身不读 references，也不调用模型。

## 质量边界

- **QA 只拦硬错误**：编译失败、内容缺失、溢出、越界、重叠、无效资产 / 图表、来源缺失（release）。
  输出只有 PASS / BLOCK；设计质量由逐页判断与作者审阅负责。
- **验证层次不是一回事**：代码测试（selftest）→ 产物结构检查 → 结构预览（ghost，方向证据，不是真实渲染）
  → 目标 PowerPoint 打开 / 编辑 / 另存 / 重开（本仓库未验证）→ 专业视觉验收。自动化结果里后两层恒为未验证。
  本仓库不调用 PowerPoint，也不使用 LibreOffice 等替代引擎渲染。
- **速度**：`fast`（默认）只取关键页预览，`strict` 全页取证。实测数字见 CHANGELOG。

## 测试

```bash
python scripts/selftest.py   # 退出码即门槛；当前全部通过（数量见 selftest 输出）
```

CI（`.github/workflows/ci.yml`）在 ubuntu / windows × Python 3.10 / 3.12 / 3.13 上运行自检，
并做 spec 档冒烟（断言 spec 模式不加载 python-pptx）。

## 版本与历史

版本差异与验证边界见 [CHANGELOG.md](CHANGELOG.md)。历史数据、被删除的旧模块与旧经验记录可从 Git 历史恢复。

License: MIT（见 [LICENSE.txt](LICENSE.txt)）
