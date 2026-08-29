# Security Policy

## Supported Versions

GhostRun actively supports security updates for the current major release:

| Version | Supported          |
| ------- | ------------------ |
| 2.0.x   | :white_check_mark: |
| < 2.0.0 | :x:                |

## Reporting a Vulnerability

We take the security and privacy of AI testing and prompt workflows very seriously. GhostRun operates local-first, meaning no data leaves your infrastructure by default.

If you discover a security vulnerability within GhostRun (such as a prompt injection bypass in the judge runner, transport leak in interceptors, or unsafe deserialization):

1. **Do not create a public GitHub issue.**
2. Email your findings directly to **security@parthmax.tech** or open a private security advisory via [GitHub Security Advisories](https://github.com/parthmax2/ghostrun/security/advisories/new).
3. Include detailed reproduction steps, Python version, OS, and sample payload.

We will acknowledge receipt within 24 hours and provide a patch timeline within 3 business days.
