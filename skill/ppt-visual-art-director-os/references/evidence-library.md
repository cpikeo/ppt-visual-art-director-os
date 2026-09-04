# Evidence Library

## 使用协议

参考证据不是风格命令，也不是品牌复制。每张 Evidence Card 必须完成四步：**观察行为 → 提炼原则 → 写成执行规则 → 明确反例与边界**。引用时记录来源、访问日期、证据强度和适用场景。若只有审美印象而没有可观察行为，则不能进入设计决策。

## Evidence Cards

| ID | 来源与可观察行为 | 可执行原则 | 适用边界 |
|---|---|---|---|
| EVD-APPLE-001 | [Apple Events][1] 的发布语境通常以单一产品/能力和清晰章节节奏组织注意力 | 发布页使用单一 Hero、尺度张力、少量文字；每页只推进一个能力或结论 | 不把产品舞台用于数据附录、研究页或多结论页面 |
| EVD-PENTA-001 | [Pentagram Brand Identity][2] 展示身份系统、出版物、海报、数字体验等跨媒介一致性 | 将品牌识别转译为字体、比例、线条、图形语法与应用行为，而非只取 logo 和色板 | 品牌一致性不等于所有页面都使用相同构图；内容任务仍优先 |
| EVD-IDEO-001 | [IDEO][3] 明确 Inspiration → Ideation → Implementation，并强调真实语境、原型、迭代与协作 | 在视觉方向冻结前先理解受众与场景；至少完成一次渲染证据 → 批评 → 修正闭环 | 不能把“以人为本”简化为每页放人物照片 |
| EVD-MCK-001 | [McKinsey storytelling][4] 将 storytelling 视为领导沟通能力，并强调通过叙事建立理解与行动 | 先写结论与决定，再安排证据；标题表达洞察，页面顺序服务行动 | 结论先行不代表省略来源、限定条件或不确定性 |
| EVD-KINFOLK-001 | [Kinfolk][5] 作为生活方式出版物，适合观察编辑化留白、摄影语境和材质节奏 | 用留白、统一摄影语言、稳定版心与章节节奏建立气质；把图片当叙事而非填空 | 编辑感不等于暖色 + 衬线字体 + 随机生活方式照片 |

## 证据记录模板

```yaml
reference_id: EVD-XXX-001
source: "https://..."
accessed: "YYYY-MM-DD"
subject: "参考对象"
observation: "只写可看到或可验证的行为"
principle: "从行为提炼的设计原则"
executable_rule: "对本 deck 可执行的动作或约束"
anti_pattern: "不应推导出的错误模仿"
use_when: ["适用场景"]
confidence: "high | medium | low"
```

## 证据治理

Evidence Card 只影响 Direction 和 Critic 的判断，不得覆盖事实、可读性、可编辑性和项目品牌规则。多个参考发生冲突时，优先受众与内容任务，再优先证据强度，最后才是审美偏好。对外部案例的描述应保持克制，不把未经验证的“行业共识”写成事实。

## References

[1]: https://www.apple.com/apple-events/ "Apple Events"
[2]: https://www.pentagram.com/brand-identity "Pentagram Brand Identity"
[3]: https://www.ideo.com/ "IDEO Human-centered design"
[4]: https://www.mckinsey.com/locations/mckinsey-client-capabilities-network/our-work/strategic-and-change-communications/the-communications-exchange/invest-in-the-art-of-storytelling-to-raise-your-return-on-inspiration "McKinsey: Invest in the art of storytelling"
[5]: https://www.kinfolk.com/ "Kinfolk"
