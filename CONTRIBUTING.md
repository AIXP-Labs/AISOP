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
- Reference libraries and their tests should have zero external runtime dependencies; package-build and optional documentation tooling are separate
- All control flow patterns must have corresponding test cases
- Protocol changes require updating both the spec and reference implementation

## Running Tests

Maintainers should run both suites directly from the repository root:

```bash
cd reference/python
python -B test_all.py
cd ../javascript
node test_all.js
```

Both suites must pass for implementation changes. Static rejection cases pass when they produce the expected errors; a passing checker is not proof of business execution or human confirmation. Documentation-only work does not require repeating unchanged, already-recorded suites.

### Environment Requirements

- Running the reference libraries and their tests requires only Python's standard library or Node.js built-ins; no pip/npm installation is needed.
- Python package builds separately use the setuptools backend in [pyproject.toml](reference/python/pyproject.toml), currently 77+ for SPDX license metadata.
- Optional site builds require a compatible MkDocs, Material theme and Pymdown Extensions environment for `mkdocs.yml`. Do not report an unavailable or skipped build as passing.
- The Python package declares Python 3.10+. The repository CI configuration covers Python 3.10-3.15 and Node.js 24 on ubuntu-24.04 and windows-2022. A configured matrix is not evidence of a successful workflow run.
- Use the direct commands above, not `python run.py --test` as a release gate: that Python wrapper does not propagate a child test process's nonzero exit status.

### Privacy Before Sharing

Use synthetic examples and redact private input before posting an issue or attaching logs. Inspection prints metadata and steps, and `--prompt` prints the constructed prompt; command arguments may remain in shell history or process listings. Never attach credentials, private keys, complete environment files or raw private conversations.

`.gitignore` reduces accidental inclusion but does not remove already-tracked files, secure local data or scan public templates for secrets. Report suspected vulnerabilities through [SECURITY.md](SECURITY.md), not a public reproduction containing sensitive data.

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
