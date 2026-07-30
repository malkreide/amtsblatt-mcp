"""The security documents must describe the server that exists, not an earlier one.

Ported from `swiss-procurement-mcp`, where this guard earned its place twice.
Once by catching real drift: `SECURITY.md` there cited counts four audit runs
stale and listed container sandboxing and structured logging as *accepted risks*
long after both had flipped to `pass`. A stale acceptance is worse than a missing
one — it reads as a considered decision when it is really an out-of-date
paragraph, and a reader auditing the server would have concluded that neither
control exists. And once by biting mid-audit: creating a run directory turned the
suite red until the posture summary was updated, so an unfinished audit announces
itself instead of lying quietly on disk.

This repo has one hazard the sister server does not: **two** security documents.
`SECURITY.de.md` is a summary rather than a full translation, so it legitimately
omits the audit bookkeeping — but every behavioural promise has to appear in
both, or a German-only reader gets a different server described to them. Version
0.20.0 made that concrete by adding an `ARCH-003` section to each file with
nothing coupling them. `test_the_german_summary_carries_every_behavioural_section`
is the reason this port was worth doing rather than copying.
"""

from __future__ import annotations

import json
import pathlib
import re
import typing

from amtsblatt_mcp._matching import MatchType
from amtsblatt_mcp.server import HTTP_TRANSPORTS

REPO = pathlib.Path(__file__).resolve().parents[1]
SECURITY = (REPO / "SECURITY.md").read_text(encoding="utf-8")
SECURITY_DE = (REPO / "SECURITY.de.md").read_text(encoding="utf-8")

# `(SEC-009)` and `(SCALE-002, SCALE-003)` both occur, so the ids are collected
# from the whole parenthesis rather than assumed to be one per heading. The
# sister server's version missed the second form because it never had one.
_HEADING_IDS = re.compile(r"^#{2,3}[^\n]*\(([A-Z]+-\d+(?:,\s*[A-Z]+-\d+)*)\)", re.M)


def _latest_audit_dir() -> pathlib.Path:
    runs = sorted(d for d in (REPO / "audits").iterdir() if d.is_dir())
    assert runs, "no audit runs on disk"
    return runs[-1]


def _heading_check_ids(doc: str) -> set[str]:
    return {cid.strip() for group in _HEADING_IDS.findall(doc) for cid in group.split(",")}


def test_cites_the_latest_audit_run() -> None:
    """A posture section quoting an old run misstates the current posture."""
    latest = _latest_audit_dir().name
    assert latest in SECURITY, (
        f"SECURITY.md does not reference the latest run {latest}; "
        "update the posture summary when a new audit lands"
    )


# How much prose after the run citation counts as "the sentence that cites it".
# Generous enough for a wrapped sentence, tight enough that an unrelated
# paragraph elsewhere in the posture section cannot stand in for it.
_CITATION_WINDOW = 500


def test_quoted_counts_match_that_run() -> None:
    """All three counts, anchored to the sentence that names the run.

    Two departures from the sister server's version, both found by mutating it.

    `fail` is included where that one checks only pass and partial: this server
    has six, and a posture section that quietly stops naming the fails is
    exactly the drift worth catching.

    And the search is windowed rather than document-wide. Searching the whole
    file let a *historical* sentence — "the estimate recorded at the time —
    ~32 pass / 8 partial / 6 fail" — satisfy the assertion while the actual
    posture line said something else. Changing the posture line to 31 pass left
    the suite green. The claim being guarded is that the summary states *this
    run's* numbers, so the numbers have to sit next to the run reference; a
    coincidental match twenty lines away is not the same claim.
    """
    latest = _latest_audit_dir()
    summary = json.loads((latest / "summary.json").read_text(encoding="utf-8"))
    by = summary["totals"]["by_status"]

    at = SECURITY.find(latest.name)
    assert at != -1, f"SECURITY.md does not reference {latest.name}"
    window = SECURITY[at : at + _CITATION_WINDOW]

    # `\s+` rather than a literal space: prose wraps, and the count and its
    # label legitimately end up on different lines.
    for label in ("pass", "partial", "fail"):
        assert re.search(rf"{by[label]}\s+{label}", window), (
            f"the passage citing {latest.name} does not state {by[label]} {label}"
        )


def test_does_not_accept_risks_that_are_closed() -> None:
    """The exact drift that prompted this file on the sister server.

    Anything listed under "Accepted risks" must still be open in the latest
    audit. A check that has flipped to `pass` no longer belongs there.
    """
    results = json.loads(
        (_latest_audit_dir() / "verification-results.json").read_text(encoding="utf-8")
    )["results"]
    section = SECURITY.split("## Accepted risks", 1)[1].split("\n## ", 1)[0]

    # Only the headings — prose may legitimately mention a closed check in order
    # to say that it *was* closed.
    accepted = _heading_check_ids(section)
    assert accepted, "no check ids found under Accepted risks — heading format changed?"

    wrongly_accepted = [
        cid for cid in accepted if cid in results and results[cid]["status"] == "pass"
    ]
    assert not wrongly_accepted, (
        f"listed as accepted risk but passing in the latest audit: {sorted(wrongly_accepted)}"
    )


# --- the two documents have to describe one server -------------------------


def test_the_german_summary_carries_every_behavioural_section() -> None:
    """`SECURITY.de.md` is a summary, not a translation — but not a shorter truth.

    The split it is allowed to make is structural: the German file skips the
    audit bookkeeping (measured counts, accepted risks) and carries the
    behavioural promises. So the invariant is derived rather than hand-listed —
    every check id in an English heading *except* those under "Audit posture"
    and "Accepted risks" must also head a German section.

    A curated list of "sections that must be bilingual" would rot on the first
    section nobody thought to add to it. This does not: adding an English
    section outside the bookkeeping turns the suite red until the German file
    gets one too.
    """
    bookkeeping = _heading_check_ids(SECURITY.split("## Accepted risks", 1)[1].split("\n## ", 1)[0])
    behavioural = _heading_check_ids(SECURITY) - bookkeeping
    assert behavioural, "no behavioural sections found in SECURITY.md — heading format changed?"

    missing = behavioural - _heading_check_ids(SECURITY_DE)
    assert not missing, (
        f"documented in SECURITY.md but not in SECURITY.de.md: {sorted(missing)} — "
        "a German-only reader would be told about a different server"
    )


def test_the_german_summary_invents_no_section_of_its_own() -> None:
    """The other direction, and it is not symmetric.

    German may omit bookkeeping; it may not discuss a check the English file is
    silent on. That would be a claim with no reviewed counterpart, which is how
    the two files start describing different servers from the other end.
    """
    orphans = _heading_check_ids(SECURITY_DE) - _heading_check_ids(SECURITY)
    assert not orphans, (
        f"discussed in SECURITY.de.md with no SECURITY.md counterpart: {sorted(orphans)}"
    )


# --- documented promises must match the code -------------------------------


def test_the_exact_only_promise_matches_the_code() -> None:
    """Both files promise no search ever widens. The type is what makes it true.

    If `MatchType` ever gains a `fuzzy` member, that promise becomes a false
    statement in two languages at once — and the reader most likely to rely on
    it is the one deciding whether this server can be pointed at a bankruptcy
    notice. Coupled to the code rather than to prose about the code.
    """
    exact_only = "fuzzy" not in typing.get_args(MatchType)
    for name, doc in (("SECURITY.md", SECURITY), ("SECURITY.de.md", SECURITY_DE)):
        assert ("ARCH-003" in doc) == exact_only, (
            f"{name} documents the exact-only decision but MatchType allows fuzzy "
            f"(or the reverse) — one of the two has moved without the other"
        )


def test_the_gateway_advice_covers_every_http_transport() -> None:
    """Found by writing this file, and stale in both languages.

    Hardening note 1 told operators to put a gateway in front of "the SSE
    transport". Since 0.18.0 the default is streamable-http on `/mcp`, so an
    operator on the default read advice that appeared not to apply to them — and
    the bearer auth and rate limit are single-instance on *both* paths. The
    advice was right and its scope was wrong, which is the failure mode that
    survives review longest.

    Scoped to the hardening section on purpose. The first version of this test
    searched the whole document and failed on the accepted-risks paragraph, where
    "the legacy SSE transport" is the correct and specific subject. What is wrong
    is *advice* narrowed to one transport, not any mention of SSE — a guard that
    cannot tell those apart would push the prose toward being vaguer than the
    facts.
    """
    if len(HTTP_TRANSPORTS) <= 1:
        return
    sections = (
        ("SECURITY.md", SECURITY, "## Hardening Notes for Operators"),
        ("SECURITY.de.md", SECURITY_DE, "## Härtungshinweise für Betreiber"),
    )
    for name, doc, heading in sections:
        assert heading in doc, f"{name} has no {heading!r} section — heading renamed?"
        section = doc.split(heading, 1)[1].split("\n## ", 1)[0]
        for stale in ("in front of the SSE transport", "vor den SSE-Transport"):
            assert stale not in section, (
                f"{name} scopes operator advice to SSE while the server serves "
                f"{sorted(HTTP_TRANSPORTS)} — name the HTTP transports, not one of them"
            )
