# 变更记录

## 5.2.0 · 用实战返工换速度（判断层一字未改）

一次 11 页真实交付（宋氏美学 × 现代东方年度总结）暴露出 15 个问题，其中 4 个是**静默失效**：
不报错、结果错、且每次都逼人回到源码里找口径。本次只修这些根因。

**没有动的**：`SKILL.md` / `design-craft.md` / `design-intelligence.md` 的**一个字都没改**
——判断层是资产，不是负债。不增命令、不增模块、不增规则、不增检查器。

省下来的返工（按实测）：

| 根因 | 本次代价 | 修法 |
|---|---|---|
| 介质判定看错了层 | 3 张废图 + 多轮 QC 分析 | 介质回归**资产级声明** |
| 方向族名送不到 | 全程手写材质/纹理覆盖 | 13 个色彩族名可作 `design_direction` |
| deck 级世界语言污染单张介质 | 1 次全流程重跑 | `visual_world` 与介质判定解耦 |
| 「主体贴边」判了氛围图 | 多出 3 张图、意象被迫改 | 按 `asset_function` 分级 |
| 预览画不出多序列 | 1 次「以为产物是空图」的误判 | ghost 认 `series` + `categories` |
| 隐式旋钮没进契约 | ~5 次读源码 | brief 模板补齐 |
| 指纹报错不说位置 / 白边废图 | 各 1 轮 | 报错给权威位置；边框进通用反向 |

### 介质判定回归「资产级」（最贵的一条）

`ink_gate_active` 原本认一个方向族名白名单（`song_elegance`）。它两头都错：

- 方向名送不进来时（见下条），它**永不命中**——库里唯一的水墨闸门是一段死代码；
- 方向名送进来之后，`card["family"]` 带着族名，于是**全 deck 的摄影页一起被判定为水墨**，
  提示词里出现水墨工艺纪律与 `photography medium` 并存的自相矛盾。

现在判据只有资产的介质声明：`medium`（最明确）、subject、逐页显式写下的材质。
方向默认值不算——它说的是「整副 deck 用什么质感说话」（一份宋韵里每张照片也可能拍在
纸台上），不替某一张图宣告它是画。`INK_FAMILIES` 常量随之删除。

### 方向族名可送达

`design_direction` 只认 4 个结构预设，`design_intelligence_rules.COLOR_DIRECTIONS` 的
13 个族名一律静默回落成 `quiet_minimal`。现在族名被接受，并带来它自己的
材质 / 动势 / 纹理语言与种子色板（结构骨架仍取预设，品牌色仍优先，`texture` 以键名
传下去由 `asset_prompt` 展开）。

配套：`vao.py` 的 `card["family"]` 从**页面家族名**（`cover`/`data_story`）改为**方向族名**
——`FAMILY_TEXTURE` / `FAMILY_MOTION` 的键一直是族名，传页面家族名只会静默落进
`("luxury",)` 兜底，于是每张宋韵资产都吃「fine leather grain」。

### 其余修复

- **deck 级世界语言与单张介质解耦**：`visual_world` 从 `style` 段移到 `world` 段——
  照旧进提示词当氛围语言，但不再参与闸门扫描；方向枚举也不再泄漏进提示词。
- **QC 按职能分级**：`asset_function ∈ {emotion, context, frame, separate}` 时，
  「主体贴边被裁」降为建议。该判据是为**具象主体**设的，而氛围/语境资产的画面边界
  本就该由材质与光填满。实测三层手工纸特写与静物的显著性占比同在 0.00–0.07 量级
  ——像素层面区分不了「材质延伸」与「被裁断的主体」，判据只能取自声明的职能。
- **ghost 支持多序列图表**：`_rows` 同时认 `data` 与 `categories`+`series`。
  实测 `comparison_bar` + 双序列的产物里 `<c:ser>=2`、数据点齐全，而预览只画一个叉
  ——预览「冤枉对的」与「背书错的」同样是证据失效。横向条同时补上类目轴标签。
- **brief 契约补齐**：补 `material` / `lighting` / `texture` / `asset_color` /
  `safe_area` / `negative` / `asset_type`（它们一直是「显式传入永远赢」的旋钮，却没写进模板）；
  接上 `composition_grammar` / `background_scene` / `avoid`；
  **删除 6 个零消费字段**（`tone_hint` / `type_voice` / `color_behavior` / `media_policy` /
  `energy_curve` / `evidence_posture`）——留着只会让人写了以为生效。
- **报错可执行**：`plan_sha256` 不匹配时直接报出权威位置（`asset_manifest.json` →
  `workflow.plan_sha256`），不再只说「不匹配」；缺 `asset_subject` 时 QC 提示
  「主体描述取自页面标题（标题是观点，不是画面）」。
- **通用反向补边框类**：`white border` / `black bars` / `letterbox` / `picture frame` /
  `poster mockup`。模型把「四周留白」误读成「加一圈画框」是高失效模式，画幅会整段作废。

### 迁移

无需迁移：没有命令、字段或文件的新增与删除（brief 里被删的 6 个字段本来就不生效，
写与不写等价）。`plan` / `assets` 的产物 schema 未变。

回归：**139/139 PASS**。

## 5.1.2 · 设计判断层补位（Anti-Design / 减法链 / 审美标尺）

本次只动判断与文档，不新增命令、依赖、检查器或流程。SKILL.md 净字节 **−16 B**：
加进三组判断的同时，把重复的工程凭证细节让位给 `references/production-contract.md`
——加的是判断，减的是篇幅。

### 判断层

- **Anti-Design（主动避免）**：SKILL.md 与 `design-craft.md` 首次给出显式反模式清单——
  模板感 / UI Dashboard 感 / 卡片墙 / 组件堆叠 / 过度圆角 / 过多阴影 / 过多渐变 /
  无意义图标与线条 / 过度 3D / 过度装饰 / 过度留白 / 为高级而高级 / 为变化而变化 /
  AI 机械布局 / 每页同一结构。并点明最该避免的是**「所有东西都设计得很明显」**：
  世界级设计允许视觉保持安静。
- **减法链统一**：`删除 > 重组 > 排版 > 强化 > 装饰` 成为跨内容与视觉的唯一修法顺序，
  取代原先分成两截的表述（SKILL.md 管内容层、`design-system.md` 管装饰层）。
- **审美标尺**：Apple Keynote / Pentagram / Swiss Typography / Financial Times / Bloomberg /
  Kinfolk / Monocle / Wallpaper* / IDEO 明确为**校准判断力的参照系**——学它为什么这样决定，
  不学它长什么样；参考案例不得变成下一份 PPT 的版式、色板或组件。
- **最高原则块**补入 `Content determines form / Meaning determines hierarchy /
  Context determines color / Information determines layout / Aesthetic determines selection /
  Narrative determines rhythm`。

### 修复（回归网此前在 Windows 上从未真正跑起来）

两个缺陷都是静默失效型，前者掩盖了后者：

- **selftest 在非 UTF-8 码页的 Windows 上直接崩溃**：`run_vao` 使用完全隔离的 env，
  且 `text=True` 靠 locale 猜编码——子进程按 GBK 输出中文时父进程按 UTF-8 解码，
  reader 线程抛 `UnicodeDecodeError` → `proc.stdout` 变 `None` → 报错落在无关行号
  （`TypeError: 'NoneType' object is not subscriptable`），**基线根本无法建立**。
  现固定两端 UTF-8 并加 `errors="replace"`，同时补回 Windows 进程启动硬依赖
  （`SYSTEMROOT` / `COMSPEC` / `TEMP` / `TMP` / `LOCALAPPDATA` / `APPDATA`）。
- **M-09 用例在沙箱化 Windows 上失效**：宿主会把 `symlink_to()` **静默降级**为普通文件
  （不抛 `OSError`，`is_symlink()` 却是 `False`），用例因此落进「链接创建成功」分支，
  又因 `resolve()` 本就不越界而失败。现检测到降级即强制走 post-resolution 边界分支。

回归：**139/139 PASS**。Linux / macOS 行为不变，仅是健壮性补强。

## 5.1.1 · 修复深度审计发现（本地修改版）

修复 3 项 P1、11 项 P2；不增加生产命令、运行依赖、服务、签名系统或数据库。

- **H-01**：删除共享的图片适配磁盘缓存；保留按输入/产物指纹校验的整份 PPT 编译缓存。
- **H-02**：QC/发布阶段只读 brief 原始字节与计划内需求快照，绝不隐式执行 brief。明确指定的可信 `.py` 仍可用于规划与编排；未知后缀拒绝。
- **H-03**：核验时读取图片为不可变 bytes；编译和方向预览共用该快照。源文件随后变化不会替换本轮交付内容。
- **M-01**：单页预览与总览均保存/校验 SHA-256；缺失或被替换则重建。
- **M-02**：绑定计划的稿件核对完整页 ID 与顺序，无图稿件也不例外。
- **M-03**：数值图表来源口径必须是非空白字符串。
- **M-04**：修正未指定文字明暗时的恒真对比度条件。
- **M-05**：QC 检查短边、计划比例；编排检查裁切后的有效像素是否足够支撑落位。
- **M-06 / M-11**：形状内文字纳入容量检查；禁止换行文字增加水平宽度检查。
- **M-07**：auto_fit 后的有效 spec 成为编译、预览、发布的共同输入；失败状态和修复建议统一归并。
- **M-08**：每次 check 建立 run_id，先使旧发布资格失效；异常也原子写入本轮失败报告。
- **M-09**：生成资产最终路径必须仍在 assets_dir 内；明确登记的 existing 外部素材仍允许。
- **M-10**：透明图片按计划背景合成后 QC；全透明内容拒绝，可见透明素材不一律拒绝。

新增 29 个回归检查，覆盖上述问题和正常缓存、透明 Logo、有意裁切、原生稿件等合法用法。

### 迁移说明

旧 QC 报告不能冒充新检查结果。请重新 plan → assets → asset-qc；已有素材登记为 reuse，
不需要为了迁移强制重生成。QC 报告版本升级为 `vao-asset-qc-v3`，资产清单保留 v2，
新增原始 brief 文件指纹。骨架保留 plan_path 与 plan_sha256。

图像质量底线：短边至少32px；与计划比例相对偏差不超过5%，有意裁切可在 brief 声明
`asset_allow_crop: true`；实际落位不允许明显超过有效像素尺寸（1%浮点容差）。
这些是最低有效性检查，不是艺术质量评分。

本地字节快照和哈希仍不是数字签名，也不是对不可信 Python 执行的沙箱。

## 5.1.0 · Asset-first workflow（本地修改版）

本次针对“先自由生成图片、后补PPT规划，却误称完整执行技能包”的流程缺口修改。
这是基于仓库的本地改进版，未向上游仓库推送，也不代表上游已发布同名版本。

### 流程

- 标准顺序明确为 brief → plan → assets → 按清单出图 → asset-qc → PPT 编排 → release。
- `assets --plan` 改为必需；核对当前 brief 与已保存 plan。
- 图片清单内部调用 asset_prompt 的提示词构建函数；外部图片生成仍由执行者调用。
- 纯原生内容明确记录跳过；已有图像通过来源登记与 QC，无需强制重生成。

### 运行时

- 新增内部 `asset_workflow.py`，不增加第二个生产CLI。
- 计划与骨架、资产清单、QC报告、实际图像以内容 SHA-256 绑定。
- 图片须声明 asset_id 与使用页；无清单/无QC不能直接通过 src 进入编译。
- 统一 QC 与绑定的图片目录及 JPEG/PNG 解析，修复复用标记覆盖主资产记录的问题。
- 修正 QC 重试仍返回成功的漏洞；retry/missing/block 均返回非零。
- 发布结果增加资产流程凭证；修复 BLOCKED 与 release_eligible=true 可能并存的状态。
- 图片比例、文本明暗与风格进入提示词缓存指纹，避免不同需求错误复用。
- 明确重跑资产准备时不能将已有字节冒充本轮新生成图片。

### 文档与验证

- 更新 SKILL、README、生产契约、设计系统、brief模板。
- 新增资产工作流说明、迁移说明及证据边界。
- 增加资产流程集成/回归测试；测试使用本地图片夹具，不调用在线图片服务。
- 修正既有 CI 中的失效规划命令与不存在的模板引用，改走真实 vao.py 入口。

### 兼容性注意

- 无图片稿件的检查命令不变。
- 有图片的旧稿不能再仅凭图片路径发布：须建立计划、清单与有效 QC；已有图登记为 reuse。
- 旧版资产清单/QC 不自动升级，不补造原先未执行的步骤。
- 本地哈希链不是外部图片服务调用证明，也不构成图像授权审核。
