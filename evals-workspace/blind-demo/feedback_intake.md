# 人评回执 · demo_iter

- 收到的反馈文件：`feedback.json` · 条目 2 条（新增 2 条）
- 其中无意见 1 条
- 状态：complete

| run_id | 用例 | 配置 | 反馈（原话） | 归属层（人填） | 状态 |
|---|---|---|---|---|---|
| `eval-0-two-metric-page-with_skill-run-1` | two-metric-page | with_skill | 末页那个 800 万的数字和正文一样大，看不出是决定；建议主语再大一号 |  | 未处理 |
| `eval-1-narrative-six-with_skill-run-1` | narrative-six | with_skill | — |  | 未处理 |

## 怎么处理这张表

1. `归属层` 只有人能填：判断协议（SKILL）/ 可调策略（policy）/ 契约（schema）/ 文案（文档）/ 视觉（人评）。工具不猜。
2. 具体意见先进下一轮用例：能在 `evals/` 或 `scripts/json/` 里复现的，先加用例再改代码。
3. 空反馈**不写进通过数**：它是「无意见」，不是「已验证」。
4. 处理完把 `状态` 改成 已修 / 转下轮 / 不采用（写明理由）。
