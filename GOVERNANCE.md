# AISOP Ecosystem Governance

The AI Standard Operating Protocol (AISOP) is the **format layer** of the AIXP protocol family. It independently defines the syntax and execution semantics of `.aisop.json` files, including Axiom 0 and confirmation requirements. It does not itself implement application governance, a sandbox or an execution service.

## The Tripartite Chain as an Ecosystem View

The following format, governance and execution roles describe an ecosystem division of responsibility, not a required dependency chain or exclusive list of implementations. **This repository** (`AISOP-Protocol`) maintains the aisop.dev format specification under Apache 2.0. Other projects govern their own contracts; they do not override AISOP syntax, execution semantics or Axiom 0.

### 1. The Seed Layer (`aisop.dev`) — *This repository*

The origin of the format.

- **Responsibility**: Defines the underlying `.aisop.json` language specification, Mermaid graph parsing rules, JSON Flow equivalence, the System/User execution model, and the `sys.*` system call family.
- **Philosophy**: Foundational and host-neutral. Defines Axiom 0 and execution requirements while leaving application-specific policy and concrete enforcement to consumers and implementations.
- **License**: Apache 2.0 — unified across the AIXP protocol family.

### 2. A Consuming Governance Protocol (`aiap.dev`)

A governance example within AIXP, not an authority above the AISOP specification.

- **Responsibility**: Maintains AIAP package structures and its own quality and governance rules for AISOP-based applications. AIAP and other consuming protocols must align with AISOP rather than redefine its base format.
- **Philosophy**: Rigorous, uncompromising. Ensures that all compliant intelligence adheres to "Human Sovereignty and Wellbeing."
- **License**: Apache 2.0.
- **Repository**: [AIAP-Protocol](https://github.com/AIXP-Labs/AIAP)

### 3. A Runtime and Hosting Project (`soulbot.dev`)

A runtime/hosting example in the ecosystem, not a prerequisite or sole executor for AISOP.

- **Responsibility**: Hosts and orchestrates AISOP-based applications. Concrete parsing, dispatch, sandboxing, memory and permission enforcement belong to the chosen implementation and its contracts; this document does not certify an implementation or prescribe a particular execution service.
- **Philosophy**: Secure, performant, sandboxed.
- **License**: Apache 2.0.
- **Repository**: [SoulBot](https://github.com/AIXP-Labs/SoulBot)

## AISOP Scope (What This Layer Owns)

AISOP is the format layer. It defines:

- **`.aisop.json` schema** — required fields, control flow constructs, error edges
- **Mermaid graph parsing** — node types, edge semantics, sub-graph references
- **JSON Flow equivalence** — corresponding control-flow meaning of the supported Mermaid and JSON Flow forms; parser coverage and conversion capabilities are documented separately
- **Step text classification** — `sys.*` calls, `RUN aisop.*` sub-tasks, natural language
- **`sys.*` system calls** — 24 protocol-reserved primitives across 8 namespaces
- **Deterministic expression engine** — `sys.assert` and conditional evaluation
- **Return value syntax** — `-> variable_name` for `sys.*` and whole RUN results under the specification's node-local rules

AISOP does **not** define:

- Application/package quality rules beyond AISOP's own format conformance (consuming protocols may add them)
- Application trust levels or package-specific permission models
- A concrete runtime sandbox, tool resolver or exclusive executor
- A complete application ethics-enforcement system; Axiom 0 and confirmation requirements remain part of AISOP

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

These project locations illustrate the roles above; no registration with another protocol or runtime is required to define an AISOP program:

| Domain | Role | Scope |
|--------|------|-------|
| `aisop.dev` | **Format Steward** *(this repository)* | `.aisop.json` specification, field definitions, `sys.*` calls |
| `aiap.dev` | Consuming governance protocol | AIAP package rules, quality standards and security model |
| `soulbot.dev` | Runtime/hosting example | Application hosting and implementation-specific orchestration |

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
