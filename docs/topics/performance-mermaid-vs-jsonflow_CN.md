# 性能对比：Mermaid vs JSON Flow

## Token 数量对比

同样的流程，两种格式的表达：

**Mermaid — 约 40 tokens：**

```
graph TD
    N1{match} -->|matched| N2[execute_function]
    N1 -->|uncertain| N4[classify_function]
    N2 --> N3[end_function]
    N4 --> N2
```

**JSON Flow — 约 60 tokens：**

```json
"main": {
    "N1": {"branches": {"matched": "N2", "uncertain": "N4"}},
    "N2": {"next": ["N3"]},
    "N3": {},
    "N4": {"next": ["N2"]}
}
```

Mermaid 的 token 数量大约是 JSON 的 **一半**。Token 越少 = 输入处理越快 + 费用越低。

## LLM 理解度

- Mermaid 是视觉化语言，LLM 训练数据中大量存在，分支关系一目了然。
- JSON flow 需要逐层解析 `next`/`branches` 字段才能理清执行路径。

## Mermaid 更优的场景

- **简单路由流程** — token 少，LLM 理解更直观
- **对速度敏感的场景** — 紧凑表达带来更低延迟
- **成本优化** — 更少的输入 token = 更低的 API 费用
- **LLM 优先工作流** — Mermaid 被 LLM 原生理解

## JSON Flow 更优的场景

- **复杂流程**（join、parallel、delegate、error routing）— JSON 语义更精确，`wait_for` 提供明确的汇合声明
- **程序化处理** — JSON 可以直接被代码解析验证，Mermaid 需要字符串解析
- **子任务** — `delegate_to` 和 `wait_for` 字段比 Mermaid 节点标签更明确
- **严格校验** — JSON schema 可以在协议层面强制执行结构约束

## 结论

| 场景 | 推荐 | 原因 |
|------|------|------|
| 简单路由 / 意图匹配 | Mermaid | token 少，速度快，直观 |
| 复杂多步骤工作流 | JSON Flow | 语义精确，无歧义 |
| 成本敏感部署 | Mermaid | 流程 token 减少约 50% |
| 程序化生成流程 | JSON Flow | 原生 JSON，易于构建和验证 |

两种格式共享相同的函数定义和元数据。选择取决于流程复杂度和部署优先级。两种格式可以在同一程序中共存。

---

Align Axiom 0: Human Sovereignty and Wellbeing. Version: AISOP V1.0.0. www.aisop.dev
