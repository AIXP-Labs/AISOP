# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in the AISOP protocol specification or reference implementations, please report it responsibly through GitHub's private security advisory channel:

**[Report a vulnerability on GitHub](https://github.com/AIXP-Labs/AISOP/security/advisories/new)**

This keeps the report private until a fix is released and coordinated disclosure is complete.

If that private-reporting entry is unavailable, do not post a sensitive reproduction publicly. You may open an issue that only requests a private contact route, without secrets or private logs; wait for a confirmed private channel before sending details. Availability of the GitHub feature is not guaranteed by this document.

Please include:

- Description of the vulnerability
- Steps to reproduce (if applicable)
- Potential impact assessment
- Suggested fix (if any)

## Minimize Sensitive Data

Use a synthetic, minimal reproduction and only the version and configuration details needed to explain it. Remove credentials, private keys, personal information and unrelated business data before sharing. Never attach complete environment files, authentication configuration or raw private conversations.

The reference inspection commands print program metadata and steps; `--prompt` prints the constructed prompt. Command arguments may appear in shell history or process listings. A successful static check, resolver claim or local hash does not establish trust, execute a human gate or automatically redact output. `.gitignore` does not remove files already tracked or published.

See [specification §6.2](specification/aisop-spec.md) for confirmation and audit requirements: retain which confirmation step occurred, when and its decision/selection facts; sensitive prompt or option payloads may be minimized before logging without erasing or changing those facts. This does not add an obligation to record the approver's identity. The reference libraries provide neither a confirmation UI nor an audit logger, and a passing static check does not prove either runtime guarantee.

## Response Timeline

- **Acknowledgment**: Within 48 hours
- **Initial Assessment**: Within 7 days
- **Resolution Plan**: Within 14 days

## Scope

This security policy covers:

- The AISOP protocol specification (`specification/aisop-spec.md`)
- The Python reference implementation (`reference/python/`)
- The JavaScript reference implementation (`reference/javascript/`)
- Official documentation and examples shipped in this repository

Out of scope:

- Third-party AISOP implementations (report to those projects directly)
- AIAP governance rules (report to the [AIAP-Protocol](https://github.com/AIXP-Labs/AIAP) repository)
- Runtime or host issues, including [SoulBot](https://github.com/AIXP-Labs/SoulBot) (report to the affected implementation)

## Coordinated Disclosure

We follow a coordinated disclosure process. Please do not publicly disclose vulnerabilities until a fix has been released and announced.

## Special Concern: `sys.io.confirm` Immutability

Any vulnerability that allows bypassing, weakening, or silently degrading the `sys.io.confirm` interruption guarantee is treated as **CRITICAL** regardless of other impact assessment. `sys.io.confirm` is the execution-layer guarantee of Axiom 0 and must never be bypassable.

---

Align Axiom 0: Human Sovereignty and Wellbeing. Version: AISOP V1.0.0. www.aisop.dev
