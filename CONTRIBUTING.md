# Contributing

Thanks for your interest in DomainFi Agent Toolkit.

## Current project stage

This repository is in early proposal/prototype mode. The best contributions right now are:

- Doma integration research
- use-case feedback
- architecture suggestions
- security review
- small developer templates
- documentation improvements

## Security expectations

Do not submit secrets, tokens, private keys, wallet seed phrases, or production credentials in issues, pull requests, examples, screenshots, or logs.

Future code contributions should:

- validate untrusted input
- avoid unsafe shell execution
- keep state-changing actions behind explicit user confirmation
- use environment variables for credentials
- include clear setup instructions

## Development workflow

1. Fork the repository.
2. Create a feature branch.
3. Keep changes small and focused.
4. Update documentation when behavior changes.
5. Run the validation workflow locally where possible.

## Commit style

Use clear, practical commit messages:

```text
Add architecture notes
Add Telegram alert template
Document Doma data adapter plan
```
