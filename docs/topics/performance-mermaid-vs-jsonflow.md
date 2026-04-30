# Performance: Mermaid vs JSON Flow

## Token Count Comparison

The same flow expressed in both formats:

**Mermaid — ~40 tokens:**

```
graph TD
    N1{match} -->|matched| N2[execute_function]
    N1 -->|uncertain| N4[classify_function]
    N2 --> N3[end_function]
    N4 --> N2
```

**JSON Flow — ~60 tokens:**

```json
"main": {
    "N1": {"branches": {"matched": "N2", "uncertain": "N4"}},
    "N2": {"next": ["N3"]},
    "N3": {},
    "N4": {"next": ["N2"]}
}
```

Mermaid uses roughly **half the tokens** for the same flow definition. Fewer tokens = faster input processing + lower cost.

## LLM Comprehension

- Mermaid is a visual language with extensive presence in LLM training data. Branch relationships are immediately apparent.
- JSON flow requires layer-by-layer parsing of `next`/`branches` fields to trace the execution path.

## When Mermaid Wins

- **Simple routing flows** — fewer tokens, more intuitive for LLMs
- **Speed-sensitive scenarios** — lower latency due to compact representation
- **Cost optimization** — fewer input tokens = lower API cost
- **LLM-first workflows** — Mermaid is natively understood by LLMs

## When JSON Flow Wins

- **Complex flows** (join, parallel, delegate, error routing) — JSON semantics are more precise; `wait_for` provides explicit join declarations
- **Programmatic processing** — JSON can be directly parsed and validated by code; Mermaid requires string parsing
- **Sub-tasks** — `delegate_to` and `wait_for` fields are more explicit than Mermaid node labels
- **Strict validation** — JSON schema can enforce structure at the protocol level

## Conclusion

| Scenario | Recommended | Reason |
|----------|-------------|--------|
| Simple routing / intent matching | Mermaid | Fewer tokens, faster, intuitive |
| Complex multi-step workflows | JSON Flow | Precise semantics, no ambiguity |
| Cost-sensitive deployments | Mermaid | ~50% fewer flow tokens |
| Programmatic flow generation | JSON Flow | Native JSON, easy to build/validate |

Both formats share the same function definitions and metadata. The choice depends on flow complexity and deployment priorities. Both can coexist in the same program.

---

Align Axiom 0: Human Sovereignty and Wellbeing. Version: AISOP V1.0.0. www.aisop.dev
