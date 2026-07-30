"""ARCH-003: what an empty gazette search says, and what it offers instead.

The check asks four things: a fuzzy **or suggestion** mechanism on non-sensitive
search tools, a `match_type` on every response, an actionable hint when it is
`none`, and exact-only lookups on sensitive tools with the decision documented.

**A correction, because the first attempt at this got it wrong.** Version 0.20.0
declined the first criterion on the grounds that every search here queries
bankruptcy notices, debt-collection summonses, estate calls and construction
objections — so widening could name the wrong company as bankrupt. Every rubric
in that list is **red** and unreachable through any tool: `KK`, `SB`, `SR`,
`LS`, `NA`, `ES`, `TE-*`, `GB-*`, `GE-*` and `BP-*` all sit outside
`GREEN_RUBRICS`, and that allow-list exists precisely to exclude systematic
natural-person data. The searchable set is therefore the *non-sensitive* one —
the set criterion 1 applies to, not the set criterion 4 exempts. The exception
being invoked covered rubrics this server refuses to serve.

**What is true is narrower.** `HR` / `BH` (Handelsregister) and `OB-*`
(Beschaffungen) name legal persons, so silently re-running a search with a
broadened company name would return notices about *different* companies and
present them as the answer. That is an argument about how to widen, not a reason
to leave a caller with nothing.

So this module suggests terms and never searches for them. `suggest_terms`
returns shorter forms of the caller's *own* keyword; the model decides whether
to try one. Nothing is fetched, nothing is re-queried, and no result can be
attributed to a term the caller did not choose — which is the whole hazard the
0.20.0 decision was reaching for, kept while the criterion is actually met.
"""

from __future__ import annotations

from typing import Literal

# Still no "fuzzy" member, and now for the right reason: the server never
# *performs* a widened search, so no response is ever a fuzzy match. Suggestions
# ride in the note as candidate terms. Anyone adding this member is switching
# from offering to executing, and has to come here and read that difference.
MatchType = Literal["exact", "none"]

# Below this a prefix stops narrowing anything — three characters match half the
# gazette, and a suggestion that returns noise is worse than none.
MIN_TERM_LENGTH = 4

# Three candidates is enough to get from a full German compound to its head.
MAX_SUGGESTIONS = 3

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


def suggest_terms(keyword: object) -> list[str]:
    """Shorter forms of the caller's own keyword, offered and never searched.

    Criterion 1 asks for a fuzzy match *or* a suggestion mechanism. This is the
    second, and the distinction is the entire safety argument: the server hands
    back candidate terms, the model chooses. No request is issued for any of
    them, so no notice about a different company can ever be presented as the
    answer to the original question.

    Only prefixes of what the caller typed. German compounds put the head at the
    front and the upstream matches substrings, so `Schulhausneubau` ⊃
    `Schulhaus` ⊃ `Schul`, each matching a superset of the last. No stemmer and
    no dictionary: those would invent a term the caller never used, and this
    server does not model German.

    Multi-word queries suggest their longest token first — "mobile Metallbauten"
    is asking about Metallbauten — then prefixes of that token.
    """
    if not isinstance(keyword, str):
        return []
    keyword = keyword.strip()
    if not keyword:
        return []

    seen = {keyword.casefold()}
    out: list[str] = []

    def _add(term: str) -> None:
        if len(term) < MIN_TERM_LENGTH or term.casefold() in seen:
            return
        seen.add(term.casefold())
        out.append(term)

    tokens = keyword.split()
    if len(tokens) > 1:
        for token in sorted(tokens, key=len, reverse=True):
            _add(token)
            if len(out) >= MAX_SUGGESTIONS:
                return out

    head = max(tokens, key=len) if tokens else keyword
    for length in _prefix_lengths(len(head)):
        _add(head[:length])
        if len(out) >= MAX_SUGGESTIONS:
            break
    return out


def _prefix_lengths(full: int) -> list[int]:
    """Prefix lengths to offer, longest first, ending at `MIN_TERM_LENGTH`.

    Spaced geometrically to the floor rather than by a fixed ratio, so the last
    suggestion is always the broadest one however long the input was. The
    companion server measured a fixed 30%-per-step schedule against the live API
    and found it wrong: from "Betonsanierungsarbeiten" it stopped at seven
    characters, three short of the term that actually returns results. The last
    suggestion has to be an actual last resort.
    """
    if full <= MIN_TERM_LENGTH:
        return []
    ratio = (MIN_TERM_LENGTH / full) ** (1 / MAX_SUGGESTIONS)
    lengths: list[int] = []
    length = full
    for _ in range(MAX_SUGGESTIONS):
        length = max(MIN_TERM_LENGTH, int(length * ratio))
        if length < full and length not in lengths:
            lengths.append(length)
    return lengths


def suggestion_sentence(keyword: object) -> str:
    """The suggestions as one sentence, or empty when there are none.

    Empty for a short or absent keyword rather than padded with something
    useless — a note that always has a suggestions clause trains the reader to
    skip it.
    """
    terms = suggest_terms(keyword)
    if not terms:
        return ""
    listed = ", ".join(f"«{t}»" for t in terms)
    return (
        f" Kürzere Varianten des Suchbegriffs, die einen Treffer haben könnten: "
        f"{listed} — **nicht** automatisch abgefragt, bewusst zur Auswahl."
    )


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

    Ahead of all three, when the caller gave a keyword, come the suggested
    shorter forms of it — criterion 1. They are stated as *not* automatically
    queried, because the difference between offering a term and having searched
    for it is the difference between a suggestion and a result the caller never
    asked for.
    """
    return (
        f"Keine Treffer für {describe_filters(**filters)}."
        f"{suggestion_sentence(filters.get('keyword'))} "
        "Die Suche selbst wurde **nicht** automatisch erweitert: bei "
        "Handelsregister- und Beschaffungsmeldungen liefert ein breiterer "
        "Firmenname Meldungen zu anderen Firmen, die wie eine Antwort aussehen. "
        "Deshalb Vorschläge statt stiller Erweiterung — die Auswahl bleibt beim "
        "Aufrufer. "
        "Weitere Schritte: "
        "`gazette_list_rubrics(rubric_class='all')` zeigt, ob die passende "
        "Rubrik hier bewusst nicht erschlossen ist — dann fehlt der Treffer "
        "wegen des Scope-Entscheids und nicht, weil es die Publikation nicht "
        "gibt. `gazette_source_status` prüft, ob die Quelle gerade gestört ist; "
        "eine Störung sieht von hier aus genau gleich aus wie ein leeres "
        "Ergebnis. Sonst Zeitraum erweitern oder das Stichwort weglassen."
    )
