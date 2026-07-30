"""Shared fixtures.

The autouse fixture here exists because of SDK-001. A single pooled
`httpx.AsyncClient` is shared across tool calls — which is the point — but the
pool binds to the event loop that created it, and pytest-asyncio gives each test
its own loop. A client created in one test and reused in the next raises
`RuntimeError: Event loop is closed` on first use.

That failure only surfaces for tests which actually open a connection, so the
respx-mocked suite never saw it and the live tests failed immediately. Resetting
around every test costs nothing (the client is rebuilt lazily on first use) and
removes a whole class of order-dependent failure.

It also keeps state from leaking between tests: the rubrics cache and the
connection pool are both process-wide.
"""

from __future__ import annotations

import pytest

from amtsblatt_mcp import _http as _server


@pytest.fixture(autouse=True)
def fresh_shared_client():
    _server._reset_client()
    yield
    _server._reset_client()
