# Security Policy

## Current status

DomainFi Agent Toolkit is currently a static project page and early prototype plan. It does **not** contain backend code, smart contracts, private keys, wallet integrations, or production Doma API credentials.

The local validation script is best-effort. It checks for common accidental secrets and unsafe static-site patterns, but it should not be treated as a replacement for dedicated tools such as GitHub secret scanning, gitleaks, or trufflehog.

## Supported versions

| Version | Supported |
| --- | --- |
| Proposal / prototype | Yes |

## Reporting a vulnerability

If you find a security issue in this repository, please open a private GitHub security advisory or contact the maintainer directly.

Please include:

- affected file or component
- impact
- reproduction steps
- suggested fix, if known

## Security principles for future development

Future Doma integrations should follow these rules:

- never commit API keys, private keys, seed phrases, OAuth tokens, bot tokens, or webhook secrets
- load credentials only from environment variables or secret managers
- treat all marketplace/domain data as untrusted input
- validate user-provided domain filters, URLs, wallet addresses, and notification targets
- avoid shell execution; if needed, use argument arrays rather than string interpolation
- use parameterized queries for storage layers
- redact secrets and wallet addresses in logs where possible
- add rate limits and retry bounds to monitoring jobs
- keep agent prompts and tool outputs separated from executable commands
- require explicit confirmation before any action that spends funds, transfers domains, lists assets, or changes ownership state

## Static site notes

The current GitHub Pages site is static HTML/CSS with no JavaScript, no forms, no cookies, and no third-party analytics. External links use `rel="noopener noreferrer"`.
