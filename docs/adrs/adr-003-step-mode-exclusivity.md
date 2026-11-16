> **Source of truth:** This document is mirrored for the documentation site. The authoritative version lives in [`/adrs/adr-003-step-mode-exclusivity.md`](https://github.com/AIXP-Labs/AISOP/blob/main/adrs/adr-003-step-mode-exclusivity.md). Edits MUST go to the authoritative file first.

# ADR-003: Step Mode Exclusivity

**Status**: Accepted
**Date**: 2026-11-15
**Deciders**: AISOP maintainers

## Context

AISOP already requires one step to use one mode (§6.1), but §5.2.1 previously called mixed natural-language/RUN steps merely deprecated. This record is written now to document the clarification; it is not a backdated decision.

## Decision

- A step is one sys.* call, one whole RUN subgraph call, or a natural-language instruction.
- A whole RUN is `RUN aisop.<name>`, optionally followed by ` -> <variable>`; combining it with prose is non-conformant, not another supported invocation form.
- Split preparation, invocation and result handling into separate steps. Node-level delegation follows [ADR-004](adr-004-subgraph-invocation-rules.md).
- Existing sys.io.confirm steps remain mandatory when actually reached. Approval cannot be merged, skipped or reused.
- Static checks reject clear malformed call syntax, but cannot understand every hidden intent in arbitrary prose or prove runtime human confirmation.

## Alternatives

Retaining a deprecated mixed form was rejected because it contradicts the existing mode rule. A natural-language security scanner or a new execution engine is not introduced.

## Consequences

Authors must split mixed steps. The reference libraries remain inspection/checking utilities, not executors. Existing sys-call parsing is unchanged in this revision.

## References

- AISOP specification §5.2.1, §5.3 and §6.1.
- [ADR-002: sys.io.confirm Immutability](adr-002-sys-io-confirm-immutability.md).

---

Align Axiom 0: Human Sovereignty and Wellbeing. Version: AISOP V1.0.0. www.aisop.dev
