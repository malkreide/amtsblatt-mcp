"""ARCH-003: what an empty gazette search says, and why it never widens.

The check asks that empty search results carry a `match_type`, that `none`
comes with an actionable hint, and that any tool which deliberately stays
exact-only says so. It also asks for a fuzzy or suggestion mechanism on the
*non-sensitive* search tools. This server has none, and that is the finding's
fourth criterion rather than a gap in it.

**Nothing here widens a search term.** Every search tool in this server queries
official gazette publications: bankruptcy notices, debt-collection summonses,
estate calls, construction objections. A keyword search broadened from
`Muster AG` to `Muster` returns notices about *different legal persons*, and a
model that cannot see the term was changed under it will report them as though
they answered the question. The failure mode is naming the wrong company as
bankrupt. There is no widening strategy careful enough to be worth that, and
"no publication matched" is a legitimate, actionable answer.

What an empty result gets instead is an honest account of why it might be
empty. That matters more here than a fuzzy match would, because this server has
a scope gate no caller can see from the outside: searches run against the
green rubrics only, so a keyword that genuinely appears in the gazette can come
back empty purely because its rubric is deliberately not served. An empty
result that does not say so reads as "no such publication exists", which is a
different and false claim.
"""

from __future__ import annotations

from typing import Literal

# No "fuzzy" member, deliberately. The type is the smallest place where the
# exact-only decision is visible in the code, and adding the member is the
# first thing anyone implementing widening would have to do — at which point
# they have to come here and read why it is absent.
MatchType = Literal["exact", "none"]

# The filter fields worth naming back to the caller. Ordered as a human would
# describe the search, not as the upstream query builds it.
_FILTER_LABELS: tuple[tuple[str, str], ...] = (
    ("keyword", "Stichwort"),
    ("rubric", "Rubrik"),
    ("sub_rubric", "Subrubrik"),
    ("canton", "Kanton"),
    ("date_start", "ab"),
    ("date_end", "bis"),
)


def match_type(count: int) -> MatchType:
    """`exact` when the filters matched something, `none` when they did not.

    There is no third case: a hit is a hit on the terms the caller gave, since
    nothing here rewrites them.
    """
    return "exact" if count else "none"


def describe_filters(**filters: object) -> str:
    """The applied filters, in one line, so a retry is not the same search.

    A caller told only "no results" will often retry with the same parameters
    in a different shape. Naming what was actually sent upstream — including
    the defaults the caller never typed — is what makes the next attempt
    different from the last one.
    """
    parts = [f"{label}: «{filters[key]}»" for key, label in _FILTER_LABELS if filters.get(key)]
    return ", ".join(parts) if parts else "keine Filter ausser dem Zeitraum-Standard"


def empty_note(**filters: object) -> str:
    """ARCH-003 criterion 3: an empty result has to be actionable.

    Three moves, in the order they are worth trying, and each one is a real
    possibility rather than a suggestion to try harder:

    1. The rubric may be deliberately unserved — this server's own doing, and
       invisible from the outside.
    2. The upstream may be degraded — indistinguishable from an empty result
       at this layer.
    3. The filters may be too narrow — the ordinary case, listed last because
       it is the one a caller will already have thought of.

    The note also states that the search was not widened. Without that line the
    absence of a fuzzy match reads as a missing feature, and the next person to
    touch this file adds one.
    """
    return (
        f"Keine Treffer für {describe_filters(**filters)}. "
        "Die Suche wurde **nicht** automatisch erweitert — bei Amtsblatt-"
        "Publikationen würde ein breiterer Begriff Meldungen zu anderen "
        "Personen oder Firmen liefern, die wie eine Antwort aussehen. "
        "Nächste Schritte: "
        "`gazette_list_rubrics(rubric_class='all')` zeigt, ob die passende "
        "Rubrik hier bewusst nicht erschlossen ist — dann fehlt der Treffer "
        "wegen des Scope-Entscheids und nicht, weil es die Publikation nicht "
        "gibt. `gazette_source_status` prüft, ob die Quelle gerade gestört ist; "
        "eine Störung sieht von hier aus genau gleich aus wie ein leeres "
        "Ergebnis. Sonst Zeitraum erweitern oder das Stichwort weglassen."
    )
