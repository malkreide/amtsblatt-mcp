"""One version, one source.

Found while writing the egress doc: `_otel.py` reported `service.version`
"0.1.2" and `__init__.py` said "0.1.3", while the package was actually 0.4.0.
Three hardcoded literals had drifted apart across three releases, so every
OpenTelemetry span carried a version that had not been current since v0.1.x.

All of them now read `importlib.metadata`, which reads `pyproject.toml`. This
test is what keeps a fourth literal from appearing.
"""

from __future__ import annotations

import json
import pathlib
import re

import amtsblatt_mcp
import amtsblatt_mcp._otel as otel
import amtsblatt_mcp.server as server


def _declared_version() -> str:
    text = (pathlib.Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(
        encoding="utf-8"
    )
    m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.M)
    assert m, "no version in pyproject.toml"
    return m.group(1)


def test_package_version_matches_pyproject() -> None:
    assert amtsblatt_mcp.__version__ == _declared_version()


def test_server_and_otel_report_the_same_version() -> None:
    declared = _declared_version()
    assert server.__version__ == declared
    assert otel._VERSION == declared


def test_no_hardcoded_version_literals_remain_in_src() -> None:
    """A new literal is the exact regression this file exists to catch."""
    src = pathlib.Path(__file__).resolve().parents[1] / "src" / "amtsblatt_mcp"
    offenders = []
    for path in src.rglob("*.py"):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not re.search(r'^\s*_?_?(VERSION|version)__?\s*=\s*"\d+\.\d+', line):
                continue
            # The documented source-tree fallback in __init__.py is the one
            # literal that is allowed to exist.
            if "+unknown" in line:
                continue
            offenders.append(f"{path.name}:{lineno}: {line.strip()}")
    assert not offenders, (
        "hardcoded version literal(s) found; read importlib.metadata instead:\n"
        + "\n".join(offenders)
    )


# --- server.json (MCP registry manifest) ----------------------------------
#
# The companion swiss-procurement-mcp hit this in production: server.json
# carried its own copy of the version, drifted, and the registry publish
# failed looking for a PyPI release that had never existed. The error reads
# like a propagation delay, so retrying looks like the fix and never is.


def _server_json() -> dict:
    path = pathlib.Path(__file__).resolve().parents[1] / "server.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_server_json_version_matches_pyproject() -> None:
    assert _server_json()["version"] == _declared_version()


def test_server_json_package_version_matches_pyproject() -> None:
    """The registry validates *this* field against PyPI, not the top-level one."""
    packages = _server_json()["packages"]
    assert packages, "server.json declares no packages"
    for pkg in packages:
        assert pkg["version"] == _declared_version(), (
            f"package {pkg.get('identifier')!r} pins {pkg['version']}, "
            f"pyproject says {_declared_version()}"
        )
