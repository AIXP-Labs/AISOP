> **Source of truth:** This document is mirrored for the documentation site. The authoritative version lives in [`/adrs/adr-002-sys-io-confirm-immutability.md`](https://github.com/AIXP-Labs/AISOP/blob/main/adrs/adr-002-sys-io-confirm-immutability.md). Edits MUST go to the authoritative file first.

# ADR-002: `sys.io.confirm` Immutability as the Execution-Layer Guarantee of Axiom 0

**Status**: Accepted
**Date**: 2026-04-15
**Deciders**: AISOP maintainers

## Context

Axiom 0 ("Human Sovereignty and Wellbeing") is a normative principle — but principles without enforcement mechanisms drift over time. Every protocol that aspires to long-term safety needs at least one execution-layer construct that:

- Is **mechanically verifiable** (not just declarative text)
- Cannot be silently bypassed by trust-level escalation
- Preserves human authority at the point where it matters most: irreversible decisions

The candidate constructs that could carry this weight in AISOP:

- A blocking I/O primitive requiring human acknowledgment before continuation
- An assertion mechanism that halts execution on failure
- A formal proof system over the program graph
- A trust-level registry with maintainer-controlled escalation

## Decision

`sys.io.confirm` is the **inviolable** execution-layer guarantee of Axiom 0:

1. `sys.io.confirm` is **forced-blocking**. It cannot return until the human operator responds.
2. **No trust level may bypass it.** Even at the highest trust tier, `sys.io.confirm` blocks.
3. **No protocol revision may add a bypass mechanism.** Any future ADR proposing such a bypass is automatically rejected as a violation of Axiom 0.
4. **No silent degradation.** Implementations must not substitute `sys.io.confirm` with auto-confirm, timeout-pass-through, or default-yes behavior.
5. **Audit trail required.** Every `sys.io.confirm` invocation must be observable in the execution trace.

## Rationale

- **One inviolable primitive is enough.** A protocol that has even a single guaranteed human-in-the-loop point at irreversible decisions cannot be trivially weaponized.
- **Trust-level bypass would defeat the purpose.** A "skip confirm at T4" rule would force the question of who controls the trust level — and that authority becomes the new attack surface.
- **Mechanical enforcement is verifiable.** Reference implementations can include a test that asserts no code path returns from `sys.io.confirm` without a real human response.
- **The guarantee is minimal.** It does not constrain creativity, performance, or sophistication — it only protects the moment of human decision.

## Consequences

### Positive

- AISOP programs gain a verifiable safety floor that does not depend on prompt engineering or LLM compliance
- Reference implementations can mechanically assert this property in test suites
- AIAP governance (in AIAP-Protocol) can build quality rules on top of this guarantee (e.g., MF32 in AIAP_Standard.core)
- Long-term protocol evolution has a fixed point: any change must preserve this invariant

### Negative

- Programs that legitimately want unattended automation must use other primitives (e.g., `sys.io.notify`, `sys.event.emit`) and design around the human checkpoint
- Implementations must invest in a real human-confirmation UI (cannot stub it out)

### Neutral

- The specific UX of confirmation (text prompt, dialog, voice, etc.) is implementation-defined; only the blocking semantics are normative

## Alternatives Considered

### Alternative 1: Trust-level bypass at T4

Rejected. Adding a trust-level bypass shifts the safety boundary from `sys.io.confirm` itself to the trust-level assignment process — which then becomes the new weak link.

### Alternative 2: Timeout-with-default-action

Rejected. Any non-blocking semantics break the "human authority at irreversible decisions" guarantee. A timeout with auto-proceed is functionally equivalent to no confirmation.

### Alternative 3: Multiple inviolable primitives

Considered for `sys.security.audit`, `sys.assert`, etc. — rejected for v1.0.0 to keep the inviolable surface minimal. Future ADRs may add additional inviolable primitives if a clear case emerges.

## References

- Specification: `specification/aisop-spec.md` §sys.io.confirm
- Related: AIAP_Standard.core MF32 (AIAP-side enforcement of this invariant)
- Related: ADR-003 (Step Mode Exclusivity) — prevents `sys.io.confirm` from being smuggled in as natural-language text
- CODE_OF_CONDUCT.md — explicit rejection of any change that weakens this guarantee

---

Align Axiom 0: Human Sovereignty and Wellbeing. Version: AISOP V1.0.0. www.aisop.dev
