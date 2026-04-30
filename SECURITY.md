# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in the AISOP protocol specification or reference implementations, please report it responsibly through GitHub's private security advisory channel:

**[Report a vulnerability on GitHub](https://github.com/AIXP-Labs/AISOP/security/advisories/new)**

This keeps the report private until a fix is released and coordinated disclosure is complete.

Please include:

- Description of the vulnerability
- Steps to reproduce (if applicable)
- Potential impact assessment
- Suggested fix (if any)

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
- SoulBot runtime issues (report to the [SoulBot](https://github.com/AIXP-Labs/SoulBot) repository)

## Coordinated Disclosure

We follow a coordinated disclosure process. Please do not publicly disclose vulnerabilities until a fix has been released and announced.

## Special Concern: `sys.io.confirm` Immutability

Any vulnerability that allows bypassing, weakening, or silently degrading the `sys.io.confirm` interruption guarantee is treated as **CRITICAL** regardless of other impact assessment. `sys.io.confirm` is the execution-layer guarantee of Axiom 0 and must never be bypassable.

---

Align Axiom 0: Human Sovereignty and Wellbeing. Version: AISOP V1.0.0. www.aisop.dev
