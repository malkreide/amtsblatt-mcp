## Finding: OPS-001 — Test-Strategie: Unit-Tests mocked + Live-Tests gemarkert

**Severity:** high
**Status:** open
**Server:** amtsblatt-mcp
**Check-Reference:** OPS-001
**Category:** OPS
**Audit-Run:** 2026-07-28T062517-Z-amtsblatt-mcp

### Observed Behavior

Check status: **fail** (3 evidence points collected).

- respx used for HTTP mocking
- live marker registered (pyproject.toml:71)
- CI runs pytest -m 'not live' (ci.yml:31)

### Expected Behavior

All pass criteria of OPS-001 satisfied. See `checks/OPS-001` in the mcp-audit catalogue
(catalog_hash 091f446b27965044ce658a1d5f4b2cabe2b0ab5661dcc1a53b6be8f1f2e093c0).

### Evidence / Gaps

- gazette_list_rubrics has only 2 unit tests, below the 5 floor
- Only 3 of 6 tools have a live test — gazette_search_detailed, gazette_get_publication and gazette_list_rubrics have none
- No tests/test_live.py; live tests are scattered across test_search.py and test_publication.py
- No separate nightly or manual live-test workflow

### Evaluator Notes

The sister server closed this finding; the fix was never ported here.

### Effort Estimate

M
