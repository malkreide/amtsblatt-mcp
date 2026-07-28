"""ARCH-005: the API key is held as SecretStr and does not leak into strings.

The 2026-07-27 re-audit graded ARCH-005 down from `pass` to `partial`: the key
was held as a plain `str`, so any `f"{config}"`, `repr()` or accidental log of
the surrounding object would have printed it in clear text.

These tests pin the property rather than the implementation: whatever holds the
key, formatting it must not reveal it.
"""

from __future__ import annotations

import pytest
from pydantic import SecretStr

from amtsblatt_mcp._middleware import BearerAuthMiddleware

KEY = "s3cr3t-not-a-real-key-0123456789abcdef"


async def _noop_app(scope, receive, send):  # pragma: no cover - never called
    raise AssertionError("downstream app must not run for a rejected request")


def test_secretstr_hides_the_value_in_str_and_repr() -> None:
    wrapped = SecretStr(KEY)
    assert KEY not in str(wrapped)
    assert KEY not in repr(wrapped)
    assert KEY not in f"{wrapped}"
    assert wrapped.get_secret_value() == KEY


def test_middleware_instance_does_not_expose_the_key_when_formatted() -> None:
    mw = BearerAuthMiddleware(_noop_app, SecretStr(KEY))
    assert KEY not in repr(mw)
    assert KEY not in str(mw.__dict__.get("app", ""))


def test_middleware_rejects_a_bare_str_key() -> None:
    """A plain str is exactly the regression this check exists to prevent."""
    with pytest.raises(TypeError, match="SecretStr"):
        BearerAuthMiddleware(_noop_app, KEY)


def test_middleware_still_rejects_an_empty_key() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        BearerAuthMiddleware(_noop_app, SecretStr(""))


async def test_auth_still_works_end_to_end() -> None:
    """Wrapping must not break the comparison it protects."""
    seen: list[int] = []

    async def send(message):
        if message["type"] == "http.response.start":
            seen.append(message["status"])

    async def downstream(scope, receive, send):
        seen.append(200)

    mw = BearerAuthMiddleware(downstream, SecretStr(KEY))
    scope_ok = {"type": "http", "headers": [(b"authorization", f"Bearer {KEY}".encode())]}
    scope_bad = {"type": "http", "headers": [(b"authorization", b"Bearer wrong")]}

    await mw(scope_ok, None, send)
    await mw(scope_bad, None, send)

    assert seen == [200, 401]


def test_env_example_ships_a_placeholder_not_a_key() -> None:
    """The file exists for ARCH-005 — it must never accumulate a real value."""
    import pathlib

    example = pathlib.Path(__file__).resolve().parents[1] / ".env.example"
    assert example.is_file(), ".env.example is required by ARCH-005"
    text = example.read_text(encoding="utf-8")
    assert "MCP_API_KEY=" in text
    line = next(ln for ln in text.splitlines() if ln.startswith("MCP_API_KEY="))
    value = line.split("=", 1)[1]
    assert "replace-me" in value, f"placeholder looks like a real value: {value!r}"
