# AISOP Protocol Documentation

Welcome to the **AI Standard Operating Protocol (AISOP)** documentation.

AISOP is an open protocol for defining structured AI programs using Mermaid or JSON flow graphs. It enables defining multi-step AI programs with visual or structural control flow — branching, parallel execution, sub-tasks, and error handling — all in a single portable JSON format.

---

## What is AISOP?

AISOP is the **format layer** of the AIXP protocol family. Every AISOP file (`.aisop.json`) consists of:

- **Mermaid graph** *or* **JSON Flow graph** — equivalent, machine-readable control flow
- **Function definitions** — step-based operations with `sys.*` calls, sub-tasks, or natural language
- **Sub-graph references** — composable building blocks via `aisop.<sub>` and `RUN aisop.*`
- **Deterministic expression engine** — `sys.assert` and conditional evaluation
- **24 protocol-reserved system calls** across 8 namespaces (I/O, run, assert, llm, code, state, event, security)

The protocol is anchored by **Axiom 0: Human Sovereignty and Wellbeing** — an immutable principle that no version of AISOP may weaken or remove. The execution-layer guarantee of Axiom 0 in AISOP is the **`sys.io.confirm` immutability** — it is forced-blocking at all trust levels and cannot be bypassed.

---

## Quick Navigation

### Topics

| Resource | Description |
|----------|-------------|
| [What is AISOP?](topics/what-is-aisop.md) | Understanding the protocol and why it exists |
| [Mermaid vs JSON Flow](topics/comparison-mermaid-vs-jsonflow.md) | Two equivalent representations |
| [Performance Comparison](topics/performance-mermaid-vs-jsonflow.md) | Runtime cost analysis |

### Architecture Decision Records

| ADR | Description |
|-----|-------------|
| [ADR-001: Mermaid as Primary Format](adrs/adr-001-mermaid-as-primary-format.md) | Why Mermaid + JSON Flow dual representation |
| [ADR-002: `sys.io.confirm` Immutability](adrs/adr-002-sys-io-confirm-immutability.md) | Axiom 0's execution-layer guarantee |

### Reference Implementations

| Implementation | Repository Path |
|---------------|----------------|
| Python | [`reference/python/`](https://github.com/AIXP-Labs/AISOP/tree/main/reference/python) |
| JavaScript | [`reference/javascript/`](https://github.com/AIXP-Labs/AISOP/tree/main/reference/javascript) |

---

## The AIXP Protocol Family

AISOP is one layer of a multi-protocol family. See [`GOVERNANCE.md`](https://github.com/AIXP-Labs/AISOP/blob/main/GOVERNANCE.md) for full details.

| Layer | Protocol | Repository |
|-------|----------|-----------|
| **Format** *(this repository)* | AISOP — `.aisop.json` syntax & semantics | [AISOP-Protocol](https://github.com/AIXP-Labs/AISOP) |
| Authority | AIAP — Governance, quality, compliance | [AIAP-Protocol](https://github.com/AIXP-Labs/AIAP) |
| Executor | SoulBot — Reference runtime | [SoulBot](https://github.com/AIXP-Labs/SoulBot) |

---

## Specification

The full normative specification is in [`specification/aisop-spec.md`](https://github.com/AIXP-Labs/AISOP/blob/main/specification/aisop-spec.md).

For the Chinese version, see [`specification/aisop-spec_CN.md`](https://github.com/AIXP-Labs/AISOP/blob/main/specification/aisop-spec_CN.md).

---

Align Axiom 0: Human Sovereignty and Wellbeing. Version: AISOP V1.0.0. www.aisop.dev
