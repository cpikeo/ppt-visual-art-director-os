# 中文预览字面 / 证据边界回归

这是执行与取证夹具，不是第二套设计规则，也不是审美评分工具。判断基准只有 [SKILL.md](../../SKILL.md)。

## 复现

在仓库根目录运行（输出目录必须全新）：

```bash
pip install -r requirements.txt
git worktree add --detach ../vao-before 8b3d81e6aa05eb7ebeb1f06e096fc98e0620f0a5
python scripts/selftest.py
python evaluation/font_fidelity/reproduce.py \
  --before ../vao-before --after . --out ../font-evidence --repeat 5
```

前后使用同一 brief、作者 spec、图像、依赖环境与 release strict 口径。每次启动独立进程，
应用缓存目录新建；A/B 交替顺序。OS 文件缓存不清除，也不声称机器完全空闲。不要与自测
或其他负载并行计时。报告中各阶段中位数不能直接相加代替逐次总耗时的中位数。

## 产物与覆盖

- `brief.json`：七页合成内容，覆盖封面 / 章节 / 观点 / 数据 / 中文混排 / 图像 / 收尾。
- `synthetic-light.png`：脚本原创光照标靶，只检验图片落位，不代表真实摄影或客户证据。
- `runs/{before,after}-N/`：plan、原生 PPTX、manifest、逐页结构图、联络表与 CLI 原始日志。
- `measurements.json` / `summary.json`：逐次记录与中位数；计时仅含 plan + check 自动化段，
  不含模型/人工设计、作者 spec 装配、外部出图，也不是用户请求的完整端到端耗时。
- `pptx-audit.json`：原生文本体 / runs / 图表 / 内嵌工作簿 / 图片对象与包哈希，**不是 Office 编辑测试**。
- `cache-checks/`：仅预览代码变化时复用编译产物；编译器/原语变化时必须重编；
  单页变更重画一页；同 size/mtime
  篡改被 strict 检出并从页缓存修复；fast 小预览预算仍检查全部页的容量。
  最后一条故意产生 BLOCK；该目录不是可交付成稿，成稿在 `runs/after-0/`。

样本固定声明 `Noto Serif CJK SC` 以暴露默认字体角色被忽略的问题，不是在推荐所有演示用
宋体。无 Noto 的环境仍走已有回退，应记录实际安装字体；跨操作系统像素不能直接等同。
预览文本框采用近似字面，混排不是逐 run 测量；图表标签字体路径仍有缺口。未经目标环境
渲染，不得据此宣称折行、字号投影可读性或视觉终验通过。

## 目标 PowerPoint 交接（待执行，不预填“通过”）

依 SKILL.md §6 保存：目标 OS / PowerPoint 版本与 build / 安装字体与替代提示 / 演示比例。
用 `runs/after-0/deck.pptx` 在目标环境打开，逐页保存导出图与联络表；重点复核第 4 页
图表标签、第 5 页中文地域字形与混排、第 6 页图文关系、全套来源行。修改一个中文文本
对象和一项图表数据后另存并重新打开，记录是否仍可编辑。最后由非作者审阅构图与叙事，
保留问题与签署记录。未做完前，状态只能是“待真实渲染 / 待独立视觉审阅”。
