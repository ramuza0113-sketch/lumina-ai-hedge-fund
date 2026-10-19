# Security Policy

## Supported Versions

We actively provide security updates and patches for the following versions of **Lumina Capital**:

| Version | Supported          |
| :------ | :----------------- |
| 6.x     | :white_check_mark: |
| < 6.0   | :x:                |

---

## Reporting a Vulnerability

The Lumina Capital team takes security and user safety seriously, particularly regarding API credential handling and quantitative simulation safeguards.

If you discover a security vulnerability, **please do not disclose it publicly in a GitHub issue, discussion, or pull request.**

### How to Report Privately:
1. Please report sensitive security vulnerabilities by opening a private advisory via GitHub's [Security Advisory tab](https://github.com/ramuza0113-sketch/lumina-ai-hedge-fund/security/advisories/new) or by contacting the project maintainer directly on X (Twitter) at [@prompter_note](https://x.com/prompter_note).
2. Include the following details:
   - A description of the vulnerability and its potential impact.
   - Step-by-step instructions or proof-of-concept code to reproduce the issue.
   - Suggested mitigations or fixes, if available.
3. You will receive an initial response acknowledging your report within 48 hours.

---

## Best Practices for Users & Contributors

1. **API Keys & Secrets**:
   - Never commit your `.env` file or hardcode API keys (`GEMINI_API_KEY`, `OPENAI_API_KEY`, `X_API_KEY`, broker credentials) into source code.
   - Use the provided `.env.example` template and verify that `.env` is listed in your `.gitignore`.
2. **Broker Integration Safety**:
   - Live broker adapters (e.g., Interactive Brokers) must remain disabled or set to paper trading mode unless you explicitly verify order execution boundaries.
   - Always verify risk limits (`MAX_POSITION_SIZE`, ATR stop-loss floor) before enabling automated order routing.
