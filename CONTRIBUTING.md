# How to Contribute

> ⚠️ **Contribution Status (Current Stage)**
>
> We welcome **discussion through GitHub Issues** at this stage of development.
>
> **External Pull Requests are not currently accepted.** If you have a proposal — bug report, feature idea, specification clarification, or implementation suggestion — please open an issue describing it. If we agree it adds value, maintainers will implement it and credit you.
>
> This policy may be revisited in the future.

> **Stage Status (v1.0.0)**
>
> AISOP is at early specification stage. Initial decisions are made by AIXP Labs core maintainers; community discussion period scales as the contributor base grows.

## Ways to Contribute (via Issues)

- **Specification** — Propose changes to the protocol spec
- **Reference Implementations** — Suggest implementations in new languages (Go, Java, Rust, etc.)
- **Documentation** — Suggest improvements, tutorials, typo fixes
- **Test Cases** — Propose new test scenarios for edge cases
- **Bug Reports** — Report issues with the spec or reference implementations

## Contribution Process

1. **Open an issue** describing your proposal, bug, or idea
2. **Discuss** with maintainers — clarify scope, design, and approach
3. **If accepted**, maintainers will implement the change and credit you in commit/release notes

## Guidelines

- Keep the protocol simple — complexity is a bug, not a feature
- Reference implementations should have zero external dependencies
- All control flow patterns must have corresponding test cases
- Protocol changes require updating both the spec and reference implementation

## Running Tests

```bash
cd reference/python
python test_all.py
```

All tests must pass before submitting.

## Writing Guidelines

### RFC 2119 Keywords

When writing normative specification text, use the keywords defined in [RFC 2119](https://tools.ietf.org/html/rfc2119):

- **MUST** / **MUST NOT** — Absolute requirements
- **SHOULD** / **SHOULD NOT** — Strong recommendations with documented exceptions
- **MAY** — Truly optional behavior

These keywords MUST be capitalized when used in their normative sense.

### Terminology

- Use "AISOP file" for individual `.aisop.json` files
- Use "AISOP program" or "flow program" for executable AISOP definitions
- Capitalize "Axiom 0" (it is a proper noun)
- Reference "Mermaid graph" or "JSON flow graph" — not bare "graph"
- Use "sys.* call" for system calls (e.g., "sys.io.confirm call")
- Capitalize control flow constructs: Branch, Sub-task, Parallel execution

### Document Structure

- Begin each topic document with a one-paragraph introduction
- Use tables for field specifications
- Use code blocks with language annotations for examples
- Use Mermaid diagrams for flow and architecture illustrations
- Cross-reference between documents using relative links

### Closing Seal

All specification documents MUST end with:

```
Align Axiom 0: Human Sovereignty and Wellbeing. Version: AISOP V1.0.0. www.aisop.dev
```

## Code of Conduct

Be respectful, constructive, and focused on making the protocol better for everyone.

## License of Contributions

By submitting an issue or any other content (including specification proposals, code snippets in issues, or design suggestions), you agree that your submitted content may be used by maintainers under the terms of the [Apache License, Version 2.0](LICENSE), the same license as the project.

## Axiom Constraint

All contributions must comply with **Axiom 0: Human Sovereignty and Wellbeing**. Any changes that harm human health, dignity, or freedom will not be accepted.

---

Align Axiom 0: Human Sovereignty and Wellbeing. Version: AISOP V1.0.0. www.aisop.dev
