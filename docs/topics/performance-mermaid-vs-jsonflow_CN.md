# 性能对比：Mermaid vs JSON Flow

## 表示方式示意

以下用两种格式表示同一流程，仅展示表示方式，不是测量基准或独立 AISOP 程序。JSON 示例展示一个图成员。

**Mermaid：**

```
graph TD
    N1{match} -->|matched| N2[execute_function]
    N1 -->|uncertain| N4[classify_function]
    N2 --> N3[end_function]
    N4 --> N2
```

**JSON Flow 图成员：**

```json
"main": {
    "N1": {"branches": {"matched": "N2", "uncertain": "N4"}},
    "N2": {"next": ["N3"]},
    "N3": {},
    "N4": {"next": ["N2"]}
}
```

Token 数取决于 tokenizer、标签、流程结构和序列化/格式化方式。Mermaid 在某些流程中可能更紧凑，但本页没有提供 token、延迟、成本或准确率的测量对比，不承诺普遍节省比例。

## LLM 理解度

- 模型对两种表示的理解取决于模型与任务；训练数据熟悉度本身不是正确性保证。
- JSON Flow 显式列出 `next`/`branches`，Mermaid 用视觉边表达连接。应校验生成的定义，不能把流畅输出当作合规。

## Mermaid 可能适合的场景

- **简单路由流程** — 紧凑的边表示可能更便于审阅
- **对体积敏感的场景** — 使用目标 tokenizer 测量实际序列化输入
- **成本评估** — 比较提供方的实际输入费用，不预设固定节省比例
- **模型辅助编写** — 检查生成的语法和预期拓扑

## JSON Flow 可能适合的场景

- **复杂流程**（join、parallel、delegate、error routing）— `wait_for` 等显式字段可帮助结构审查；两种表示遵循相同的 AISOP 语义
- **程序化处理** — JSON 可以直接被代码解析验证，Mermaid 需要字符串解析
- **子任务** — `delegate_to` 和 `wait_for` 字段比 Mermaid 节点标签更明确
- **结构校验** — 可直接检查对象字段；结构校验本身不证明运行时安全或真人确认

## 结论

| 场景 | 推荐 | 原因 |
|------|------|------|
| 简单路由 / 意图匹配 | 可考虑 Mermaid | 紧凑边表示；仍需检查实际程序 |
| 复杂多步骤工作流 | 可考虑 JSON Flow | 显式结构字段；运行时语义仍重要 |
| 成本敏感部署 | 测量两种表示 | 取决于 tokenizer、序列化和流程 |
| 程序化生成流程 | JSON Flow | 原生 JSON，易于构建和验证 |

两种格式共享相同的函数定义和元数据。选择取决于流程复杂度和部署优先级。两种格式可以在同一程序中共存。

参考库只检查有限 Mermaid 子集，不执行业务流程，也不提供完整双向转换器。部分解析或静态成功不是运行时保证。

---

Align Axiom 0: Human Sovereignty and Wellbeing. Version: AISOP V1.0.0. www.aisop.dev
