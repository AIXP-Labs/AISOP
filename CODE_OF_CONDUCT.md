# Code of Conduct

## Our Pledge: Axiom 0

In the interest of fostering an open, safe, and rigorous environment for the development of structured AI programs, we pledge to prioritize **Human Sovereignty and Wellbeing** above all experimental, commercial, or computational goals.

This pledge is known as **Axiom 0**.

## Standards

Examples of behavior that contributes to a positive environment for our community include:

- Demonstrating empathy and kindness toward other contributors
- Maintaining specification rigor — every protocol clause must be precise, testable, and unambiguous
- Gracefully accepting constructive feedback on protocol design
- Prioritizing the physical and psychological safety of end-users whose programs run under AISOP
- Being transparent about the limitations and edge cases of the format
- Preserving cross-implementation compatibility — AISOP should behave the same in Python, JavaScript, and any future implementer-equivalent runtime

Examples of unacceptable behavior include:

- Proposing modifications to the AISOP protocol that compromise, dilute, or bypass Axiom 0
- Weakening the `sys.io.confirm` blocking semantics in any way (it is the execution-layer guarantee of Axiom 0)
- Introducing ambiguous step-text classification rules that allow agents to silently coerce one mode into another (e.g., `sys.*` masquerading as natural language)
- Adding control-flow constructs that lack deterministic equivalents in both Mermaid and JSON Flow representations
- Submitting reference-implementation changes that diverge in observable behavior between Python and JavaScript without justification
- Public or private harassment of other contributors
- Publishing others' private information without explicit permission

## Scope

This Code of Conduct applies within all community spaces, including GitHub repositories, discussions, issues, pull requests, and any other communication channels associated with the AISOP project.

## Enforcement Responsibilities

The AISOP Protocol maintainers are responsible for clarifying and enforcing our standards of acceptable behavior.

Any protocol change request that compromises Axiom 0 — particularly the immutability of `sys.io.confirm` — will be rejected regardless of performance benefits, ergonomics improvements, or technical convenience.

## Reporting

Instances of unacceptable behavior may be reported to the AISOP Protocol maintainers through the channels listed in [SECURITY.md](SECURITY.md).

All reports will be reviewed and investigated promptly and fairly.

---

Align Axiom 0: Human Sovereignty and Wellbeing. Version: AISOP V1.0.0. www.aisop.dev
