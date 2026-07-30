"""The response envelope, and the one thing every failure path must carry.

Extracted from `server.py` for `ARCH-011`.

Every tool in this server returns `str` (`SDK-002`), so a client has no typed
field to read — which made the provenance marker load-bearing rather than
decorative. Before `OBS-001` the failure paths returned a bare German sentence
with no footer while every success ended in `_provenance: live_api_`, so the only
way to tell "the source is down" from "nothing matched" was to parse prose.

All three outcomes now carry the marker: `live_api`, `refused` (declined by
design — retrying changes nothing) and `degraded` (the source could not be
reached — the same call may work later). That distinction is the whole point;
the attribution riding along is what the licence wanted anyway.
"""

from __future__ import annotations

import json

import httpx

from .constants import (
    ATTRIBUTION,
    EgressDenied,
    GazetteFilterIgnored,
    GazetteInvalidCode,
    RubricBlocked,
)

# ---------------------------------------------------------------------------
# Output envelope
# ---------------------------------------------------------------------------


def _md(lines: list[str], provenance: str) -> str:
    """Append the mandatory attribution + provenance footer (Markdown)."""
    return "\n".join([*lines, "", "---", f"_{ATTRIBUTION}_", f"_provenance: {provenance}_"])


def _json_out(payload: dict, provenance: str) -> str:
    """Wrap a JSON payload with the mandatory attribution + provenance fields."""
    enriched = {**payload, "attribution": ATTRIBUTION, "provenance": provenance}
    return json.dumps(enriched, ensure_ascii=False, indent=2)


def _note(text: str, provenance: str) -> str:
    """A refusal or a degraded answer, wearing the same envelope as a result.

    OBS-001: every tool here returns `str`, so a client cannot tell "nothing
    matched" from "the source was unreachable" by looking at a status field —
    both come back as `isError: false` with prose inside. A successful answer
    ends in `_provenance: live_api_`; without this helper the failure paths
    ended in nothing at all, which left German prose as the only signal.

    With it, the three outcomes are one field apart rather than one sentence
    apart: `live_api`, `refused` (policy said no), `degraded` (the source could
    not be asked). The attribution comes along for free, which it should have
    been doing anyway — it is a licence condition, not a decoration.

    Markdown only, deliberately: a caller asking for `response_format='json'`
    still gets prose here, because the failure happens before the format branch
    is reached. That is pre-existing and unchanged; the footer at least makes
    the outcome greppable in both cases.
    """
    return _md([text], provenance)


def _handle_error(e: Exception) -> str:
    """Translate an exception into an actionable, human-readable message.

    The provenance split is what the caller acts on: `refused` means this server
    declined and retrying changes nothing, `degraded` means the source failed
    and the same call may well work later.
    """
    if isinstance(e, RubricBlocked):
        return _note(str(e), "refused")
    if isinstance(e, (GazetteFilterIgnored, GazetteInvalidCode)):
        return _note(str(e), "refused")
    if isinstance(e, EgressDenied):
        return _note(f"Egress verweigert: {e}. Ziel-Host nicht in ALLOWED_HOSTS.", "refused")
    if isinstance(e, httpx.HTTPStatusError):
        status = e.response.status_code
        if status == 400:
            return _note("Fehler 400: Ungültige Anfrage. Bitte Parameter prüfen.", "degraded")
        if status == 401:
            # Verified upstream behaviour: a missing `publicationStates` yields
            # 401/AccessDeniedException, NOT 400. It never means "credentials
            # required" — the read API is unauthenticated.
            return _note(
                "Fehler 401: Die Quelle hat die Anfrage abgelehnt. Das deutet auf "
                "einen fehlenden `publicationStates`-Parameter hin, nicht auf "
                "fehlende Zugangsdaten — die Lese-API ist unauthentifiziert.",
                "degraded",
            )
        if status == 404:
            return _note("Fehler 404: Publikation nicht gefunden. Bitte ID prüfen.", "degraded")
        if status == 429:
            return _note("Fehler 429: Rate-Limit überschritten. Bitte kurz warten.", "degraded")
        return _note(f"Fehler {status}: Anfrage an das Amtsblattportal fehlgeschlagen.", "degraded")
    if isinstance(e, httpx.TimeoutException):
        return _note(
            "Timeout: Das Amtsblattportal antwortet nicht. Bitte erneut versuchen.", "degraded"
        )
    if isinstance(e, httpx.ConnectError):
        return _note(
            "Verbindungsfehler: Das Amtsblattportal ist nicht erreichbar. "
            "Dies ist KEIN leeres Ergebnis — es konnten keine Daten abgefragt werden.",
            "degraded",
        )
    return _note(f"Unerwarteter Fehler: {type(e).__name__}: {e}", "degraded")


# ---------------------------------------------------------------------------
