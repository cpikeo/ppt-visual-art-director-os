# Contract（执行契约 · 写 elements 前查）

运行时权威表：落地给什么值、什么会被当场抓住。判断校准 → `judgment.md`；
资产链 → `assets.md`；案例 → `precedent.md`。

## 层级与阻断

| 层（执法身份） | 核心问题 | 是否阻断 |
|---|---|---|
| Guard（hard） | 文件/数据/结构正确、可编译、无溢出碰撞、资产链完整 | 是 |
| 声明执法（declared） | 作者在 `theme.constraints` 写下的数字：留白/背景层/字阶/粗体/色相族 | 否（warn/hint，但点名是谁写的数字被超） |
| 留痕（trace） | 可读性 / 节奏 / 图表论点风险 / 字体键缺失 | 否（只进 `trace_summary`，不进对话） |
| Judgment | 审美、构图、节奏、应不应该这么设计 | 不属于验证层 |

trace 层在代码里**结构性禁止 error**（误写会被压回 warn），要升级一条留痕检查，
唯一合法方式是把它挪出 trace 层并说明理由——不是改级别。检查项自带 `layer` 字段；
密度测量（每页占用带 + 整副均值）每轮无条件归档进 `facts.density`（只进 JSON trace，
不是门槛），作者修订时对照「哪几页真的挤」自行判断。

**验证层不评分、不重新设计**：只有 PASS / BLOCK 二态。QA 只拦截生产级硬错误；
作者写下数字约束（`theme.constraints`）才执法，包不发明审美数字。

## 硬门（阻断）

| 任务 | 契约 |
|---|---|
| 文本 | 内容进 `text`，样式平铺顶层；框高 ≥ 字号×行高×行数（`TEXT_OVERFLOW`） |
| 填充 | Fill Contract；无效 fill 报编译错，不静默回退（`COMPILE_FAIL`） |
| 墨迹 | text–text/chart/image 相交即 `OVERLAP`；来源区永不许遮挡（`SOURCE_COLLISION`）；图表标签冲突走 `label_collision_policy`（`CHART_LABEL_COLLISION`），不缩字号 |
| 图表数据 | 每行 label + 有限 value；数值图齐 `source/unit/period/basis`（draft 警告、release 阻断）；同 metric 跨页同单位（`DATA_INTEGRITY_FAIL`） |
| 载荷 | schema 合法 ≠ 画得出来：行数据图须有可画行；`matrix` 要 points、`architecture` 要 layers、数字展示要元素级 `value`；空载荷阻断 |
| 空白 | `slides: []` 或零元素且无 background 的页阻断；有 background 的呼吸页合法 |
| 图表类型 | 白名单内且数据形态匹配（`CHART_TYPE_FAIL`） |
| 元素合法性 | schema / focus 唯一 / 几何合法（error 级归 `GUARD_FAIL`） |
| 资产链 | 有图缺有效 QC 不编译（`ASSET_WORKFLOW_FAIL`），见 `assets.md` |
| 编译与发布 | release 门 = 0 阻断 + 资产链凭证 + 预览证据 + Manifest |

## 留痕信号（只留痕，不阻断，不逐条修复）

| 信号 | 说明 |
|---|---|
| `direction_seed` | 方向发下的五个数字约束（留白/背景层/字阶/粗体/级差）——只执法作者/方向声明过的 |
| `contrast` | 声明色弱化字 <3:1 提示、<1.8:1 警示；正文级 <4.5:1 是硬门 |
| `palette_discipline` / `chart_style_drift` | 只执法 `constraints` 里作者声明的色相族/强调色距/标签规格上限 |
| `chart_argument` | 差异主张 + 零基长度编码 + max/min <1.25× = 差异不可见 |
| `deck_anchor` | 声明的眉标/页码有没有落、编号连不连续（位置恒定是设计判断） |
| `theme_fonts` | 字体键只读 cn/latin；未声明回落并点名 |
| `grid` / `typography` | 8 单位吸附（≤2px 豁免）；注释最小字号 |

## 执行默认值

**Canvas**：1280×720、16:9、12 列逻辑网格 + 8 单位基线。
**层级**：跨页连续只靠三锚（眉标固定上缘、页码固定象限、来源区固定位置）；五层：
背景 → 环境/媒体 → 结构/标题 → 内容/数据 → 焦点；焦点层原则上只有一个元素。
**字号阶梯**（驻点优先，相邻级差 ≥1.25×，每页 ≤4 级）：

| 级 | 驻点 | 区间 | 角色 |
|---|---|---|---|
| L4 Statement | 64 | 40–80 | 宣言、封面主张、KPI 主数字 |
| L3 Display | 44 | 40–56 | 页面主标题、Hero 结论 |
| L2 Title | 32 | 28–36 | 小节标题、图表标题 |
| L1 Lead | 22 | 20–24 | 导语、图表直接标注 |
| L0 Body | 17 | 16–20 | 正文 |
| L-1 Caption | 12.5 | 11–14 | 来源、注释、图例 |

行高：L4/L3 取 1.05–1.15，L2 取 1.15–1.25，L1/L0 取 1.3–1.5（中文取上限），Caption 1.2–1.3。
**Fonts**：方向种子用跨平台安全名（思源黑体/思源宋体/Arial/Georgia）。播放机缺字体会
自行替代且不提示——要保气质，交付环境装思源家族，或在 brief 覆盖 `theme.fonts` 为
环境确有的字族；不做字体嵌入（python-pptx 平台限制）。
**Color**：Accent 稀缺才有强调（≤5%）；层级优先用同色相明度阶梯；中性色带冷暖，忌纯灰。
**Charts**：准确 > 清晰 > 美观 > 装饰；趋势折线、比较条形、构成 ≤5 类、桥接瀑布；
一图一关系；直接标注优先于图例；一个强调点、三种语义色、八个类别封顶。
**Motion**：全套 ≤2 种姿态，默认 `still`；静态交付下内容层级独立成立。
**分组**：场 > 线（0.75–1px 发丝线）> 型 > 盒；卡片三准入见 `judgment.md` §4。

## Spec 字段速查

```python
theme = {"colors": {"background","surface","primary","secondary","ink","muted",
                    "accent","negative","premium","optional"},
         "fonts": {"cn","latin"},                     # display/body 是等价别名
         "constraints": {...},                        # 只写你真的要承诺的数字
         "chart_palette": {"primary","secondary","neutral","accent","negative"}}
```

`constraints` 可用键：`whitespace_min / type_step_min / bg_layers_max / bold_ratio_max /
max_charts / max_colors / hue_families_max / accent_hue_min / chart_label_scale_tol /
bg_layer_coverage`。写错键名被点名；**未声明一律不检查**。

**元素信封**：`id`（页内唯一）、`type`、`x/y/width/height`（数值，落 8 网格；任一维
≤2px 或通栏豁免）、`role`。填充四写法：`"#RRGGBB"` · theme token ·
`{type:solid,color,opacity}` · `{type:gradient,angle,stops×≥2}` · `{type:none}`。
**形状填充走 `fill`、描边走 `stroke`**——顶层 `color`/`line` 在形状上不生效。

| type | 专属字段 |
|---|---|
| `text` | `text size color align bold italic line_height max_lines wrap padding font family char_spacing uppercase opacity anchor` |
| `shape` | `shape`(rect/rounded_rect/ellipse/triangle/diamond/pie/line/arrow) `fill stroke stroke_width fill_role text` |
| `image` | `asset_id`（必需，清单绑定 src）`fit`(cover/contain) `crop asset_function overlay content_protection readability_exempt` |

`chart_kind` 全表（括号每页上限）：原生 bar/horizontal_bar/comparison_bar(8) · column(8) ·
line/trend/single_trend_line(8) · area(8) · donut/donut_composition/pie(8)；形状
process_flow(7) · timeline(7) · steps(6) · matrix(12) · waterfall(12) · architecture(3) ·
bubble(12) · ranked_bar(8) · progress_bar(6) · stacked_bar(8) · big_number_row(5) ·
sparkline(12) · kpi/executive_kpi/big_number（数字展示，读元素级 `value`）。未知 kind
在 Guard 阻断；缺载荷同样阻断。

**来源区**：`source_zone` 内只放 `role∈{source,method,metadata}`；其他可见对象与其相交
即 `SOURCE_COLLISION`（合格背景画心除外）。**整幅背景图可读**二选一：
① `layer:background` + `overlay`（opacity ≥0.20）+ 覆盖 ≥60%（免检）；
② 形状全幅罩必须烘焙进画心。**跨页锚**：plan 逐页发 `anchor`（≥4 页成套才有），
落成 `role=eyebrow` 与 `role=page_number` 元素，位置全 deck 一致。

## Spec minimum

```python
spec = {"canvas": {"width":1280,"height":720,"grid_columns":12,"grid_unit":8},
        "theme": {"colors":{...},"fonts":{"cn":...,"latin":...}},
        "direction": {"color_intent": [...]},
        "slides": [{"id":"s01","page_intent":{"insight":...,"focus":...},
                    "source_zone": {"x":48,"y":672,"width":1184,"height":32},
                    "elements": [...]}]}
```

## 执行模式与速度

| 模式 | 做什么 | 产物 |
|---|---|---|
| `spec` | 归一化 + Guard，不编译 | 判定报告 |
| `draft`（默认） | Guard + Compile | PPTX + 修复包 |
| `release` | draft 全部 + 出处硬门 + ghost 证据 + Manifest | PPTX + 预览 + Manifest |

| 项 | `--speed fast`（默认） | `--speed strict` |
|---|---|---|
| 资产 QC 像素域 | 长边 ≤1024 降采样；安全区纹理原分辨率 | 全分辨率 |
| 编译缓存探测 | size+mtime 快探针（分档不复用） | 整包 SHA-256 |
| 方向预览 | ≤`--ghost-pages`（默认 24）全量，否则方向采样 | 全 deck 逐页 2× 超采样 |

判定口径两档完全相同；`--deadline`（默认 120s）只跳过可选预览证据，不跳过核心正确性。

## Failure codes

`OVERLAP` `SOURCE_COLLISION` `CHART_LABEL_COLLISION` `TEXT_OVERFLOW` `READABILITY_FAIL`
`DATA_INTEGRITY_FAIL` `CHART_TYPE_FAIL` `COMPILE_FAIL` `GUARD_FAIL` `ASSET_WORKFLOW_FAIL`
→ BLOCKED，按 `fix_plan` 根因组一次改完（组内含 error 明细，零回读）。
其他 warn/hint → PASS，只进 `trace_summary`，不解释、不询问、不逐条修复。

## Release Manifest

`check --mode release` 生成：`source_spec_hash`、`validation`、`verification`、
`compile_report`（含 `output_sha256`）、`ghost_preview`、`asset_workflow`、`status`。
校验三件事：报告盖的 spec 戳与当前一致；PPTX 字节戳与磁盘一致（一次哈希比对）；
预览证据引用的页面都在当前 spec 内。`release_eligible` 仅在 release 档、编译通过且
发布凭证全有效时为真。

## 方向预览的覆盖契约

ghost 是**预览**，不是第二个渲染器：预览认的键名/载荷不得比 guard/compiler 更宽；
没实现同形几何的类型如实写「不渲染此图形 · 以编译产物为准」。预览不构成 QC：
release 门只认「预览证据存在且范围如实」。
