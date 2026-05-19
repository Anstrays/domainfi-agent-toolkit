# Wire Arc Testnet paid-agent status

Use this prompt with a coding agent when extending the Arc/Circle paid-agent integration. The goal is safe testnet wiring, not autonomous custody.

## Prompt

You are improving `domainfi-agent-toolkit` Arc paid-agent support. Follow these rules:

1. Retrieve and cite current official Arc and Circle docs before changing chain/payment assumptions:
   - https://docs.arc.network/llms.txt
   - https://developers.circle.com/llms.txt
2. Separate your notes into:
   - verified Arc/Circle facts,
   - repo-specific implementation choices,
   - assumptions/unknowns that need human review.
3. Preserve the safety boundary:
   - Arc Testnet only,
   - no private keys in repo, prompts, logs, config, examples, or PR text,
   - no custody, autonomous spending, or mainnet fallback,
   - real payments require human wallet approval and production Circle Gateway/x402 verification.
4. Keep the local `x402-test:<resource>:<amount>` proof demo-only. Do not describe it as real settlement.
5. If adding code, use strict TDD:
   - write a failing unittest first,
   - run the focused test and show the expected failure,
   - implement the smallest safe code,
   - run focused tests, full unittest suite, and `python3 scripts/validate_repo.py`.
6. Prefer dependency-free Python unless production wiring explicitly requires a reviewed dependency.

## Expected output

Return a compact plan or patch summary with:

- docs retrieved and citations,
- files changed,
- tests added/updated,
- exact validation commands and results,
- remaining production replacement boundary for Circle Gateway/x402.
