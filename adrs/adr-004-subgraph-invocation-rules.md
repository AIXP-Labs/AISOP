# ADR-004: Subgraph Invocation Rules

**Status**: Accepted
**Date**: 2026-11-15
**Deciders**: AISOP maintainers

## Context

Peer aisop graphs already exist, but calling, returning, target resolution and shared-function interpretation need explicit rules independent of any host or derived protocol.

## Decision

- Graphs remain peers of main; sub_mermaid/sub_jsonflow are descriptions, not new containers. Prefer functional ASCII identifiers.
- Keep Mermaid whole aisop.<name> labels, bare JSON delegate_to names, and whole RUN steps with optional node-local result storage. See [ADR-003](adr-003-step-mode-exclusivity.md).
- Prepare before implicit delegation. Same-target explicit steps locate calls within preparation/result handling; each actually reached step calls once and labels add no extra call. Failure or rejection can prevent later calls.
- Resolve valid local targets first. A standalone file rejects absent targets. Components may use a strict-boolean consumer callback; callback exceptions and non-booleans are errors, and unresolved targets without it warn. A consumer claim is not trust or target-conformance proof.
- Keep parent locals until that parent completes; restrict child context and explicitly define business completion outputs. Do not add a universal return field, global last_result or implicit context merge.
- Keep routing local. An actually missing valid runtime target raises subgraph_not_found; exact on_error, existing category matching, default and Mermaid/JSON error edges precede propagation of unhandled errors to the parent call node. Only an unhandled outermost main error terminates the program. No new category taxonomy, rollback or automatic retry is defined.
- Reject local subgraph call cycles, not ordinary flow loops. Warn about shared names unless all uses are entries or all are terminal, and about graphs with no valid incoming call.
- Keep flow_format required; delegate priority preserves post-call branches. Preserve confirmation at each actual arrival, never reuse approval.
- Keep protocol and package versions at 1.0.0. Record this clarification and stricter validation honestly in CHANGELOG.

## Alternatives

New subgraph containers, prefixed JSON delegates, host-specific directory loading and an execution engine in the reference libraries were rejected as unnecessary scope. Repeated calls are not globally deduplicated.

## Consequences

The reference checker supports a finite Mermaid subset and reports unsupported lines as PARSE_PARTIAL. It cannot prove runtime returns, error propagation, confirmation, actual call counts, cross-file acyclicity or full reachability. Static ERROR is not downgraded by an on_error handler. The six SYS_ERROR_TYPES remain a sys-only subset.

## References

- AISOP specification §4.4, §5.2.1, §5.3, §6.9 and §6.12.

---

Align Axiom 0: Human Sovereignty and Wellbeing. Version: AISOP V1.0.0. www.aisop.dev

## Partial Supersession — 2026-11-16

Only the category-matching portion of the historical error-routing decision above is superseded. Current matching is exact type, default, the current graph's Mermaid/JSON error edge, then the parent caller; only an unhandled outermost main error terminates execution. See specification §5.2.4 and §6.12. Custom error names remain exact matches; no implicit timeout category exists. All other decisions and the original historical text remain in force.
