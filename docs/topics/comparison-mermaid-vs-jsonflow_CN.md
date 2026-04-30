# Mermaid vs JSON Flow：控制流对比

## 概览

| 控制结构 | Mermaid | JSON Flow | 备注 |
|---------|---------|-----------|------|
| 顺序 | 支持 | 支持 | 等价 |
| 二分支 | 支持 | 支持 | 等价 |
| 多分支 | 支持 | 支持 | 等价 |
| 并行分叉 | 支持 | 支持 | 等价 |
| 并行汇合 | 支持 | 支持 | JSON Flow 更明确 |
| 回环 | 支持 | 支持 | 等价 |
| 子流程 | 支持 | 支持 | JSON Flow 有 `delegate_to` |
| 收敛 | 支持 | 支持 | 等价 |
| 错误路由 | 支持 | 支持 | 两者都有原生错误边 |

---

## 逐项对比

### 1. 顺序

**Mermaid：**
```mermaid
graph TD
    greet[Greet] --> classify[Classify] --> reply[Reply] --> end_node((End))
```

**JSON Flow：**
```json
{
  "greet":    { "next": ["classify"] },
  "classify": { "next": ["reply"] },
  "reply":    { "next": ["end"] },
  "end":      {}
}
```

---

### 2. 二分支

**Mermaid：**
```mermaid
graph TD
    check{Check?} -->|yes| approve[Approve]
    check -->|no| reject[Reject]
```

**JSON Flow：**
```json
{
  "check": { "branches": { "yes": "approve", "no": "reject" } }
}
```

---

### 3. 多分支

**Mermaid：**
```mermaid
graph TD
    route{Route?} -->|billing| billing[Billing]
    route -->|tech| tech[Tech]
    route -->|other| general[General]
```

**JSON Flow：**
```json
{
  "route": {
    "branches": { "billing": "billing", "tech": "tech", "other": "general" }
  }
}
```

---

### 4. 并行分叉

**Mermaid：**
```mermaid
graph TD
    prepare[Prepare] --> step_a[Step A]
    prepare --> step_b[Step B]
```

**JSON Flow：**
```json
{
  "prepare": { "next": ["step_a", "step_b"] }
}
```

---

### 5. 并行汇合

**Mermaid：**
```mermaid
graph TD
    step_a[Step A] --> sync[Sync]
    step_b[Step B] --> sync
    sync --> finish[Finish]
```

**JSON Flow：**
```json
{
  "step_a": { "next": ["sync"] },
  "step_b": { "next": ["sync"] },
  "sync":   { "wait_for": ["step_a", "step_b"], "next": ["finish"] }
}
```

JSON Flow 优势：`wait_for` 明确声明需要等待的节点。Mermaid 的视觉汇聚暗示汇合行为，但没有明确的等待列表 — 汇合语义来自函数中的 `join` 键。

---

### 6. 回环

**Mermaid：**
```mermaid
graph TD
    attempt[Attempt] --> check{Quality?}
    check -->|retry| attempt
    check -->|pass| done((Done))
```

**JSON Flow：**
```json
{
  "attempt": { "next": ["check"] },
  "check":   { "branches": { "retry": "attempt", "pass": "done" } }
}
```

---

### 7. 子流程（Delegate）

**Mermaid：**
```mermaid
graph TD
    prepare[Prepare] --> call_sub[aisop.validation]
    call_sub --> continue_main[Continue]
```

子任务（`validation`）：
```mermaid
graph TD
    check_input[Check Input] --> verify[Verify]
    verify --> done((Done))
```

**JSON Flow：**

主任务：
```json
{
  "prepare":  { "next": ["call_sub"] },
  "call_sub": { "delegate_to": "validation", "next": ["continue_main"] }
}
```

子任务（`validation`）：
```json
{
  "check_input": { "next": ["verify"] },
  "verify":      { "next": ["done"] },
  "done":        {}
}
```

两者都支持子任务复用。Mermaid 通过节点标签 `aisop.<sub>` 表达委派。JSON Flow 使用 `delegate_to` 字段。

两种格式还支持步骤层子任务调用：函数步骤文本中的 `RUN aisop.<sub>`。

---

### 8. 收敛

**Mermaid：**
```mermaid
graph TD
    route{Route?} -->|a| handle_a[Handle A]
    route -->|b| handle_b[Handle B]
    route -->|c| handle_c[Handle C]
    handle_a --> merge[Merge]
    handle_b --> merge
    handle_c --> merge
```

**JSON Flow：**
```json
{
  "route":    { "branches": { "a": "handle_a", "b": "handle_b", "c": "handle_c" } },
  "handle_a": { "next": ["merge"] },
  "handle_b": { "next": ["merge"] },
  "handle_c": { "next": ["merge"] },
  "merge":    { "next": ["end"] }
}
```

---

### 9. 错误路由

**Mermaid：**
```mermaid
graph TD
    risky_step[Risky Step] --> continue_step[Continue]
    risky_step -.-> error_handler[Error Handler]
    error_handler --> end_node((End))
```

**JSON Flow：**
```json
{
  "risky_step": {
    "next": ["continue"],
    "error": "error_handler"
  },
  "error_handler": {
    "next": ["end"]
  }
}
```

两者都有原生错误路由。Mermaid 使用虚线边 `-.->`. JSON Flow 使用 `error` 字段。两者都支持通过函数中的 `on_error` 进行精细错误路由。

---

## 总结

| 维度 | Mermaid | JSON Flow |
|------|---------|-----------|
| 用途 | Token 高效的可视化流程 | 精确的结构化定义 |
| Token 数量 | 约 40 tokens（仅流程） | 约 60 tokens（仅流程） |
| LLM 理解度 | 高 — 训练数据中大量存在 | 中 — 需要解析 JSON 字段 |
| 机器可读 | 需要 Mermaid 解析器 | 原生 JSON |
| 错误处理 | `-.->` 虚线边 + `on_error` | `error` 字段 + `on_error` |
| 并行汇合 | 视觉汇聚 + 函数中的 `join` | 明确的 `wait_for` + 函数中的 `join` |
| 子任务 | `aisop.<sub>` 节点标签 + `RUN aisop.sub` | `delegate_to` 字段 + `RUN aisop.sub` |
| 可视化 | 原生 Mermaid 渲染 | 可转换为 Mermaid 显示 |

**设计原则**：两种格式共享相同的函数定义（§5）和元数据格式（§2）。唯一区别是流程图（§4）的表达方式 — Mermaid 字符串 vs JSON flow 对象。两种格式可以在同一程序中共存。

---

Align Axiom 0: Human Sovereignty and Wellbeing. Version: AISOP V1.0.0. www.aisop.dev
