# Performance: Mermaid vs JSON Flow

## Illustrative Representations

The same flow expressed in both formats below is a representation-only illustration, not a measured benchmark or a standalone AISOP program. The JSON example shows a graph member.

**Mermaid:**

```
graph TD
    N1{match} -->|matched| N2[execute_function]
    N1 -->|uncertain| N4[classify_function]
    N2 --> N3[end_function]
    N4 --> N2
```

**JSON Flow graph member:**

```json
"main": {
    "N1": {"branches": {"matched": "N2", "uncertain": "N4"}},
    "N2": {"next": ["N3"]},
    "N3": {},
    "N4": {"next": ["N2"]}
}
```

Token counts depend on the tokenizer, labels, workflow structure and serialization/formatting. Mermaid may be more compact for some flows, but this page provides no measured token, latency, cost or accuracy comparison and promises no universal saving.

## LLM Comprehension

- Model understanding of either notation depends on the model and task; training-data familiarity alone is not a correctness guarantee.
- JSON Flow exposes `next`/`branches` explicitly, while Mermaid expresses edges visually. Validate generated definitions instead of treating fluent output as conformance.

## When Mermaid May Fit

- **Simple routing flows** — compact edge notation may be easier to review
- **Size-sensitive scenarios** — measure the actual serialized input with the target tokenizer
- **Cost evaluation** — compare actual provider input costs rather than assuming a fixed percentage
- **Model-assisted authoring** — check the generated syntax and intended topology

## When JSON Flow May Fit

- **Complex flows** (join, parallel, delegate, error routing) — explicit fields such as `wait_for` can aid structural inspection; both notations follow the same AISOP semantics
- **Programmatic processing** — JSON can be directly parsed and validated by code; Mermaid requires string parsing
- **Sub-tasks** — `delegate_to` and `wait_for` fields are more explicit than Mermaid node labels
- **Structured validation** — object fields can be checked directly; structural validation alone does not prove runtime safety or human confirmation

## Conclusion

| Scenario | Recommended | Reason |
|----------|-------------|--------|
| Simple routing / intent matching | Consider Mermaid | Compact edge notation; check the actual program |
| Complex multi-step workflows | Consider JSON Flow | Explicit structural fields; runtime semantics still matter |
| Cost-sensitive deployments | Measure both | Tokenizer, serialization and workflow dependent |
| Programmatic flow generation | JSON Flow | Native JSON, easy to build/validate |

Both formats share the same function definitions and metadata. The choice depends on flow complexity and deployment priorities. Both can coexist in the same program.

The reference libraries inspect a finite Mermaid subset and do not execute business flows or provide a complete bidirectional converter. Partial parsing or static success is not a runtime guarantee.

---

Align Axiom 0: Human Sovereignty and Wellbeing. Version: AISOP V1.0.0. www.aisop.dev
