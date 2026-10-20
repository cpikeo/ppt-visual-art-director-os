# Changelog

仅记录行为差异、迁移事项与验证边界。已提交的详细历史见 Git；本次压缩前工作树副本随审计交付保存。

## 10.3.0 — 2026-10-20（safe_area 从提示词变成版面契约）

### 声明的字段必须有人执行

- **问题**：`safe_area` 一路只喂给成图 QC 的亮度采样（「这块区域要留白」），**版面侧无人校验**。实测：把标题从左侧压字区整体挪到右半区、压在高亮上，`--mode release` 依然 PASS（审计 E16）。更糟的是，仓库自带的资产样例自己就差了 4.8px 才进压字区（`x: 72` vs 左边界 76.8）——声明写了三个月，一次也没被执行过。
- **guard 新增 `safe_area` 规则**：页上声明 `safe_area`（0–1 归一化矩形，相对整幅背景图）后，图上每个文字元素的**锚点**必须落在区内——横向按 `align`（左/中/右）、纵向按 `anchor`（上/中/下），缺省左/上。判锚点不判外框：短文字配宽框是常态，用外框判会误杀左对齐标题，而锚点越界就是真把字放到了别处。越界报出「横向锚点 760px 在压字区 77–512px 之外」这种可直接修的量。
- **清单继承**：`--assets-manifest` 绑图时，页上没写 `safe_area` 就从清单条目继承（图是照着它留白的）；页上写了却和清单不一致 → **BLOCK**，因为那不是笔误而是「图按 A 留白、字按 B 排」。
- **两处豁免，都写进 contract**：`role ∈ {source, method, metadata}` 的页脚小字（它们本就压在页脚带上），以及显式 `safe_area_exempt: true` 的装饰性文字。`{}` 仍表示本页不压字。
- **实测**：审计 E16 的错位稿 `build_asset_shift.py` 现在 `BLOCKED`（`s01_t / s01_s` 两条 `safe_area`），修正到 `x: 88` 的对照稿 `PASS`；`audit/sm` 8 页 release 产物 **sha256 不变**（`cca264ae2bb1…`，54,940B）——没声明压字区的稿子零影响。
- **新增钉 6 个**（selftest 775 → **781**）：越界必拦 / 区内不误拦 / 页脚小字豁免 / 像素值报 schema / 清单继承 / 页-清单冲突 BLOCK。

## 10.2.0 — 2026-10-20（渲染冒烟进 CI：三度量对拍变成本地/CI 都能跑的门槛）

### 对拍不该只跑一次

- **新增 `tools/metrics_calibration.py --smoke`**：固定 8 段文本 × 4 档栏宽 = **32 探针**，一次编译一次渲染，**0.8 s** 跑完。选样不是均匀抽样，是「曾经出过事的形状」：混排百分比、数字+单位、长句、极窄栏（160px）。
- **门槛只有两条，都对准危险方向**：
  - `guard 低估 == 0`：guard 报的行数少于真排 = 放行一个会溢出的框，是这类错误里最坏的；高估（多报一行）只是让作者删一句能排下的话，属安全方向，只报告不拦。
  - `ghost 不一致 ≤ 2`（`--max-ghost-mismatch`，棘轮）：已知的两处都在 ≤9 字/行的极窄栏，真值只有 PowerPoint 能给；多一个就红——那说明预览开始说谎。
- **新增 workflow `.github/workflows/render-smoke.yml`**：nightly（03:00 JST）+ 手动 + 只在 `scripts/**`、`tools/metrics_calibration.py`、本文件变更时触发。装 `libreoffice-impress`/`poppler-utils`/`fonts-noto-cjk`，把 `soffice --version`、`pdftotext -v`、`fc-list | grep -c "CJK SC"` 打进日志（换渲染器 = 换仲裁者，数字必须能对上版本），探针明细作为 artifact 留 30 天。`ci.yml` 的必跑矩阵仍然零外部渲染器——冒烟是另一条更慢的线。
- **顺手修掉一个让 CI 直接跑不起来的坑**：`metrics_calibration.py` 的 `--scripts` 默认值写死成 `/home/user/repo/scripts`，换目录/换机器就找不到模块。改为按工具自身位置解析，并加钉禁止 `tools/` 下再出现写死的绝对路径。
- **实测（本地，LibreOffice 25.2 + Noto CJK）**：32 探针 · guard 一致 30/32（**低估 0**、2 处高估）· ghost 一致 30/32（2 处：`deck_s07_body_160` 少算一行、`mix_pct_160` 多算一行）· 退出码 0。
- **新增钉 2 个**（selftest 774 → **775**）：工具无写死绝对路径。

## 10.1.0 — 2026-10-20（plan.json 默认瘦身：决策全留，重复句上提）

### 体积是作者要付的上下文成本

- **默认瘦身，`--full` 保留完整推演**：`vao plan` 落盘的是 `intelligence.compact_plan()` 的投影；完整 bundle 仍原样返回给 CLI/遥测/资产链（判断没有第二套）。
- **删的都是「可推导或重复」**，判断一个字不删：
  - `understanding.numerals` 只留原文（`value/unit/year` 由 raw 推出）；8 个布尔只列被置真的（false 是默认态）。
  - `visual_role.alternatives` / `focus.rejected` / `composition.rejected` 只留名字（否决理由属复盘，`--full` 里看）。
  - `production.must_place` 压成 `"role:type"` 字符串。
  - 同一列表里**重复出现**的说明句（如每条 `weaken` 尾巴上的「支撑证据：与结论同屏但小一档…」）抽出来只说一次，进 `deck.legend["information_weight/weaken#通用说明"]`；只出现一次的是这一项特有的判断，原样保留。
  - 全稿唯一取值的规则句（`typography.scale.limit` 的「22–45 汉字/行…」等）上提到 `deck.legend`，页内不再抄。
- **实测体积**（`json.dumps(ensure_ascii=False)` 字符数）：
  | 样本 | 完整 | 瘦身 | 降幅 |
  |---|---|---|---|
  | 8 页（东京开店 brief） | 26,072 | 18,602 | **−28.7%**（≈11.8k → 8.5k tok） |
  | 40 页（big.yml） | 117,680 | 67,666 | **−42.5%**（≈53.5k → 30.8k tok） |
  省下来的主要是「同一句说明在多页重复」，所以页越多省得越多——这也是为什么判据不用魔数，而是「≥15% 且随页数单调更省」。
- **纯函数**：投影深拷贝要改的块，输入 bundle 不被修改、结果幂等（首版忘了深拷贝，`compact_plan(bundle)` 会把调用方的 plan 一起改掉，测「前后对比」时量的是被改过的输入——已修并加钉）。
- **逃生口有证据**：`--full` 产出的 `composition.rejected` 每项都带 `why_not`，且文件比默认版大（selftest 直接跑两条命令比大小）。
- **新增钉 4 个**（selftest 770 → **774**）：瘦身 ≥15% 且随页数更省 + 纯函数幂等；14 个决策位 × 全页逐位相等（含 numerals 原文与 must_place 角色序列）；`deck.legend` 的每句话逐字来自完整版；`--full` 保留 `why_not` 且体积更大。

## 10.0.0 — 2026-10-20（删除 chart_kind 别名表 · 旧名不再是合法输入）

### 破坏性变更：旧名从「兼容」变成「错误」

- **别名表删除**：`primitives` 不再有 `CHART_ALIASES` / `resolve_chart_kind` / `apply_chart_alias`，`CHART_KINDS` 就是 `CHART_SPEC` 的 19 条。编译器、预览、guard 三处入口的归一步骤同时删除——名字只剩一种，就没有「归一」这件事。
- **旧名一律报错**：`horizontal_bar` 等 7 个退役名在 **draft 也拦**（此前只在 release 拦）。失败码仍是 `CHART_KIND_ALIAS`，报错给出 canonical、该名当年隐含的默认值（`show_values: false`）与改名命令；未知 kind 仍走 `CHART_TYPE_FAIL`，两类错误不再混在一起。
- **只留一张退役表**：`RETIRED_CHART_KINDS`（7 条）+ `retired_chart_kind()`，只服务报错文案与迁移工具，**不参与任何渲染**。9.37 的 `reject_chart_kind_alias` 规则开关随之删除——门已经是硬的，不需要旋钮。
- **迁移证据（可执行）**：`tools/rename_chart_kinds.py --audit <dir>` 扫描输入文件（.py/.json/.yml/.yaml）里的退役名，逐条给「文件:行 → canonical」，有残留退出码 1。仓库自身与三份样本稿均为 0 处（`--audit .` 输出「迁移完成」）。
- **仓库内自测随之迁移**：3 处 fixture 仍写着 `comparison_bar` / `donut_composition`，被新门一一拦下后改为 canonical——门咬住了才会发现它们。
- **selftest 775 → 770**：删掉 4 条「旧名仍可编译」的断言（前提已不存在），新增 4 条：别名表确实不存在、旧名在任何档位都拦且报错可执行、未知 kind 与退役名分属两个失败码、`--audit` 能看见旧名并给出文件:行。

### 升级方式

```bash
python3 tools/rename_chart_kinds.py <你的 build.py 或 plan.json> --audit .   # 先看有没有
python3 tools/rename_chart_kinds.py . --write                              # 一次改完（含默认值）
```

## 9.37.0 — 2026-10-20（旧 chart_kind 名在 release 档成为硬门 · 批量改名工具）

### 合并只有配上期限才算合并

- **release 档拒绝旧名**：`release_guard_rules("release")` 现在置 `reject_chart_kind_alias: True`，`chart_kind_alias` 由 warn 升为 **error**，规则映射到失败码 `CHART_KIND_ALIAS`（进 `BLOCKING_CODES`，修复包给一句话的改法）。draft 档行为不变（仍是 warn）：旧稿还能跑，但交付环节必须写 canonical。默认值仍是 False，库内直接调 `check_spec` 的调用方零变化。
- **批量改名工具 `tools/rename_chart_kinds.py`**：把 plan/build 里的旧名一次换成 canonical，并**原子补齐该名隐含的默认值**（`horizontal_bar / donut_composition → show_values: false`）。少了这半步，只改名会让横条图突然长出数值标签——那是改图，不是改名。
  - `.py` 走 `ast`（dict 字面量与 `dict(chart_kind=...)` kwargs 两种语法都覆盖），`.json` 走自带的只记偏移扫描器（stdlib json 不给位置）；两者都按 **UTF-8 字节偏移**做精确替换，不重排、不重新序列化，注释与缩进原样保留。
  - 语法细节分档处理：`.py` 补 `show_values: False`（Python 字面量），`.json` 补 `"show_values": false`——写混了不是格式问题，是 NameError / 非法 JSON。
  - 默认干跑打印 unified diff，`--write` 落盘；退出码 0 = 无需改/已写入、1 = 干跑有待改、2 = 输入不可读，或改完仍有非字面量写法（f-string、变量拼接）没改干净。后者会逐条打印但**不改文件、不假装成功**。二次运行输出「没有旧名」，天然幂等。
  - 实测：同一份 spec 改名前后编译产物**逐字节相同**（`.json` 与 `.py` 各一例）；`audit/charts/chart_build.py` 的 `horizontal_bar → bar` 迁移后产物仍 `09c5b74a…`，预览逐像素不变。
- **仓库自测同步迁移**：`selftest` 里一处 release 正向样例原本写着 `comparison_bar`，被新门拦下——这正好证明门真的咬住，已改成 `bar`。
- **新增钉 3 个**（selftest 772 → **775**）：draft warn / release error + 失败码在 `BLOCKING_CODES`；改名工具干跑不落盘、`--write` 改名补默认、二次运行幂等；改名后产物与改名前逐字节相同。

## 9.36.1 — 2026-10-20（饼/环预览按短边取圆：不再把宽框拉成椭圆）

### 由 chart_kind 普查顺手抓到的预览谎报

- 基准：900×400 的元素框里画 donut。`soffice --convert-to pdf` + `pdftoppm` 实测真实产物的环外接为 **394×394**（圆内接于绘图区），而 `ghost.py` 直接把 `(left, top, right, bottom)` 当外接矩形传给 `pieslice`，预览画出 **900×400 的扁椭圆**，环心孔却按短边算成了圆——同一张图里几何自相矛盾。作者按椭圆的留白改构图，产物却是圆的。
- 修法：半径取 `min(宽, 高) / 2`，圆心不变；扇区颜色、文字反色、环心 KPI 全部不动。**只改预览，不改产物**：8 页样本 `out13.pptx` 仍为 `cca264ae…`，LibreOffice 渲染逐像素未变。
- 影响面：donut / pie 两类（含旧名 donut_composition）的预览；基准方框（宽=高）的页逐像素不变。
- **发布清单标注**：`release_manifest` 的 notes 标签新增「图种别名」（此前旧名告警会落到泛化的「非阻断」，作者读完不知道动哪里）。实测含 `horizontal_bar` 的 2 页样张：产物 `09c5b74a…` 未变，notes 出现 `[图种别名] chart_kind='horizontal_bar' 已并入 'bar'（默认 show_values=False）…`。
- **新增钉 1 个**（selftest 771 → **772**）：宽框里的 donut 环外接必须近正方形且直径不超过短边。

## 9.36.0 — 2026-10-20（26 个 chart_kind 合并为 19 条渲染路径 · 旧名走别名表）

### 一个 kind 一条渲染路径，同图异名的写法不再各留一份分支

- **先证伪再合并**：新增 `tools/chart_kind_survey.py`——同一份载荷（`rows/points/layers/value`）逐 kind 编译 + `ghost_page`，对 **PPTX 字节**与**预览 PNG 字节**双取 sha。结果：`kpi = executive_kpi = big_number`、`bar = comparison_bar`、`line = trend = single_trend_line` 是**字节级同义词**；`horizontal_bar` 与 `donut_composition` 只是**缺省值**不同（`show_values` 默认关），显式同参时字节全同。其余 19 种（column、area、pie、waterfall、ranked_bar、progress_bar、stacked_bar、bubble、process_flow、timeline、steps、matrix、architecture、sparkline、big_number_row…）产物各不相同，**不是别名，不合并**。
- **`primitives.CHART_SPEC` 只留 canonical（26 → 19）**，旧名进 `CHART_ALIASES: 旧名 → (canonical, 该名隐含的默认值)`；`CHART_KINDS` 仍等于「可写的全部名字」（19 + 7 = 26），所以旧稿不被拒。
- **归一函数只有一处**：`resolve_chart_kind()` / `apply_chart_alias()`。compiler 的 `add_chart`、`add_native_chart`、ghost 的图表分支、verify 的 `_check_chart` 与 `_check_metric_units` 在**读 kind 之前**统一归一，下游代码里的 `kind in ("line", "trend", "single_trend_line")` 这类三合一判断全部消失。`apply_chart_alias` 返回新字典，不覆盖作者显式写的字段。
- **旧名隐含默认值落成显式字段**：`horizontal_bar` → `show_values=False`、`donut_composition` → `show_values=False`；缺省名单因此只剩 `bar / column / donut` 一处。合并前后 **26 个写法的 PPTX 逐字节未变**（`tools/chart_kind_survey.py --compare`），LibreOffice 渲染逐像素一致。
- **guard 对旧名出声**：新增告警 `chart_kind_alias`（warn，不阻断），提示 canonical 名与该名隐含的默认值——否则「为什么这张横条图没有数值」又要靠猜。
- **判断层同步**：`intelligence` 的成对比较建议从 `comparison_bar` 改为 canonical `bar`。
- **工具可跑基线**：`chart_kind_survey.py --scripts <旧工作树> --outdir <目录> --compare <基线 json>`，缺 `CHART_ALIASES` 的旧检出会退化成恒等映射，保证「合并前」由同一份代码路径生成。
- **新增钉 3 个**（selftest 768 → **771**）：旧名归一 + 隐含默认只补缺 / 旧名产物与 canonical 逐字节相同（编译四次比 sha）/ guard 旧名只告警不拦。

## 9.35.0 — 2026-10-20（三度量统一：guard / ghost / PPTX 一套折行与度量 · 字阶表单一来源）

### 同一段文字不再由三套判据各算一遍

- **折行只有一份实现**：`ghost._wrap_lines` 与 `verify.estimate_lines` 此前各自成篇（一个逐字贪心 + PIL，一个是「总宽 ÷ 栏宽」的估算）。现在折行核心在 `primitives.wrap_lines`，guard 与预览只提供「一个字有多宽」的度量函数（`primitives.measure_text`：能解析到主题字体就用真字面，解析不到回落宽度表）。
- **混排边界间距计入度量**：CJK↔拉丁每个边界渲染器会多让 0.22 em（实测 LibreOffice 25.2 + Noto CJK：单边界 +0.217 em、双边界 +0.450 em，与方向无关）。漏掉它，`11.8%` 这类混排会少算一行。
- **行首空白不计宽 · 行尾句读点可悬挂半个字**：前者曾把 `7,100 万日元` 拆成两行；后者曾把「一行差一个句号」的 26 字句判成两行，逼作者白删内容。
- **数字与单位退无可退时的紧急断行**：窄栏里「数字+单位」在本行怎么都放不下时，旧逻辑回退到行首 1 个字（实测 `7,100 万日元` 被拆成 9 行）；现在数字自占一行、单位下行，与 Office 一致。
- **guard 的余量只加在窄栏**：对拍 128 个探针（`tools/metrics_calibration.py`），不留余量时有 1 个探针比真实排版少算一行（会放行溢出，发生在 8.9 字/行）；按比例留 1% 虽把低估压到 0，却让 11 个框被多算一行。最终取「每行不足 12 字时让出 0.1 个字宽」（`verify.GUARD_NARROW_*`）：低估 0、多算 6，且判据有物理解释。
- **对齐结果**（`tools/metrics_calibration.py`：编译 → LibreOffice → `pdftotext -bbox` 逐行读词框；LibreOffice 缩字自适配的页自动剔除）：guard 122/128、ghost 126/128 行数一致；guard 的 6 个偏差全部是「多算一行」方向。
- **字阶一张表**：`primitives.TYPE_SCALE`（1280 宽画布）合并了散在 compiler 的 18/16/14/12/40÷3 与 ghost 的同名默认值；plan 的 `deck.type_scale` 与骨架里的字阶行都由它派生，逐页只给档位（`stat/display/title/...`）与像素值，不给坐标。
- **新增钉 8 个**（selftest 760 → **768**）：guard/ghost 逐宽度行数一致 / 字面缺失时宽度表只高估不低估 / 行首空白不占位 / 余量只加在窄栏 / 编译器缺省字号取自 TYPE_SCALE / 画布变宽整套等比放大 / deck 级字阶表 + 逐页档位 / 封面走 display 档。

## 9.34.0 — 2026-10-20（PPT_CASE_004 实测回流 · 瀑布桥小计死代码 / 柱顶值契约 / 构成图扇区反色）

### 真实案例（PPT_CASE_004 · 15 页高端静奢红酒融资路演）逐页跨渲染器对拍抓出的三处静默分歧

- **瀑布图小计段死代码（真缺陷）**：`compiler.py` 与 `ghost.py` 的 `waterfall` 分支均写了 `row.get("subtotal") or row.get("is_total") or row.get("total")` 从零轴起画整段并跳过跨小计桥接虚线，但上游唯一行解析 `primitives.chart_rows` 构造归一化行字典时漏掉了该布尔标记——导致两侧的小计分支**同时退化为死代码**。`PPT_CASE_004` P11（`240 - 18 - 19 → 毛利 203 [subtotal] - 62 → 营业利润 141 [subtotal]`）实测中，小计 `203` 被当成增量叠到 `406`。现由 `primitives.chart_rows` 统一透传 `subtotal`，编译与预览同步恢复零轴小计柱、强调色填充与桥接断口。
- **瀑布图 `show_values` 静默失效与预览柱色分叉（真缺陷）**：
  - `verify.py` 将 `waterfall` 归入 `NUMERIC_CHART_KINDS`：声明 `unit` 而未开 `show_values` 时报 `chart_unit_invisible` 提示「要显示请 `show_values: true`」；但作者开启 `show_values: True` 后，告警虽消失，`compiler.py` 与 `ghost.py` 却完全未消费 `show_values`，图上仍无任何数值/量纲。现两侧同步消费 `show_values`（默认 `False` 保持向后兼容；显式开启时于每段柱顶落居中可编辑数值与 `unit`）。
  - `ghost.py` 正向瀑布柱曾硬编码为 `ink`（黑条），忽略 `chart_primary_color` 与 `secondary_color`，与产物（`primary` 酒红条 / `secondary` 石灰灰条）分叉；现统一走 `chart_primary_color` 与 `secondary_color`。
- **构成图（`donut / donut_composition / pie`）逐扇区标签色坍塌与预览分叉（真缺陷）**：`compiler._native_chart_text` 将 `plot.data_labels.font.color` 统一设为 `ink`（深色），而各扇区实色由 `series_palette` 跨明度派生——`PPT_CASE_004` P09 深叶绿扇区 `#2E372D` 上落 `#1C1A19` 黑字，实测对比度仅 `1.18:1`；与此同时 `ghost.py` 一律画 `background` 浅字，在浅暖金扇区上反向失真。现 `compiler.py` 与 `ghost.py` 逐扇区统一走 `ctx.auto_text_for(palette[i])`（深扇区反白、浅扇区深墨），并在 OOXML `point.data_label` 完整写入 `a:ea / a:cs` 中文字族、`show_category_name`、`show_value` 与 `number_format`。
- **新增钉 5 个**（selftest 751 → **756**）：`chart_rows` 透传 `subtotal/is_total/total` 且小计零轴起算不跨桥接 / `waterfall` 开启 `show_values` 在产物与预览同形落柱顶值与 `unit` / `waterfall` 预览正负柱色与产物 `primary_color` 同源 / `donut` 逐扇区 `auto_text_for` 反色且保留 `a:ea` 中文字体 / `donut` 预览扇区文字明暗与产物同向。

## 9.33.0 — 2026-10-20（第四轮审计 · 规范—代码一致性；基线仍 684ff0a；包版本 9.33.0）

### 把「规范说了、代码没做到」变成可执行断言

方法：把 SKILL.md / references/*.md 的规范性句子逐条改写成断言（`audit/spec_conformance.py`，52 条），
跑出三处真实分歧并修掉；其中一处由新判据当场抓出作者稿里的静默失效。

- **未消费字段（真缺陷，最贵的一类）**：契约写「未消费字段必拦」，guard 只硬编码拦过 `content` / `style` / `line` 四个已知写法。实测 `font_size: 40`、`colour`、`maxlines`、`align_left`、`spacing`、`bold_weight` **全部静默通过**——作者写了字号，产物还是默认字号，所有硬门全绿。现按两档判定：
  - **疑似写错**（归一化同名 / 复合词 / 词尾 / 相似度 ≥0.86）→ `error`，给出候选字段名（`font_size` → `size`、`maxlines` → `max_lines`、`spacing` → `char_spacing`）；
  - **完全对不上的未知字段** → `warn`（可能是作者自己的注解，不假拦）。
  字段白名单**不手抄**：`verify.consumed_fields()` 首次调用时扫 compiler / ghost / verify / primitives / assets 的 `.get("x")` 与 `["x"]`，得到「渲染器真的会读的名字」集合（361 个），另加动态键读取的 13 个字段；读不到源码时返回空集（该项检查自动跳过，绝不假拦）。冷启 3.8ms、热 0.003ms，24 元素页 guard 增量 +0.24ms。
- **归一化不幂等（真缺陷）**：`_snap_span` 的 docstring 承诺「幂等」，随机 400 例实测 **307 例二次归一漂移**（如 y=146 → 144）。根因：尺寸被圆整时按中心吸附，留下「边不在网格、中心在网格」的几何；下一趟按边吸附又把它挪走 ≤grid/2。单次归一不动，但编译 / 预览 / 复验只要有一方重新归一，对象就与 guard 认证的位置差 2px。现以「中心已在网格上则保留」收口，实测 400/400 幂等。
- **渐变 `stops<2` 不在编译前拦**：契约的填充四写法要求 ≥2 个 stop，实际只有编译器抛 `COMPILE_FAIL`。guard 现在提前给出「补第二个 stop 或改 solid」的可修诊断（判定不变，省一次编译）。
- **文档措辞与代码对齐**：contract「判定边界」按实测拆成 **拦**（含疑似写错字段、渐变 stops<2）与 **告警不拦**（对不上的未知字段、非 `ranked_bar` 的 `target`、不可见 `unit`）；「归一化与网格」改为代码真正承诺的语义——**中心落网格、边不保证是 4 的倍数、二次归一不位移**（原文「几何按 4px 机械吸附」会让作者以为坐标一定是 4 的倍数）。
- **新判据当场抓出作者稿缺陷**：`audit/e2e/build_author.py` 里两张图写了 `"grid": False`（编译器里网格线恒关，`grid` 不是受支持字段）——此前静默通过，现在被拦，作者删掉该字段后 PASS。这正是这条判据要防的事：作者以为关掉了网格，其实什么都没发生。
- **新增钉 5 个**（selftest 746 → **751**）：疑似写错字段拦下并给候选 / 下划线写错同样拦 / 未知字段只告警不假拦 / 合法字段零噪音 / **docs↔code：contract.md 点名的每个字段都在渲染器消费集里**（把「文档写了、代码不认」变成回归）。
- **验证**：selftest **751/751**、bench **57/57**、四组冻结泛化 81/31/14/8 不变、`audit/spec_conformance.py` **52/52**、E2E `release --strict` PASS（0.35s，6 页 ghost + 60KB PPTX）。
- **未验证**：目标 PowerPoint 渲染与视觉终验；Windows / 远端 CI。

## 未发布 — 2026-10-20（第三轮审计 · 基线 684ff0a；包版本仍为 9.33.0）

### 证据形态判断修复 + 文档密度重构 + 量具诚实性

**A · 判断链：证据形态（intelligence.py）** —— 用 20 个跨行业未见案例（医疗 / 教育 / 零售 / 公益 / 工程 / 金融 / 制造 / 农业 / 组织）同机对照基线 HEAD：证据形态 **9/20 → 17/20**、页面角色 **10/20 → 17/20**（余下 3 例为保守判定，逐例见审计报告 §4）。

- **并列可比量进同一形态**：同一单位 ≥3 个不同取值（`实训课 82%／直播课 61%／录播课 44%`、`支座脱空 27 处／裂缝 64 处／渗水 41 处`）此前落到 `none`，页面被判成观点页（`role=establish / focus=statement_text`），作者拿到的是「立一句话」而不是「把可比的量排齐」。单位相同只是必要条件：多量纲页再验一次指标名归属——`1.9 元利润 / 6.2 元履约成本 / 58 元客单价` 仍是多指标面板，不是并列项。
- **`comparison` 标志与证据形态拆开**：并列量成立的是形态，不是「两端有胜负」。三档报价并排仍是 `comparison` 形态、`comparison=false`（冻结泛化 G04/G23/R03 因此保持原判）。
- **分解关系**：`设备 3,200 + 产线改造 1,100 + 数字化 500 = 4,800 万元`、`教师培训 21／设备 12／监测 5／其余为差旅` 此前无「占 / 其中 / 其余」字样就不成立 `part_whole`（「其余」判据还要求同单位子项）。新增纯算术校验 `_sums_to_total`（≥3 个部分加总等于另一取值，容差 0.5%）与「其余 + ≥2 同单位取值」。**要求 ≥3 个部分**：两项相加等于第三项在比率 / 日期里太常见（`缩短 1.8 天 ＋ 现值 6.6 天 ＝ 原值 8.4 天`、`0.8% ＋ 1.1% ≈ 2%`），那不是作者写下的构成，是算术巧合。
- **分期不再冒充时间轴**：`一期投产 14 个月…`、`一期投入 4800 万元（设备／改造／数字化）` 因「一期/二期」被硬拉到 `sequence`（0.9 压过所有数据形态），投资拆解页因此被判成流程图。现在分期要成为可排的承诺轴，需**每期各带同单位量**（`一期 1,200 万；二期 1,800 万；三期 1,800 万`，自检既有期望），否则只是项目名（权重 0.7）。
- **并列判据先剥括号注记**：`电力 1,240 度（−80 度）` 的括号增减量不是第三项（`_strip_parenthetical`），拆项行不再被读成四个可比取值。
- **计量词表补齐计数单位**：`处 / 项 / 条 / 起 / 所 / 栋 / 册 / 辆 / 架 / 艘 / 门 / 款` 进 `_NUM` —— 缺陷清单、整改台账这类页面此前整页落到「无证据」。

**B · 结构预览（ghost.py）：数字内部不断行**

- `_cjk_break_fix` 补**数字 token 不可拆**：断口落在同一个数字内部时整 token 推下。实测（E2E）标题「回收期从 2.6 年拉到 3.9 年」在 440px 预览里断成 `2.` / `6 年`，`压到 18%` 断成 `1` / `8%`——行首行尾都像正常文本，靠读行发现不了；PowerPoint 不在数字内部断行，预览断了就在替真实排版说谎。既有禁则（行首标点 / 数字与单位 / 双字单位腰斩）未动。新增钉 1 个（扫描 250 个宽度，断言无「小数被断开」与「% 与数字分家」）。

**C · 量具：判断基准不再把 100% 说成全路径验证（bench.py）**

- `--ablate` 输出**覆盖缺口**：15 组语义词表中 13 组消融后指标不变 = 这 57 例不判别那些路径（人 / 现场 / 结论词 / 比较词 / 序列词 / 结构词等）。此前报告只印「准确率 100%」，读者与后续代理会把「没测到」读成「已验证」。README 同步写明该读法。

**D · 文档密度重构（信息不减，删重复与铺陈）**

| 文件 | 字符 | 变化 | 处理 |
|---|---|---|---|
| `SKILL.md` | 6,997 → 5,754 | −17.8% | 六条哲学并句；素材职责改表；「整套回看」从判断链末行移入 §3 全篇节奏（原先两处重复）；删「删除候选交作者裁决」等三处复述；`每页先答五问` / 三态主张 / 判断陷阱 / 停止信号原样保留 |
| `references/contract.md` | 5,896 → 5,300 | −10.1% | 「执行模式与速度」「安全发布」与 README 各写两份 → 单一权威（本文件），README 改为引用；失败码并一行；字段速查无删项 |
| `README.md` | 4,548 → 3,821 | −16.0% | 安全条款压成「三条纪律 + 指向契约」；判断基准段写明消融读法；快速开始不再列 references 三遍 |
| `templates/brief.yml` | 6,020 → 5,874 | −2.4% | 执行命令第 4 份副本改为指向 §5（命令唯一说明在 SKILL） |
| `references/assets.md` | 5,193 → 4,945 | −4.6% | 逐条保留字段与硬边界；家族/复用的重复解释并句 |

AI 上下文三件（SKILL + contract + assets）：32,302 → 27,245 bytes（−15.7%）。判断基准以 `verify.py` / `CHART_SPEC` 为唯一来源，文档只指路不抄录（避免双写漂移）。

**E · 验证（本机实测，Python 3.13.16 / Linux）**

- selftest **744/744**（637 基线 + 本轮新增 1 钉）；bench **57/57**（准确率 100%，未改动期望）；四组冻结泛化断言 **81/81 · 31/31 · 14/14 · 8/8** 不变。
- 跨行业未见案例（`audit/cross_industry.py`，20 例，与基线 HEAD 同机对照）：证据形态 **9/20 → 17/20**，页面角色 **10/20 → 17/20**；修复覆盖 M02/M04/M05/M06/M07/M09/M13/M14 八例，M15/M19/M20 仍保守（见报告 §4）。
- E2E：6 页中文经营决策稿 `plan → 手写 BUILD → release check --speed strict` PASS，0.19–0.52s，6 页 ghost + 60KB PPTX；`stacked_bar` 误用被口径硬拦（`data` vs `categories+series`）1 次，按修复包一次改正。对比基线 HEAD 同一 build：`check` 中位 53.9ms vs 53.9ms，`plan` 中位 51.0ms vs 47.8ms（噪声内）。
- **未验证**：目标 PowerPoint 打开 / 编辑 / 断行 / 投影可读性（本机无目标环境）；视觉审美终验未做。ghost 只证明结构方向。

## 未发布 — 2026-10-20（第二轮审计 · 基线 2a51a44；包版本仍为 9.33.0）

### 判断链与资产链的断链修复（P1–P5）+ 预览/产物同源（P6）

- **P1 asset_function 词表同源**（assets.py）：`ASSET_FUNCTION_PHRASES` 补齐文档契约六值（hero/proof/emotion/context 的用途短语此前在提示词构建里**静默丢失**——实测 `build_asset_prompt(..., asset_function="hero")` 输出不含该值）；删除三个零消费者的死键（direct/contextualize/immersive）；`validate_asset_card` 点名未知值；`build_manifest` 对既有素材缺省 `frame`，与生成路径同一缺省，不再两套口径。SKILL/assets.md/模板注释同步。
- **P2 主体缺口提问接通**（intelligence.py）：媒体提问的主体分支此前不可达（死分支）——`decision=reuse` 且 `media.direction.need_asset=False` 时永远走不到。现挂到 `decision ∈ (required, reuse)` 且无 `asset_subject`/`asset_source` 的页面上，问题模板改为「准备给这页什么素材？…或取自页面标题与正文」。
- **P3 视觉分量与高潮入 plan**（intelligence.py）：`_coherence_pass` 新增 `judgment.emphasis{level:climax|lead|support|quiet, why}` 与 `coherence.climax{page, why}`；climax 优先级=最后的请求/决定页 → 首个主视觉（required/reuse 非 frame）页 → 首个有 claim 的 establish 页；`build_skeleton` 逐页输出视觉分量行与高潮行。rhythm 键集随 climax 扩一位，既有键值未动。
- **P4 brief 模板补全**（templates/brief.yml）：媒体声明（kind/function/asset_function/safe_area/allow_crop/text_color）此前无示例声明，「无声明只作轻提示」对作者不可见；补注释与示例。
- **P5 主张抽取误判修复**（intelligence.py）：「X 不到 Y 的三分之一」类比较句被判成话题题（claim absent / evidence none，E2E 实测发现）。「不到」补入 `_TITLE_ASSERTION` 与 `_COMPARISON_WORDS`（与「低于/不足」同族）；名词化门改为名词化形状不否决带断言谓语的标题。与既有阈值语义一致（「上线不到两周」判 comparison 不变）。
- **P6 ghost 单序列条/柱取色与产物同源**（ghost.py）：bar/column 单序列分支硬编码 `ink`，无视 `chart_primary_color`（颜色角色系统的作者逃生口）——实测产物 `series=#8A8984`（primary_color=muted 生效）而预览画墨条，预览把「强调哪一项」画错。现与编译器同一条规则（含「有高亮且基础==accent 时让位 primary 角色」）。
- 新增钉 21 个：`test_art_direction_linkage`（词表同源/提示词透传/死键点名/existing 缺省/主体缺口提问/emphasis-climax 传递/「不到」断言/名词化门对照）与 `test_ghost_chart_color_single_source`（像素级取证预览=产物）。
- **端到端实证**：5 页中文经营评审稿（/home/user/e2e）走 `plan → manifest（提示词含 hero 职责短语）→ 资产 QC（2 轮 block 后 accept：contrast_suitability、subject_position 精确点名）→ check --mode release --speed strict PASS → 5 页 ghost + pptx`。QC 拦截与修复循环是链路正常工作的证据。
- 验证：selftest **743/743**、bench **57/57**、四组冻结泛化断言不变（81/31/14/8），复跑通过。judgment_cases.json 57 案例期望未动。目标 PowerPoint 渲染与独立视觉终验仍未验证（见报告 §6）。

## 未发布 — 2026-10-20（基线 d0fb621；包版本仍为 9.33.0）

### 设计判断基准升级为完整艺术指导标准（SKILL.md §1–§3 / §6）

- **身份与工作流**：§1 升为 Visual Art Director + Editorial Art Director 标准统筹摄影/背景/插画/图表配图/图标/装饰元素；新增页内微循环「理解 → 判断 → 编排 → 构图 → 执行 → 校验」，写明「先理解内容与叙事再确定视觉概念、先判断素材职责再构图与执行、先统筹整套视觉关系再落实单页细节」，明确不将艺术指导退化为风格套用、素材堆砌或规则化排版。
- **设计哲学**：§2 增补核心原则（内容决定视觉，主张决定焦点，证据约束表达，构图组织关系，对比建立张力，统一塑造品质，变化推进叙事，留白维持呼吸）与最终标准（主体突出而不突兀…设计大胆而有秩序；单页有表达与构图，全篇有艺术方向与节奏）。新立两条纪律：**层级用六件工具**（尺度/位置/明暗/色彩/视觉重量/留白；主张、证据、图像互相支持，不为视觉冲击弱化关键内容或制造虚假关联）、**对比集中爆发**（尺度/景别/明暗/色彩/疏密/虚实/材质/视觉重心的差异要有目的，避免平均用力与无意义视觉冲突）；「统一的是表达逻辑」「内容驱动视觉」两条写明统一的是审美原则与表达逻辑而非每页布局，按叙事阶段在一致性中形成有依据的变化。
- **判断链与素材导演**：§3 焦点行纳入视觉主角与注意力路径，跨页节奏行纳入叙事阶段（主视觉/证据展开/过渡/停顿/结论），整套回看行纳入「视觉高潮必须对应内容高潮」；素材导演重构为职责制——背景（氛围/语境）、主体图像（核心视觉：大幅主视觉/局部特写/非对称/边缘裁切/前景遮挡/负空间，协调主体比例、透视、方向与文字区域）、辅助图像（补充语义）、图表（数据关系）、插图（解释/概念）、图标（识别），增对比与构图张力、全局统一、图标族规范（线条/端点/填充/比例/视觉重量同族）、素材质量清单（来源/相关性/清晰度/裁切/主体完整性/透视/光影/色彩协调/文字可读性；优先复用，避免重复生图）；新增「全篇视觉叙事与节奏」小节（关键页给足视觉权重、次要页保留呼吸、避免连续同质化与每页争抢注意力），与 plan 的 rhythm 枚举对齐。
- **QA**：§6 明写「区分结构检查与真实渲染验证……不得以规则通过或预览正常替代审美验收」；素材人工验收从五项扩为六项：语义（含素材与内容一致性）、焦点与对比（对比是否有效且集中）、主次与协调（图像与文字在实际页面是否协调）、清晰度（含裁切/透视/光影）、连续性与节奏（含页面间节奏与视觉高潮落点）、删除测试。停止信号增「对比有效而不刺眼 · 全篇方向统一、节奏有据」。
- `references/assets.md` 增「素材家族与复用执行」（家族一致来源链、图标族执行、复用优先、一次批量）；README 对齐哲学表述与质量边界。**运行时行为不变**：plan / check / verify / ghost / compiler 判据与输出未动，judgment_cases 冻结期望未动；文档结构钉（六节、逐页五问、退役名）保持。
- 验证：selftest **720/720**、bench **57/57**、四组冻结泛化断言不变，复跑通过。目标 PowerPoint 与专业视觉终验仍未验证（SKILL §6）。

## 未发布 — 2026-10-19（基线 d53cb55；包版本仍为 9.33.0）

### 中文排版与单页判断

- **断行建议覆盖无标点长主张**：`_BREAK_RULES` 增补处置式「把/将」（单字只收两侧 ≥6 字断口，把握/将来 不被劈开）、结果/目的连词（带动/推动/导致/促使/进而/从而/使得/有助于/用于/旨在）与事件状语「后」；「全年经常性收入」不再被「年」劈开。行长上限固定为 `max_line`（此前 cap=`len//2+4`，41–48 字主张被建议 21–26 字单行）；超过 2×max_line 的主张不再给断点，排版 scale 增补 `lead_rewrite`「先改写成一句更短的可复述结论」并进骨架。
- **口径/期间声明句不再当主张**：`_SCOPE_HEADS` 增补「数据周期/统计周期/数据区间/统计范围/时间范围」——「数据周期为 2026 年 4 至 9 月」此前凭「短句＋数字」赢下结论位（实测）。
- **主数字＝当前值**：主张点名两个指标、各带多年取值时，先在每个指标内部折叠到当前值（同指标同单位才折叠，护栏/意图量同池出局不变），再按主张主语位取指标——双指标系列页的主语不再落在序列开头的基期值（实测「去年订单量增长与履约成本同步上升」页曾把 2023 年的 1,840 万当主语）。
- **多指标并列面板是证据页**：无单一形状、不同数字 ≥3、主张不带数字的页面判 prove（焦点给对齐与同屏参照），不再判 persuade；主张自带数字的标本页（「相加为100不是共同分母」）数字是被讨论的对象，仍是观点页。
- **两端张力构图收敛**：`asymmetric_tension` 的数字项随 comparison 走——没有比较内容的页面不因「有 2 个数字」漂进张力构图，与该算子「等权时不制造倾向」的落选理由一致。

### 跨页叙事与整稿节奏

- **密度方向语义**：抬升记 `build`（「证据体量增大，阅读负荷上升：密度抬升处必须有新的信息增量」），回落才记 `breathe`；此前两方向共用一个词，负荷增加被说成「让出阅读时间」。
- **相邻页信息增量检查**进 `coherence.notes`：后页非年份取值完全复现前页（≥2 个量、无一新增）时提示作者确认新观点/新口径/新拆解，都不是就压缩为引用或合并页面；收束页回收量与比较页引用两端豁免。只提示复核，不自动改页。
- **正文请求句提醒**：主张未点名而正文含请求/决定句时进 `open_questions`（「请委员会批准…」曾被数字焦点挤成一行正文，决定被推迟）。
- **眉标断词修复**：边界字表移除「用/有」（嵌在名词词内的频率高于虚词用法）；相邻段为单字时双向拒绝候选（切口落在两字词内部）；「以…」介词框架与被边界字劈开的半截谓语（压/改/转/拆/提/分/需/职 等）收进首尾字表；窗口上限 6→7 字（完整主语短语「去年订单量增长」好过整页缺省）。50 个真实风格中文标题实测：断词碎片 0（修复前含「率不足」「保留现」「单均成本压」「总部职」「付费」「收入改」「覆盖半径需」等 7 例），12 例安全缺省。

### 结构预览（ghost）证据诚实性

- **max_lines 截断不再静默**：预览按声明丢弃的行数在文本框右下角标注「还有 N 行未显示（max_lines）」，并进 `text_truncations()` 台账（"页/元素" → 行数）；交付层写进 ghost.meta.json 并打 stderr 警示（点明目标 PowerPoint 不截断）。此前被截掉的行在页面与 meta 里都无痕迹，读图会把「预览没画」当成「排版装得下」——实测 guard 估算与 ghost 实测是两套测量，全大写宽字母混排处存在「guard PASS 但预览实测超行」的生产可达域（宽字母估算 0.55em vs 真实 ≈0.95em）。
- **预览排版口径与产物对齐**：`_draw_text` 无条件插入混排脚本间隙（compiler.py:197 对所有 run 插入、guard 按间隙后文本量宽，此前 char_spacing=0 时预览不插，同一行文本三个口径）；space_before/space_after 计入段间隙（compiler 写真实段落属性，此前被预览忽略）；逐段折行，段内禁则照旧、截断按段记账。
- **完全出画布的元素记账**：bbox 与画布无交集的元素进 `out_of_canvas()` 台账并转 meta/stderr 提示；部分出血不算（常为有意构图）。此前预览静默裁掉，「观众不可见」与「不存在」无从区分。
- **联络表自我声明与混尺寸对齐**：标签带（表格 chrome，不碰页面像素）标注「结构预览 · 方向证据 · 非目标软件渲染」；独立调用给出不同尺寸页图时按格子缩放对齐，不再把小图露底/大图压格画进证据。
- **Pillow 10.0 位图回落下 ghost 标注的锚点定位**：依赖下限档（Pillow==10.0）的 `load_default()` 返回位图字面，`draw.text` 的 anchor 被静默忽略——截断标记（rs）、联络表边界声明（ra）与 PREVIEW_ABSTRACT 占位声明（mb/mt）会画到锚点右下方之外（CI minimum 档实测：标记 corner 墨迹 2px、边界带 0px；latest 档 Pillow≥10.1 的默认字面是 FreeType 故不复现）。新增 `_draw_anchored`：FreeType 直接用 anchor，位图回落按 bbox 手工偏移；只影响 ghost 自己的标注文字，待评内容的绘制路径与 Pillow 约束不变（requirements 下限仍为 10.0）。
- ghost.meta.json 新增可选键 `text_truncations`、`out_of_canvas`（无则不写，既有键与契约不变）；页缓存键含 engine 指纹（preview scope 含 ghost.py），本轮改动自动失效全部页缓存并重画——属设计内行为。

### 评估与盲评链路（bench）

- **盲评匿名化补漏**：打包抹去 pptx 文件属性里的作者/时间身份（docProps/core.xml 的 creator/lastModifiedBy/lastPrinted/revision/created/modified），目录待评版本剔除 vao/bench 流程工件（manifest/meta/key/页缓存/.git）——此前带作者批注的 build.py、含绝对路径的 manifest 会原样进入「盲」评目录；画面内容、备注或文件名里的身份无法自动清除，由 pack 内 README 提醒送评人自检（不假装净化彻底）。
- **key v2 溯源**：记录映射、打包时间（UTC）、打乱种子（未给则生成并记录——顺序可复现可审计）与各版本前后 sha256（可查材料调包）；汇总端兼容旧版平铺 key。
- **评分表成器**：csv.writer 正确转义（此前逗号会串列）；表头增 `review_time` 列（旧表仍可读）；新增 README.txt 定义量表 1–7 与五维度中文含义、评审独立纪律。
- **统计诚实性**：ICC(2,1) 实现经 Shrout & Fleiss (1979) 文献值对拍（0.290/0.715，实现未变）；汇总新增按版本重抽样的自助法 95% 区间（固定种子可复现）与版本数/评审数披露——3 个版本的点估计在模拟中可于 0.25–1.00 间波动，只报点估计就是伪精确。完全一致矩阵（零方差）按「完全一致」处理并注明，不再误判 NO_CONSENSUS；共识标签 `CONSENSUS_WEAK_OR_OK` 更名 `CONSENSUS_SUPPORTED`，阈值判定写为显式 `meets_threshold` 字段（四舍五入显示值与原始值不再混淆）；0.5 共识线在报告里标明为启发式阈值、非统计检验。
- **数据完整性**：部分填写行记数不统计（此前静默丢弃）；缺失版本按评审者列明细；评审不足 3 位仍报均值与缺口（此前整个丢弃已收数据）；量表外分数拒绝（此前 9999 分照单全收）；完全相同的评审向量标记 `suspect_identical_reviewers`（保留数据交组织者复核，不静默平均、不剔除）；评审者名先归一化再判重。
- **样本身份**：bench 报告新增 `cases_identity`（案例文件路径 + sha256 前 12 位），开发集/冻结集/未来独立集在报告层面可追认；冻结评测 runner 原有冻结哈希校验不变。
- 已知边界（记录不改）：匿名化无法清除作者写进画面的身份；自助法区间在版本极少时偏宽，这正是要暴露的不确定性；盲评通道至今未执行过（无真实评审数据），其输出不构成设计质量证据。

### 回归与验证

- selftest 新增 `cjk_rhythm_regression`（17 条）、`ghost_observations`（10 条）与盲评链路审计钉（9 条：文献值对拍/匿名净化/溯源/流程工件剔除/量表拒绝/零方差/缺口报告/重复向量标记/区间与读法边界）：**720/720**；bench 57/57；四组冻结断言 81/31/14/8 不变（冻结期望未动）。
- **selftest 字面环境无关化**：ghost 截断钉改为「拉丁文本钉机制（真字体/回退字体同一套代码）＋中文按字面环境分支断言（有真 CJK 字面验度量折行，没有则验回落记账）」——修复 GitHub ubuntu runner（无 CJK 字体）上 3 条误报失败（716/719）；沙箱双环境（有/无 Noto CJK）实测均 720/720。截断行数期望与实现同式计算（`_wrap_lines` 度量−max_lines），不再硬编码依赖特定字体度量。
- 端到端（5 页中文经营稿，作者按骨架落元素）：plan 中位 97ms（基线 99ms）、release+strict check 中位 60ms（基线 61ms，同机对照；ghost 轮改动后复测仍 60ms，全页缓存失效重画 5 页）——判断与预览增量成本在噪声内；release PASS，ghost 结构预览只证明结构方向。目标 PowerPoint 打开/编辑/另存与专业视觉终验仍未验证（SKILL §6）。

## 未发布 — 2026-10-16（基线 0422dc6；包版本仍为 9.33.0）

### 安全与交付完整性

- 拒绝 text 为 null/bool、非有限或越界 angle/opacity；编译写入点归一角度、夹紧 alpha、排序渐变 stops，避免非法 OOXML。
- brief/spec/manifest 拒绝展开超过 250,000 节点的文档，阻断 YAML 别名指数放大。
- 编译失败保留旧完整 PPTX，不发布半成品或为旧产物签署新成功凭证；release 先撤销旧 PASS。已知路径/链接别名预检、单文件原子发布与同轮资产字节快照继续保留。
- Guard/compiler 拒绝坏图表行、空标签与冲突载荷；旧 `data + categories` 输入仍兼容。坏缓存回落重建；盲评拒绝非法/漏评输入，导出不覆盖旧工作。

### 图像与设计兼容

- contain/cover 使用保持盒子比例的画布，修复小图拉伸失真；ghost contain 支持等比放大。
- QC/compiler/ghost 统一 EXIF 显示方向，旋转图不再透传未转置字节。
- 预览相对底图改为**按编译侧同序**解析（`[输出目录, 稿件目录]`，与 `compiler._resolve_src` / `primitives._media_stamp` 一致，vao 显式传入 `_image_roots`）：同名相对路径在两处各有一张图时，预览画的必须与产物贴的是同一张（审计实测两处根序分叉）。独立调用 `ghost_deck`（不带 `_image_roots`）保持 `_base_path` 优先的旧口径；pie 保持实心，仅 donut 族挖孔。
- 作者素材声明优先；对象不默认继承背景材质/光影。`asset_reason` / `asset_composition` 不触发配图额度；提示词缓存 v2→v3 重建，不自动删除旧图。

### 回归与 CI

- 五个案例 JSON 移至 `scripts/json/`；测试默认路径、CI 与文档同步，案例字节及冻结哈希不变。显式 `--cases scripts/文件名.json` 调用须改用新路径。

- 保留主集、r2、r3、r4 四组冻结案例（55 案例、134 断言），不改期望；CI 显式检查必需集存在，仍执行额外同前缀集，防止删除后静默漏测。
- CI 保留 Linux/Windows × Python 3.10/3.12/3.13 与 Linux 3.10 依赖下限组合；显式启用 UTF-8。
- 修正 selftest 对资产快照键和读图路径的比较，按 resolve 后身份核对；符号链接临时目录已复现旧测试误报。
- Linux 本地审计验证：selftest 637/637、bench 57/57；四组冻结断言分别 81/81、31/31、14/14、8/8。两页含图 strict 发布 PASS，干净样例 PPTX 与审计修复前字节一致；坏图等负例 BLOCKED exit 2。
- 远端历史 CI #64（e734d6a）为失败，Windows Regression suite 失败；公开日志下载要求管理员权限，根因未确认——**第二轮已定位并修复，见「Windows/CI 可移植性」**。本次改动尚未推送或完成远端矩阵验收，不宣称远端已变绿。

### 审计修复（同批，2026-10-16）

- **产物权限**：原子发布统一走 `primitives.atomic_replace`——`mkstemp` 的 0600 不再随 `os.replace` 变成产物权限（此前 plan/manifest/QC/缓存/预览 PNG/交付 PPTX 一律 0600，共享目录与 CI 收集 Permission denied；覆盖既有 0644 还会静默收窄）。目标已存在 → 保持原权限；不存在 → umask 默认，与 `open(path,"w")` 同纪律。
- **`--deadline 0`**：只有 `None` 才是「不限时」。此前 `not deadline` 把显式 0 秒预算静默升格为不限时，release 照常渲染预览并 PASS，而同语义的 `-5` 正确 BLOCK；现在 0 如实按「没有预算」处理（缺预览证据即 BLOCK）。
- **unit × show_values 死锁**：release 出处硬门要求数值图表写 unit，编译器却把「unit 在数值标签关闭时不可见」判为编译失败——两个门互相打架，唯一出口是强制打开数值标签。编译器不再拦截（只负责渲染）；guard 出非阻断告警 `chart_unit_invisible`，进发布清单 notes（标签按领域标注：可读域 / 单位可见性 / 非阻断）。
- **可修诊断**：坐标 bool（`x: True` 曾静默当 1px）与 `_positive_num`/`_finite`/`_alpha_ok` 同口径拒绝；canvas 超出 PowerPoint 可表达的 1–56 英寸（96–5376px，`SLIDE_MIN_PX`/`SLIDE_MAX_PX` 单源）给「整稿等比缩放」的可修诊断，不再透出 python-pptx 的裸 range 错误。
- 本轮复跑（审计修复后，Linux）：selftest 654/654（新增 17 条回归断言）、bench 57/57、四组冻结断言 81/31/14/8 不变；含图样例 release PASS 且 PPTX 字节与修复前一致（sha256 9c7bf5d0…）；SIGINT 中断不产出半成品、不留临时文件。远端矩阵仍未推送验证。

### 审计修复（第二轮，2026-10-16）

- **单张解码预算**：新增 `assets.QC_MAX_PIXELS`（1 亿像素，随 `qc_profile` 进 QC 档案）。`fast` 档只缩小统计工作域，原图仍要完整解码一次；实测本机 QC 峰值约 23–26MB/百万像素（4MP→142MB、9MP→243MB、16MP→417MB），一张 12000×12000（144MP）的图在 2GB 容器里把整轮 check 打到 OOM 被 SIGKILL——作者拿到的是「进程没了」。现在超过预算在**解码之前**（读 IHDR 后立即判）拦成可修诊断：「先降采样到预算内再登记」。线画在 100MP（8K 帧 33MP / 5000 万像素相机 50MP / 中画幅 100MP 都过）；Pillow 自身炸弹线为 178.9MP，其下的 89.5–178.9M 只警告不拦。该值是**策略线而非机器推导值**：内存受限的 runner 需自行调低（单源常量，QC 档案可见）。
- **资产失败原因直达修复包**：图读不出来（损坏/截断/超预算）时链路只报「无接受该图片的 QC 结果」，真正判词埋在 `results[].qc.issue`；现在把原始原因带进 `workflow_issues`（「图片不可用（…）」），作者不必再开第二个文件找根因。
- **字距越界**：`char_spacing` 以 pt 声明并写入 `a:rPr/@spc`，而 `@spc` 是 ST_TextPoint（±4000pt，1/100pt 计）。实测 `char_spacing: 1000000` 一路 PASS 并写出 `spc="100000000"`——非法 OOXML，PowerPoint 打开会进修复流程。guard 前置拒绝（可修诊断），`set_run_font` 按同一常量 `CHAR_SPACING_MAX_PT` 夹紧兜底。
- **目标线不再静默消失**：`target` / `target_label` 只由 `ranked_bar` 渲染，而编译器把转换异常吞掉——`target: "abc"` 的稿件 release 仍 PASS，产物里一根参考线都没有。现在非有限 `target` 由 guard 拒绝、编译器直接调用时也发声；其他 kind 上写这两个字段会得到 `chart_field_unconsumed` 告警（写了不生效必须留痕）。契约补记该字段的适用 kind。
- **提示词缓存键覆盖全部输入**：身份指纹刻意不含 `safe_area` / `text_color` / `ratio`（校准压字区不该让已出图改名），但 `build_asset_prompt` 读它们。按身份查缓存时，作者把压字区从左侧改到右侧再跑 plan，拿回旧提示词，而清单里的 `safe_area` 已是新值——清单与出图指令互相矛盾。`prompt_cache_key` 把提示词输入混进键（资产 id 与去重语义不变）。
- 本轮复跑（第二轮修复后，Linux）：selftest 676/676（本轮新增 22 条）、bench 57/57、四组冻结断言 81/31/14/8 不变；同一含图样例 PPTX 字节与基线 `aa47e2f` 一致（sha256 9c7bf5d0…），墙钟中位 0.42s vs 0.41s（+1.4%，噪声内）；元素保真度探针 22/22、EXIF 方向 1–8 全对、不可信资产 6 类畸形清单全部 rc=2 无 traceback。远端矩阵仍未推送验证。

### Windows / CI 可移植性（第二轮，2026-10-16）

- **CI #64 根因确认**（原记录「根因未确认」）：`windows-latest` 的回归套件崩在 `test_deep_release`——它用 `os.path.relpath(blind_src, Path.cwd())` 构造相对路径，而 GitHub 的 Windows runner 工作区在 `D:`、临时目录在 `C:`，两棵根之间不存在相对路径：`ValueError: path is on mount 'C:', start on mount 'D:'`。测试死在 setup 而不是断言上。改为 `_portable_relpath()`：能相对就相对，做不到退回绝对路径（该检查要验的是「blind pack 不篡改传入的来源标识」，绝对路径同样成立）。本机用 `ntpath` 复现了该 ValueError，并让 `test_deep_release` 走兜底分支跑满 41/41；把助手换回原写法可复现同一崩溃（对照实验）。
- **Windows 没有 POSIX 权限位**：`test_atomic_publish` 原先断言 `st_mode == 0o644 / 0o664 / 0o600`；Windows 的 `stat` 只反映只读标志（`chmod` 之后一律报 `0o666`），这三条会在 Windows 腿误报。判据改成跨平台可证的形式——**覆盖前后权限不变**，数值相等只在 `os.name == "posix"` 时追加（检查数量不变，POSIX 覆盖不减）。
- **测试侧缺 encoding**：`selftest.py` 6 处 `read_text()` 读的是管线写出的 UTF-8 中文 JSON；未指定编码时，非 UTF-8 模式的 Windows（CI 之外的本机）会解码失败。补齐 `encoding="utf-8"`。生产代码经 AST 扫描确认没有同类问题（初筛 16 处 `open()` 全是 `Image.open`/zip 成员，非文本读取）。
- 本轮复跑（Windows 可移植性修复后，Linux）：selftest **680/680**、bench 57/57、四组冻结断言 81/31/14/8 不变、CI 的 spec 冒烟红线（禁 import pptx/lxml/compiler）本机逐字复刻通过。Windows 实机仍待 CI 矩阵验证，本地只做了条件模拟与平台文档级推论。


### 审计精简（本轮 Agent Mode）

- `vao.py`：骨架写盘前对目标文件的重复读取合并为一次（先读一次再比较），消除同一路径的二次 I/O。
- `primitives.py`：删除从未被任何模块调用的 `latin_word_match`（grep 全仓库无消费者），减法测试无质量损失。
- 本轮未改动判断基准、字段契约与测试期望；selftest 680/680、bench 57/57、四组冻结断言 81/31/14/8 全过。

### Markdown 深度优化（Agent Mode 续，2026-10-16）

- **SKILL.md**：合并「五问」与判断表为单一权威位置（表格），消除重复列举与冗余流程；「素材导演」五节各精简 40–50% 而保留全部独特判断能力；§2/§6 去除低价值铺垫与重复解释。217→143 行（-34%），~4378→~2972 tokens（-32%）。
- **references/contract.md**：删除与 SKILL.md 重复的判断原则重述、冗余安全说明与过度展开的实现细节；保留全部执行契约字段与失败码。178→103 行（-42%），~3769→~2047 tokens（-46%）。
- **references/assets.md**：删除与 SKILL.md §3「素材导演」重叠的设计原则；保留资产执行字段、QC 判据与来源链硬边界。84→55 行（-35%），~1806→~918 tokens（-49%）。
- **总计**：三份核心 Markdown 从 ~9953 tokens 降至 ~5937 tokens（-40%），AI 读取 Context 的信息密度提升，同一判断能力以更少篇幅传递。
- 本轮未改动任何脚本逻辑、判断基准或测试期望；selftest 684/684、bench 57/57、四组冻结断言 81/31/14/8 全过；plan + check 生产链路正常。

### 审计修复（Agent Mode 续，2026-10-16）

- **`test_win_portability` 的错误前提**（Windows 腿）：「同盘符仍给出相对路径」拿 `tmp` 与 `Path.cwd()` 配对——windows-latest 的 tmp 在 `C:`、工作区在 `D:`，这对本身就是跨盘，恰好落进兜底分支，断言与前提相反（本机以 PureWindowsPath + ntpath 语义复现：该断言在目标平台上必失败）。同盘对改为**两头同根**构造（`work` vs `tmp`），并补一条 ntpath 同盘对的 Windows 语义断言；跨盘对仍用 ntpath 实错 + mock 复现。**生产逻辑未动**：`_portable_relpath` 的「能相对就相对」与 `blind_pack` 的「key 原样记录作者路径表达」保持原样。
- **数字与单位被「个」截断**：`_NUM` 的单位组把「个」当独立单位，「2.1 个点 / 5 个百分点 / 2 个季度」被解析成「2.1 个」＋游离汉字——主语量、判断理由与骨架里出现残缺量（审计实测：「提升 2.1 个点」的 lead 显示「2.1 个」，claim 理由写「数字「2.1 个」」）。「个」改为分类词＋计量名词同进同出（个百分点/百分点/个点/个季度/个星期/个小时/个人…），无名词跟随时仍是计数（「5 个」）。
- **目标/计划量冒充「当前状态」**：`_attributed_primary` 的同分末值与主张锚定不识别意图模态——「…2024 年 22%。计划：…目标把复捐率拉回 28%」的下降序列把 2025 目标量 28% 选成焦点，理由却写「是序列的当前值：先立住现状」（审计实测）。新增 `_INTENTION_MARK` 子句级情态判据，与条件从句同池出局：被申请的量（请批准…）不受限；整句都是意图时退回全体，不判空；「目标客户/目标市场/目标 PowerPoint/计划外支出」等复合名词不算意图标记。`number_roles` 的「当前状态（末值）」分支同步只在**现状值**里取末值。
- **计量短语在预览里被腰斩**：`ghost._UNIT_INNER` 原为手抄子集（漏「万美/方米/瓦时」及「个百分点/个点/个季度」的内部对），且 `_cjk_break_fix` 的单位回退只退一步——三字短语（「万｜美元」「个百｜分点」）单次回退后仍停在短语内部（fuzz 实测 width=264 断成「3,800 万｜美元」）。改为从 `UNIT_WORDS` 派生全部相邻对（删掉手抄子集），回退循环走到短语之外再由数字规则整体推下；`UNIT_WORDS` 补「个百分点/百分点/个点/个季度/个星期」。
- `intelligence._metric_of_clause` 的局部 `unit_head` 字符表更名 `unit_chars`，不再遮蔽从 primitives 导入的 `unit_head` 接口（名称冲突，无行为变化）。
- 回归新增 4 条断言（单位绑定 / 目标量不冒充现状 / 目标句回退与「目标客户」除外 / ntpath 同盘对）；删除 1 处无消费的测试内 import。
- 复跑（Linux）：selftest **684/684**（680＋新增 4）、bench 57/57、四组冻结断言 81/31/14/8 全部不变（冻结期望未动）；12 页中文代表性稿 release+strict PASS，PPTX 内数字-单位为 U+00A0 不断行空格（含「2.1 个百分点」）、原生图表可编辑、无越界、另存重开正常；spec 冒烟红线（禁 pptx/lxml/compiler）通过。性能对照（中位）：check 12 页 release+strict 68ms（持平）、plan 95→102ms（噪声带）、selftest 15.9→15.6s。Windows 实机仍待 CI 矩阵验证，本地只做了 ntpath/PureWindowsPath 条件模拟。

## 9.33.0 — 2026-10-15

- `resolve_chart_highlight` 统一序列/类别强调，类别强调写入原生 `dPt`；删除的 `series_highlight_index` 外部调用须迁移到返回 `(series_index, point_index)` 的新接口。
- matrix 坐标有限数硬门；修复临时包清理、空文本 split_runs、环心 KPI 预览、absent 归因及缓存写盘诊断。

## 9.32.0 — 2026-10-15

- 修正份额关系、逐数字主语、千分位与时间序列判断；同单位多数字不自动成为趋势。
- 区分作者主张、证据陈述与未决；不把标签数字升格结论、不补未知关系。冻结案例保持只读。

## 历史迁移索引

| 版本 | 关键差异 / 迁移 |
|---|---|
| 9.31–9.29 | 独立泛化与视觉证据分层；关系/主张纠偏；Windows 管道 UTF-8。移除旧验收工件，未提交产物不能从 Git 恢复。 |
| 9.28–9.25 | CHART_SPEC 单源；标签与容量契约、编译缓存跨速度档；删除未消费字段、候选与盲评通道。 |
| 9.24–9.22 | 页级修复定位；timeline 单位须写入实际绘制字段；图片由作者声明，无自动图位额度。 |
| 9.21–9.18 | 移除外部渲染链，生产入口收敛；判断/骨架瘦身；设计与结构证据分层。 |
| 9.17–9.15.1 | `plan --json` 返回摘要，完整判断读 plan_path；覆盖保护、发布凭证、多序列图例、截断门与 CJK SC 字面。 |
| 9.15–9.3 | 中文禁则、资产 QC、图像编码与字体性能、缓存/身份复用；历史图位配额不代表现行行为。 |
| 9.2–9.0 | 主张/角色与整稿回看；删除命名风格预设，QA 收窄为硬错误。 |
| 8.x–7.3.2 | 页级声明、修复包与 CI；合并判断/资产/验证入口；缓存及资产哈希链基线。 |

## 验证边界

- 代码测试、PPTX 结构、ghost 预览和真实 PowerPoint 显示/编辑验收相互独立；本环境未完成真实 PowerPoint 与专业视觉终验。
- 远端 CI 仅以实际作业结果为准；历史测试量、局部字节一致不代表所有稿件兼容或性能提速。
- Python brief/build 是可信作者代码而非沙箱；不保证同输出并发或敌对 TOCTOU。建议独立运行目录。
