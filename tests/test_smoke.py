# tests/test_smoke.py
# Placeholder smoke test. Exists to:
# 1. Confirm pytest + PyQt6 load correctly in CI (catches libEGL-type issues)
# 2. Prevent pytest exit code 5 (no tests collected) from failing CI
# Remove or replace once real test cases are implemented (see tester session).

def test_placeholder():
    assert True
