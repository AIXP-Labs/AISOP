# ADR-001: Mermaid as Primary Flow Format (with JSON Flow Equivalence)

**Status**: Accepted
**Date**: 2026-04-15
**Deciders**: AISOP maintainers

## Context

AI agent programs need a structured, portable way to represent multi-step workflows: branches, parallel execution, sub-tasks, error handling. Several format candidates were available:

- **BPMN 2.0** — Industry-standard but complex (XML-heavy, designed for human business analysts)
- **Mermaid** — Lightweight text format, GitHub-native rendering, widely adopted in AI/dev tooling
- **JSON-only DAG** — Pure JSON nodes/edges arrays
- **YAML state machines** — Human-readable but ambiguous parse rules
- **Custom DSL** — Maximum control but requires custom toolchain

AISOP must serve two equally important consumers: **humans** (visual review of program logic) and **machines** (automated parsing, validation, execution).

## Decision

AISOP defines **two equivalent representations** with bidirectional translation:

1. **Mermaid graph** (primary, in `aisop.main` and `aisop.<sub>` fields) — human-friendly, GitHub renders inline
2. **JSON Flow graph** (alternative, in `flow.main` and `flow.<sub>` fields) — machine-direct, no parser needed

Both representations carry the **same semantic content**. Implementations MUST accept either form and produce identical execution behavior.

The primary format identifier is `flow_format: "mermaid"` or `flow_format: "json"` in the AISOP file metadata.

## Rationale

- **Mermaid wins on adoption**: GitHub-native rendering, built into VS Code, recognized by most LLMs in their training data
- **JSON wins on machine determinism**: No parser ambiguity, faster validation, cleaner programmatic generation
- **Equivalence is non-negotiable**: A protocol that allows two representations to drift is not a protocol — it's two protocols
- **BPMN was rejected**: Excessive complexity for AI agent use cases, XML-only, weak LLM training coverage
- **Custom DSL was rejected**: Forces every implementer to build a parser; Mermaid + JSON together cover both ergonomic axes without custom tooling

## Consequences

### Positive

- Visual review on GitHub without external tools
- LLMs can directly generate Mermaid (high training coverage)
- Programmatic generation can target JSON Flow (no string templating)
- Implementations choose either parser path based on their language ecosystem
- Cross-implementation parity is achievable by validating the JSON Flow round-trip

### Negative

- Implementations must support both formats (or document which is supported)
- Bidirectional translation rules add specification surface area
- Mermaid's syntax has informal edge cases that require AISOP-specific clarification

### Neutral

- The reference Python and JavaScript implementations both default to Mermaid input but produce JSON Flow as the canonical internal representation

## Alternatives Considered

### Alternative 1: Mermaid only (no JSON Flow)

Rejected because programmatic generation tools must template strings — error-prone and harder to validate.

### Alternative 2: JSON Flow only (no Mermaid)

Rejected because it loses human-visible control flow review on GitHub. AISOP files would become opaque blobs.

### Alternative 3: BPMN 2.0

Rejected for excessive complexity. BPMN serves business process modeling with formal swim-lanes and event types that AI agent workflows do not need.

## References

- Specification: `specification/aisop-spec.md` §Mermaid Parsing Rules, §JSON Flow Schema
- Performance comparison: `docs/performance-mermaid-vs-jsonflow.md`
- Format comparison: `docs/comparison-mermaid-vs-jsonflow.md`

---

Align Axiom 0: Human Sovereignty and Wellbeing. Version: AISOP V1.0.0. www.aisop.dev
