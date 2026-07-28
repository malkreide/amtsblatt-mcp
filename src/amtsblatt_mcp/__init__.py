"""amtsblatt-mcp — MCP server for amtsblattportal.ch (SHAB + cantonal gazettes).

Procurement and official notices from the Swiss gazette portal. Rubrics
carrying systematic natural-person data are excluded by design; see
:mod:`amtsblatt_mcp.rubrics`.
"""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version

try:
    # Single source of truth: the version declared in pyproject.toml. Three
    # hardcoded literals had drifted apart (0.1.3 here, 0.1.2 in _otel.py,
    # 0.4.0 in server.py), which meant OpenTelemetry reported a service
    # version three releases behind the actual one.
    __version__ = _pkg_version("amtsblatt-mcp")
except PackageNotFoundError:  # running from a source tree without an install
    __version__ = "0.0.0+unknown"
