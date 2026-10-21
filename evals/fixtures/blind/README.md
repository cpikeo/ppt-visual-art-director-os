# blind/ · 盲评导出链的**测试夹具**（不是评审证据）

这三份评分表是**合成的**，用途只有一个：验证 `tools/blind_to_comparison.py` 的翻译规则
（均值 → rubric、维度差 → strengths/weaknesses、评审不足三位 → confidence=low）。

它们**不代表任何真实评审意见**，也不构成「with_skill 更好」的证据。
真实盲评必须由独立评审者填 `score_sheet.csv`（`bench.py blind pack` 生成），
原话抄进 comparison.json 的 `reviewer_notes`。
