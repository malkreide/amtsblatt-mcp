"""SEC-022: a fingerprint of the tool surface, so a rug pull cannot be silent.

The attack this defends against is bait-and-switch. A server ships harmless tool
descriptions, the user approves them, and a later release quietly rewrites a
description to carry instructions the model then follows. Nothing in the MCP
protocol makes that visible — `tools/list` simply returns different text.

The host-side mitigation is hash pinning: record the definitions at approval
time, compare on every later listing, prompt on change. That half is not ours to
build. The **server-side** half is: publish a fingerprint of the tool surface
with every release, so a host — or a reviewer, or a diff — can see that it moved.

What is hashed is the part a model reads and acts on: the name, the description,
the input and output schemas, and the behavioural annotations. Not the title,
not the icons, not `meta` — those are presentation. A change to any hashed field
is a change to what the model will do, and therefore worth a re-approval prompt.

The committed snapshot is checked against the live server by
`tests/test_tool_hashes.py`. That is the part that makes this real rather than
ceremonial: regenerating the file becomes something CI *requires*, not something
a maintainer is supposed to remember.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

# Bumped when the canonicalisation below changes, so an old snapshot is
# recognised as incomparable rather than silently mismatching. Without it, a
# change to *how* we hash would look exactly like a change to *what* we hash.
SNAPSHOT_VERSION = 1

# The fields a client's model actually reads or is bound by. `title` and `icons`
# are presentation; `meta` is transport bookkeeping. Including them would make
# the hash churn on changes that cannot alter behaviour, and a fingerprint that
# cries wolf gets ignored.
HASHED_FIELDS = ("name", "description", "input_schema", "output_schema", "annotations")


def _canonical(tool: Any) -> str:
    """Render one tool to a stable string.

    `sort_keys` throughout: dict ordering in a JSON Schema is an artefact of how
    Pydantic walked the model, and a hash that changes when an unrelated field is
    reordered would be worse than no hash at all.
    """
    payload: dict[str, Any] = {}
    for field in HASHED_FIELDS:
        value = getattr(tool, field, None)
        if value is None:
            continue
        if hasattr(value, "model_dump"):
            value = value.model_dump(exclude_none=True, mode="json")
        payload[field] = value
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def tool_hash(tool: Any) -> str:
    return hashlib.sha256(_canonical(tool).encode("utf-8")).hexdigest()


def build_snapshot(tools: list[Any], version: str) -> dict[str, Any]:
    """Build the committed fingerprint document.

    Carries the package version so a reader can tell which release a hash
    belongs to without consulting git, and a `surface` digest over the whole set
    so that *adding* or *removing* a tool changes something visible even though
    every surviving per-tool hash is unchanged.
    """
    per_tool = {t.name: tool_hash(t) for t in sorted(tools, key=lambda t: t.name)}
    surface = hashlib.sha256(
        json.dumps(per_tool, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "snapshot_version": SNAPSHOT_VERSION,
        "package_version": version,
        "hashed_fields": list(HASHED_FIELDS),
        "surface_sha256": surface,
        "tools": per_tool,
    }
