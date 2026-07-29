#!/usr/bin/env python3
"""Regenerate `tool-hashes.json` (SEC-022).

Run this whenever a tool's name, description, schema or annotations change, and
name the change in `CHANGELOG.md` under "Tool Definition Changes" so a user knows
to re-approve the server.

    python scripts/update_tool_hashes.py

`tests/test_tool_hashes.py` fails until the file matches the live server, so
forgetting to run it is a red build rather than a silent drift. That is the
whole point: a fingerprint a maintainer is merely *supposed* to refresh is a
fingerprint that eventually lies.
"""

from __future__ import annotations

import asyncio
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from amtsblatt_mcp import __version__  # noqa: E402
from amtsblatt_mcp._toolhash import build_snapshot  # noqa: E402
from amtsblatt_mcp.server import mcp  # noqa: E402

TARGET = REPO / "tool-hashes.json"


def main() -> int:
    snapshot = build_snapshot(asyncio.run(mcp.list_tools()), __version__)
    new = json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n"
    old = TARGET.read_text(encoding="utf-8") if TARGET.is_file() else ""
    TARGET.write_text(new, encoding="utf-8")

    if old == new:
        print(f"{TARGET.name} unchanged ({len(snapshot['tools'])} tools)")
        return 0

    try:
        before = json.loads(old).get("tools", {}) if old else {}
    except json.JSONDecodeError:
        before = {}
    after = snapshot["tools"]
    moved = [n for n in sorted(set(before) | set(after)) if before.get(n) != after.get(n)]

    print(f"{TARGET.name} updated ({len(after)} tools)")
    if not moved:
        # Reached when only `package_version` changed. Prompting for a CHANGELOG
        # entry here would be crying wolf, and a reminder that fires on
        # non-events is one people learn to skip past.
        print("No tool definition changed — version metadata only, no CHANGELOG entry needed.")
        return 0

    for name in moved:
        if name not in before:
            print(f"  + {name} {after[name][:12]}…")
        elif name not in after:
            print(f"  - {name} (removed)")
        else:
            print(f"  ~ {name} {before[name][:12]}… -> {after[name][:12]}…")
    print("\nName the change in CHANGELOG.md under 'Tool Definition Changes'.")
    print("A changed description or annotation means clients should re-approve the server.")
    print("A removed or renamed tool is a breaking change and takes a major bump.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
