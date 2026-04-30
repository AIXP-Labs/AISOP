# AISOP Ecosystem Governance

The AI Standard Operating Protocol (AISOP) is the **format layer** of the AIXP protocol family. It defines the syntax and execution semantics of `.aisop.json` files — neutral, foundational, and unconcerned with application ethics or runtime behavior.

## The Tripartite Chain

The AIXP protocol family operates on a strict separation of concerns across three authoritative domains. **All layers are licensed under Apache 2.0** for unified patent protection and ecosystem consistency. **This repository** (`AISOP-Protocol`) governs the aisop.dev Seed Layer.

### 1. The Seed Layer (`aisop.dev`) — *This repository*

The origin of the format.

- **Responsibility**: Defines the underlying `.aisop.json` language specification, Mermaid graph parsing rules, JSON Flow equivalence, the System/User execution model, and the `sys.*` system call family.
- **Philosophy**: Neutral, static, foundational. Unconcerned with ethics, application logic, or runtime policy enforcement.
- **License**: Apache 2.0 — unified across the AIXP protocol family.

### 2. The Authority Layer (`aiap.dev`)

The source of governance and the steward of Axiom 0.

- **Responsibility**: Maintains the `AIAP_Protocol.md` structural specification, the `AIAP_Standard.*.aisop.json` quality gates, and enforces the Zero-Entropy and L0 isolation rules over AISOP files.
- **Philosophy**: Rigorous, uncompromising. Ensures that all compliant intelligence adheres to "Human Sovereignty and Wellbeing."
- **License**: Apache 2.0.
- **Repository**: [AIAP-Protocol](https://github.com/AIXP-Labs/AIAP)

### 3. The Executor Layer (`soulbot.dev`)

The reference runtime environment.

- **Responsibility**: Instantiates AI agents, parses AISOP files, dispatches `sys.*` calls, manages memory, and enforces the `permissions` declared in AIAP contracts at runtime.
- **Philosophy**: Secure, performant, sandboxed.
- **License**: Apache 2.0.
- **Repository**: [SoulBot](https://github.com/AIXP-Labs/SoulBot)

## AISOP Scope (What This Layer Owns)

AISOP is the format layer. It defines:

- **`.aisop.json` schema** — required fields, control flow constructs, error edges
- **Mermaid graph parsing** — node types, edge semantics, sub-graph references
- **JSON Flow equivalence** — bidirectional translation between Mermaid and JSON
- **Step text classification** — `sys.*` calls, `RUN aisop.*` sub-tasks, natural language
- **`sys.*` system calls** — 24 protocol-reserved primitives across 8 namespaces
- **Deterministic expression engine** — `sys.assert` and conditional evaluation
- **Return value syntax** — `-> variable_name` for `sys.*` results

AISOP does **not** define:

- Quality rules or compliance checks (that is AIAP's role)
- Trust levels or permission boundaries (that is AIAP's role)
- Runtime sandboxing or tool resolution (that is SoulBot's role)
- Ethics enforcement beyond the immutable `sys.io.confirm` guarantee

## Axiom 0 Immutability

**Axiom 0: "Human Sovereignty and Wellbeing" is immutable.**

No major, minor, or patch release of the AISOP protocol may ever modify, weaken, or deprecate the core alignment to Human Sovereignty and Wellbeing. This constraint is absolute and non-negotiable.

The execution-layer guarantee of Axiom 0 in AISOP is the **`sys.io.confirm` immutability**:

- `sys.io.confirm` is **forced-blocking** at all trust levels
- No protocol revision may add a bypass mechanism, silent-degradation path, or trust-level exception
- Any protocol change request that weakens `sys.io.confirm` semantics will be rejected regardless of performance benefits, commercial pressure, or technical convenience

## Versioning

Changes to the AISOP protocol follow strict Semantic Versioning (SemVer):

- **Major**: Breaking changes to the `.aisop.json` schema or `sys.*` semantics
- **Minor**: Backward-compatible additions (new `sys.*` calls, new control flow constructs)
- **Patch**: Bug fixes, documentation corrections, non-normative clarifications

The Axiom 0 immutability constraint supersedes all versioning rules.

## Protocol Steering

The AIXP protocol family is maintained by AIXP Labs across the three domains:

| Domain | Role | Scope |
|--------|------|-------|
| `aisop.dev` | **Format Steward** *(this repository)* | `.aisop.json` specification, field definitions, `sys.*` calls |
| `aiap.dev` | Governance Steward | Protocol rules, quality standards, security model |
| `soulbot.dev` | Runtime Steward | Reference implementation, tool resolution, execution |

### Decision Process

1. **Proposals**: Submit specification change requests via GitHub Issues
2. **Discussion**: Open discussion period (target governance: 14 days for normative changes; current windows scale with contributor count)
3. **Review**: Maintainers review for Axiom 0 compliance, technical soundness, and backward compatibility
4. **Cross-implementation parity**: Changes affecting `sys.*` semantics or step classification require parallel updates in both Python and JavaScript reference implementations
5. **Documentation**: Normative changes update both the specification and the changelog

## Communication

- **GitHub Issues**: Primary channel for specification discussions and proposals
- **GitHub Discussions**: Community questions and broader conversations

---

Align Axiom 0: Human Sovereignty and Wellbeing. Version: AISOP V1.0.0. www.aisop.dev
