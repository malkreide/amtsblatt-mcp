# Contributing to amtsblatt-mcp

[🇩🇪 Deutsche Version](CONTRIBUTING.de.md)

Thank you for your interest in contributing! This server is part of the [Swiss Public Data MCP Portfolio](https://github.com/malkreide).

## Reporting Issues

Open a GitHub issue with the tool call, the parameters, and what you expected.
For anything touching the rubric allow-list, read
[SECURITY.md](SECURITY.md) first — some of those belong in a private advisory.

## Pull Requests

1. Fork and branch from `main`.
2. `pip install -e ".[dev]"`
3. Make the change.
4. `PYTHONPATH=src pytest tests/ -m "not live"` — all green.
5. `ruff check src/ tests/` — clean.
6. Use [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`,
   `fix:`, `docs:`, `refactor:`, `test:`, `chore:`).

## Changing the rubric allow-list

**This is the one change that needs more than a passing test suite.**

`src/amtsblatt_mcp/rubrics.py` decides what personal data an AI agent can
systematically query. Releasing a rubric is a data-protection decision, not a
feature. A PR that touches `GREEN_RUBRICS` or `GREEN_SUB_RUBRICS` must:

- Name the rubric code and its German title from the live taxonomy.
- State what kind of person appears in it, and in what role. "Institutional"
  is a conclusion, not evidence — cite an actual publication's structure.
- Update [`docs/rubric-classification.md`](docs/rubric-classification.md) in the
  same commit.
- Keep the set **literal**. Never introduce prefix or glob matching; a glob
  auto-greens future upstream rubrics without review, which is precisely what
  the fail-closed rule forbids. `test_green_set_is_literal_codes_not_globs`
  enforces this.

When the upstream taxonomy grows, `test_every_live_rubric_is_explicitly_classified`
fails. That is intentional: the new rubric is already blocked, and the failing
test is the prompt to classify it deliberately rather than leave it on the
implicit default.

## Code Style

- Python 3.11+, type hints required.
- Ruff, line length 100.
- Follow the existing FastMCP / Pydantic v2 patterns in `server.py`: one
  Pydantic input model per tool, German docstrings in Google style, tools return
  `str` and never raise — errors come back as explanatory messages.
- New tools need tests. Tools that touch rubrics need allow-list tests.

## Testing conventions

- `respx` mocks httpx; fixtures live in `tests/fixtures.py` as Python literals.
- Tools are invoked directly (`await gazette_search_publications(SearchInput(...))`),
  not through an MCP client.
- Assert on the outgoing query with `route.calls[0].request.url.params`.
- For anything blocked, assert `route.call_count == 0` — the point is that no
  request was made, not merely that no data came back.
- Live tests carry `@pytest.mark.live` and are excluded in CI.
- Fixtures must contain **no real personal data**, consistently anonymised.

## Data Sources

**No-Auth-First:** this server targets the freely accessible read API of
amtsblattportal.ch. Features requiring credentials (publishing, retrieving
unpublished records) are out of scope.

## License

By contributing you agree that your contributions are licensed under the MIT
License of this project.
