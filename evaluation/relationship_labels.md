# 关系判断与原生图表标签的同口径回归

本夹具只执行与验证 [SKILL.md](../SKILL.md)，不是审美评分或自动排版系统。

## 运行

```bash
pip install -r requirements.txt
python scripts/selftest.py
python evaluation/relationship_labels.py \
  --before /path/to/baseline-9.15.1 --after . --out /fresh/evidence --repeat 5
```

基线必须是上一轮工作区 **9.15.1 快照**，不能把 Git HEAD `8b3d81e` 当成该快照。
输出目录必须全新，repeat 至少 2；最后一个 before-N 在计时完成后用于版本升级缓存试验，
因此保留 `before-0` 作原始视觉/原生对象对比。不要与自测或其他任务并行计时。

## 证据如何读

- `relationship-cases.json`：15 个预先声明期望的有限句式正反样本；4 个关系样本与 11 个
  控制样本。不覆盖自由文本理解；不确定、量化与复杂混合关系仍需作者判断。它们不是
  CASE_006 原稿，也没有用盲评冒充客观审美分数。
- `before/after-judgments.json`：输入与完整逐页判断。同一正文中的关系应该改变角色、
  焦点和空间解释，但不意味着作者必须采用某个预制布局。
- `runs/{before,after}-N/`：同一八页作者 spec，覆盖封面、章节、观点、治理、数据、
  中文混排、图片与收尾；治理页用成对文字表达职责，不补画上下级。**布局是作者固定
  编排，不是不同模型的设计成稿 A/B**。图片继承上轮原创合成光照标靶。
- `chart-audit.json`：检查原生图表 show_values、字号、a:ea 字体声明与数值；缺失标签
  必须到原生 OOXML 查证，不能只看可能“替成品补标签”的预览。
- `measurements.json`、`summary.json`：交替 A/B、新进程、新应用缓存；OS 缓存未清除。
  只计 plan + check 自动化段，人工 spec 装配、模型思考和外部生成不在内。中位数不能
  逐阶段相加；N=5 不足以从小差异推断稳定提速。
- `cache-assertions.json`：编译器变更必须废掉旧 PPTX 与预览，随后暖态复用；原有
  单页变更、同 stat 篡改、Fast 非预览页容量检查见复用的 font_fidelity 夹具。

PowerPoint 实际打开、编辑、字体替代、长类目折行与遮挡、投影可读性仍待目标环境
取证。原生对象和 XML 正确，不等于真实视觉终验通过。
