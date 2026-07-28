"""ARCH-012: the MCP protocol version is pinned, and the pin is enforced.

The check asks for an explicit `protocolVersion` — "no latest, no default". The
SDK offers no way to configure it: negotiation happens in the session layer and
neither `FastMCP.__init__` nor `Settings` takes the parameter.

So the pin is a declared constant plus detection. This test is the enforcement
half, and it is deliberately CI-facing rather than runtime-facing: an SDK bump
should break *our* build, not the runtime of someone who upgraded `mcp`
downstream. The server itself only logs a WARNING.
"""

from __future__ import annotations

import pathlib
import re

from mcp.types import LATEST_PROTOCOL_VERSION

from amtsblatt_mcp.server import MCP_PROTOCOL_VERSION

REPO = pathlib.Path(__file__).resolve().parents[1]


def test_pin_matches_the_installed_sdk() -> None:
    """Fails when an SDK update moves the protocol version.

    When this fails, the fix is not to edit the constant blindly: read the spec
    changelog for what changed between the two versions, verify the server still
    behaves, then bump the constant, the README section and CHANGELOG together.
    """
    assert MCP_PROTOCOL_VERSION == LATEST_PROTOCOL_VERSION, (
        f"pinned {MCP_PROTOCOL_VERSION}, SDK negotiates {LATEST_PROTOCOL_VERSION}"
    )


def test_pin_is_a_dated_spec_version_not_a_moving_target() -> None:
    """"latest" or a range would defeat the purpose of pinning."""
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", MCP_PROTOCOL_VERSION), MCP_PROTOCOL_VERSION


def test_readme_documents_the_same_version() -> None:
    """A pin nobody can find is not documentation."""
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    assert "MCP Protocol Version" in readme, "README lacks the required section"
    section = readme.split("MCP Protocol Version", 1)[1][:1200]
    assert MCP_PROTOCOL_VERSION in section, (
        f"README's protocol section does not name {MCP_PROTOCOL_VERSION}"
    )


def test_readme_documents_an_update_policy() -> None:
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    section = readme.split("MCP Protocol Version", 1)[1][:2000].lower()
    assert "update" in section or "policy" in section, (
        "the protocol section states a version but no update policy"
    )
