# test-quality-guard

Prevent fake test coverage by enforcing behavior-focused tests.

## When To Use

- A large batch of tests was generated quickly (AI or scripted).
- Coverage jumped but confidence did not.
- You suspect placeholder patterns like `assert True` or status-only endpoint checks.

## Workflow

1. Run static guard:
   - `python3 scripts/check_test_quality.py`
2. Run test suite:
   - `.venv/bin/pytest -q` (or your standard project command)
3. Review any flagged tests and replace low-value assertions with behavior assertions.

## Fail Criteria

Treat the batch as blocked if any are true:

- Any tautological assertion exists (`assert True`, `assert x == x`, literal == same literal).
- Any `test_*` function has zero assertions.
- Status-code-only tests exceed the configured ratio (`--max-status-only-ratio`, default `35%`) for medium+ suites.

## Rewrite Rules

- For API tests:
  - Keep status assertions, but also assert response contract (required keys, values, ordering, side effects).
- For service/unit tests:
  - Assert state transitions and error handling paths, not only return truthiness.
- For edge-case tests:
  - Assert the exact failure mode (status code + detail or raised exception type/message).

## Quick Commands

- Baseline check: `python3 scripts/check_test_quality.py`
- Stricter run: `python3 scripts/check_test_quality.py --max-status-only-ratio 0.25`
- Alternate directory: `python3 scripts/check_test_quality.py --tests-dir integration_tests`
