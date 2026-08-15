#!/usr/bin/env python3
"""Zeichnet je eine echte Antwort pro Abfrage auf.

Warum nicht von Hand geschrieben: eine handgeschriebene Erfolgs-Antwort stimmt
mit dem ueberein, was ihr Autor annahm, und kann die Quelle deshalb nicht
widerlegen. Aufgezeichnet wird darum an demselben Ort, an dem der Server die
Antwort entgegennimmt — ueber einen httpx-Response-Hook auf dem geteilten
Client aus `_http._get_client()`. Damit tragen Aufzeichnung und Betrieb
denselben User-Agent, dasselbe Timeout und dieselbe Egress-Allowlist.

## Personendaten

Das Amtsblatt-Korpus enthaelt Personendaten — Konkurse, Betreibungen,
Erbschaften, Zivilstand, Vorladungen. Dieser Server erschliesst sie nicht: die
Freigabeliste in `rubrics.py` laesst nur ausgewaehlte Rubriken durch, und das
Green-Gate greift vor *und* nach dem Abruf.

Aufgezeichnet wird ausschliesslich durch die Werkzeuge, also durch dieses Gate.
Zusaetzlich sind die **Volltexte** bewusst aus einer Beschaffungsrubrik
gewaehlt und nicht aus dem Handelsregister: eine Ausschreibung nennt
Vergabestelle und Projekt, ein HR-Detaileintrag dagegen die Organe mit Namen.
Was hier im Ordner landet, ist damit dasselbe, was Vergabestellen ohnehin
oeffentlich ausschreiben.

Die Trefferlisten stammen aus dem Handelsregister und aus der Beschaffung. Sie
fuehren Firmen und Amtsstellen, keine Privatpersonen.

## Aufruf

    PYTHONPATH=src python scripts/record_fixtures.py

Schreibt nach `tests/fixtures/` und erzeugt `tests/fixtures/PROVENANCE.md` neu.
Dateien, die kein Plan-Eintrag mehr erzeugt, werden geloescht — sonst waechst
der Ordner und der Nachweis bleibt zurueck.

`tests/fixtures.py` (die gekuerzten, anonymisierten Stubs) bleibt daneben
bestehen: es traegt die Fehlerpfade und die gesperrten Rubriken, die sich nicht
aufzeichnen lassen — der Server holt sie ja gerade nicht ab.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import sys
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL / "src"))

from amtsblatt_mcp import _http, inputs  # noqa: E402
from amtsblatt_mcp.tools import publication, rubrics, search, status  # noqa: E402

FIXTURES = WURZEL / "tests" / "fixtures"

VERSUCHE = 4

# Wie viele Trefferzeilen je Antwort bleiben. Die Form einer Zeile belegen drei
# genauso gut wie hundert; die Zahl steht je Datei im Nachweis.
ZEILEN = 3

# Aufzeichnungsstichtag. Die Quelle liefert je nach Tag andere Publikationen —
# ohne festen Zeitraum waere jede Neuaufnahme ein anderer Datensatz und der
# Diff unlesbar.
ZEITRAUM = {"date_start": "2026-08-01", "date_end": "2026-08-14"}


@dataclass(frozen=True)
class Aufruf:
    """Ein Werkzeugaufruf, der Anfragen ausloesen soll."""

    name: str
    werkzeug: str
    klasse: str
    eingabe: dict[str, Any]
    # Kuerzen ist nur dort harmlos, wo der Server die Liste ganz liest. Filtert
    # er *in* ihr, schneidet ein Schnitt auf die ersten Zeilen womoeglich genau
    # die Zeile weg, die er sucht.
    kuerzen: bool = True
    notiz: str = ""


# Die Publikations-ID fuer den Volltext-Abruf wird zur Laufzeit gesucht:
# Publikationen laufen ab, und eine fest verdrahtete UUID waere beim naechsten
# Aufzeichnen ein 404. Gesucht wird in einer Beschaffungsrubrik — siehe oben.
DETAIL_RUBRIK = "OB-TI"


def plan(publikations_id: str) -> list[Aufruf]:
    return [
        Aufruf(
            "rubrics",
            "gazette_list_rubrics",
            "RubricsInput",
            {"rubric_class": "all"},
            kuerzen=False,
            notiz="Ungekuerzt: der Server klassiert jede Rubrik gegen die "
            "Freigabeliste. Auf die ersten Zeilen geschnitten faenden die "
            "gruenen Rubriken sich selbst nicht mehr.",
        ),
        Aufruf(
            "search_hr",
            "gazette_search_publications",
            "SearchInput",
            {"rubric": "HR", "limit": 5, **ZEITRAUM},
            notiz="Trefferliste Handelsregister — Firmen und Amtsstellen, keine Privatpersonen.",
        ),
        Aufruf(
            "search_keyword",
            "gazette_search_publications",
            "SearchInput",
            {"keyword": "Informatik", "limit": 5, **ZEITRAUM},
        ),
        Aufruf(
            "search_procurement",
            "gazette_search_procurement",
            "ProcurementInput",
            {"canton": "TI", "limit": 5, **ZEITRAUM},
        ),
        Aufruf(
            "search_detailed",
            "gazette_search_detailed",
            "DetailedSearchInput",
            {"rubric": DETAIL_RUBRIK, "limit": 2, **ZEITRAUM},
            notiz="Suche plus Volltexte in einem Aufruf. Bewusst eine "
            "Beschaffungsrubrik: ein HR-Detaileintrag nennt die Organe mit Namen.",
        ),
        Aufruf(
            "publication",
            "gazette_get_publication",
            "PublicationInput",
            {"id": publikations_id},
            notiz="Volltext einer Ausschreibung — Vergabestelle und Projekt.",
        ),
        Aufruf("status", "gazette_source_status", "StatusInput", {}),
    ]


@dataclass
class Antwort:
    """Eine gesehene Antwort samt der Anfrage, die sie ausgeloest hat."""

    url: str
    text: str
    werkzeuge: list[str] = field(default_factory=list)
    darf_kuerzen: bool = True
    dateiname: str = ""
    original_bytes: int = 0
    gekuerzt_von: int = 0
    behalten: int = 0
    sha256: str = ""
    bytes: int = 0

    @property
    def schluessel(self) -> str:
        """Woran eine Anfrage beim Abspielen wiedererkannt wird."""
        return self.url


def _endung(text: str) -> str:
    """`.json`, wenn die Antwort JSON ist — sonst `.xml`.

    Die Volltexte kommen als XML. Eine solche Datei `.json` zu nennen waere
    eine Behauptung ueber ihren Inhalt, die nicht stimmt.
    """
    try:
        json.loads(text)
    except json.JSONDecodeError:
        return ".xml"
    return ".json"


def _hook_fuer(gesehen: list[Antwort]) -> Callable[[httpx.Response], Awaitable[None]]:
    """Baut den Response-Hook fuer einen Versuch.

    Eigene Funktion, damit die Liste als Argument gebunden ist und nicht als
    Schleifenvariable aus dem umgebenden Namensraum (ruff B023).
    """

    async def hook(response: httpx.Response) -> None:
        await response.aread()
        gesehen.append(Antwort(url=str(response.request.url), text=response.text))

    return hook


_MODULE = (publication, rubrics, search, status)


def _werkzeug(name: str) -> Any:
    for modul in _MODULE:
        if hasattr(modul, name):
            return getattr(modul, name)
    raise RuntimeError(f"Werkzeug {name} nicht gefunden")


async def _fahre(a: Aufruf, client: httpx.AsyncClient) -> list[Antwort]:
    """Ruft ein Werkzeug und gibt die dabei gesehenen Antworten zurueck."""
    fn = _werkzeug(a.werkzeug)
    modell = getattr(inputs, a.klasse)(**a.eingabe)
    letzter: Exception | None = None

    for versuch in range(VERSUCHE):
        if versuch:
            await asyncio.sleep(2**versuch)
        gesehen: list[Antwort] = []
        hook = _hook_fuer(gesehen)
        client.event_hooks.setdefault("response", []).append(hook)
        try:
            ergebnis = await fn(modell)
        except Exception as e:  # noqa: BLE001 — jeder Fehler ist hier ein Retry-Grund
            letzter = e
            continue
        finally:
            client.event_hooks["response"].remove(hook)

        if "Fehler" in str(ergebnis)[:200]:
            letzter = RuntimeError(f"{a.werkzeug} meldet: {str(ergebnis)[:200]}")
            continue
        if not gesehen:
            letzter = RuntimeError(f"{a.werkzeug} hat keine Anfrage abgeschickt")
            continue
        for antwort in gesehen:
            antwort.werkzeuge.append(a.werkzeug)
            antwort.darf_kuerzen = a.kuerzen
        return gesehen

    raise RuntimeError(f"{a.name} nach {VERSUCHE} Versuchen nicht aufgezeichnet: {letzter}")


def _kuerze(daten: Any) -> tuple[int, int, Any]:
    """Kuerzt jede Liste im Baum auf `ZEILEN`; gibt (vorher, nachher, Daten).

    Nur die Zahl der Eintraege, nie ein Feld. `total` bleibt stehen: die Quelle
    meint damit die Gesamtzahl der Treffer und nicht die Zahl der gelieferten
    Zeilen, und genau die liest der Server aus.
    """
    vorher = nachher = 0

    def geh(knoten: Any) -> Any:
        nonlocal vorher, nachher
        if isinstance(knoten, dict):
            return {k: geh(v) for k, v in knoten.items()}
        if isinstance(knoten, list):
            vorher += len(knoten)
            gekuerzt = knoten[:ZEILEN]
            nachher += len(gekuerzt)
            return [geh(v) for v in gekuerzt]
        return knoten

    # Erst laufen lassen, dann die Zaehler lesen. `return vorher, nachher,
    # geh(daten)` wertet von links nach rechts aus und lieferte deshalb immer
    # (0, 0) — der Nachweis schrieb «ungekuerzt» ueber jede gekuerzte Datei.
    ergebnis = geh(daten)
    return vorher, nachher, ergebnis


async def _finde_publikation(client: httpx.AsyncClient) -> str:
    """Sucht eine aktuelle Publikation der Beschaffungsrubrik."""
    antwort = await client.get(
        f"{_http.GAZETTE_BASE}/publications",
        params={
            "publicationStates": "PUBLISHED",
            "rubrics": DETAIL_RUBRIK,
            "pageRequest.size": 1,
        },
    )
    antwort.raise_for_status()
    inhalt = antwort.json().get("content") or []
    if not inhalt:
        raise RuntimeError(f"keine Publikation in {DETAIL_RUBRIK} gefunden")
    return str(inhalt[0]["meta"]["id"])


async def main() -> int:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    heute = datetime.now(UTC).date().isoformat()
    nach_schluessel: dict[str, Antwort] = {}
    zaehler: dict[str, int] = {}

    client = _http._get_client()
    try:
        publikations_id = await _finde_publikation(client)
        print(f"Volltext-Publikation: {publikations_id}", file=sys.stderr)
        for a in plan(publikations_id):
            print(f"… {a.werkzeug} ({a.name})", file=sys.stderr)
            for antwort in await _fahre(a, client):
                if antwort.schluessel in nach_schluessel:
                    vorhanden = nach_schluessel[antwort.schluessel]
                    if a.werkzeug not in vorhanden.werkzeuge:
                        vorhanden.werkzeuge.append(a.werkzeug)
                    continue
                zaehler[a.name] = zaehler.get(a.name, 0) + 1
                antwort.dateiname = f"{a.name}_{zaehler[a.name]}{_endung(antwort.text)}"
                nach_schluessel[antwort.schluessel] = antwort
    finally:
        await _http._close_client()

    for antwort in nach_schluessel.values():
        antwort.original_bytes = len(antwort.text.encode("utf-8"))
        try:
            daten = json.loads(antwort.text)
        except json.JSONDecodeError:
            # XML bleibt, wie es kam — die Volltexte sind ohnehin klein.
            (FIXTURES / antwort.dateiname).write_text(antwort.text, encoding="utf-8")
        else:
            if antwort.darf_kuerzen:
                antwort.gekuerzt_von, antwort.behalten, daten = _kuerze(daten)
            # Neu eingerueckt geschrieben: eine Zeile JSON waere kleiner, aber
            # im Diff nicht lesbar, und ein Fixture will gelesen werden.
            (FIXTURES / antwort.dateiname).write_text(
                json.dumps(daten, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )
        roh = (FIXTURES / antwort.dateiname).read_bytes()
        antwort.sha256 = hashlib.sha256(roh).hexdigest()
        antwort.bytes = len(roh)

    antworten = sorted(nach_schluessel.values(), key=lambda x: x.dateiname)
    _schreibe_provenance(antworten, heute, publikations_id)

    # Aufraeumen: was kein Plan-Eintrag mehr erzeugt, hat auch keinen Nachweis.
    geschrieben = {a.dateiname for a in antworten} | {"PROVENANCE.md"}
    for pfad in sorted(FIXTURES.iterdir()):
        if pfad.name not in geschrieben:
            print(f"– entferne veraltet: {pfad.name}", file=sys.stderr)
            pfad.unlink()

    print(f"{len(antworten)} Aufzeichnungen in {FIXTURES}", file=sys.stderr)
    return 0


def _schreibe_provenance(antworten: list[Antwort], heute: str, publikations_id: str) -> None:
    zeilen = [
        "# Herkunft der Fixtures",
        "",
        f"Aufgezeichnet am **{heute}** mit `PYTHONPATH=src python scripts/record_fixtures.py`.",
        "",
        "Eine Antwort je **Abfrage**, nicht je Endpunkt: drei Endpunkte, aber mehrere",
        "Abfrageformen (Suche nach Rubrik, nach Stichwort, nach Beschaffungskanton;",
        "Volltext; Taxonomie; Erreichbarkeitsprobe).",
        "",
        "Die Antworten stammen aus dem geteilten Client (gleicher User-Agent, gleiches",
        "Timeout, gleiche Egress-Allowlist wie im Betrieb), abgegriffen ueber einen",
        "httpx-Response-Hook. Ausgeloest hat sie jeweils das Werkzeug selbst — und damit",
        "durch das Green-Gate.",
        "",
        "## Personendaten",
        "",
        "Das Amtsblatt-Korpus enthaelt Personendaten. Dieser Server erschliesst sie",
        "nicht, und dieser Ordner deshalb auch nicht: aufgezeichnet wurde",
        "ausschliesslich durch die Werkzeuge, also durch die Freigabeliste in",
        "`rubrics.py`.",
        "",
        "Die **Volltexte** stammen bewusst aus einer Beschaffungsrubrik und nicht aus",
        "dem Handelsregister: eine Ausschreibung nennt Vergabestelle und Projekt, ein",
        "HR-Detaileintrag dagegen die Organe mit Namen. Die Trefferlisten fuehren Firmen",
        "und Amtsstellen.",
        "",
        f"Die Publikations-ID des Volltexts (`{publikations_id}`) wird beim Aufzeichnen",
        "gesucht und nicht fest verdrahtet — Publikationen laufen ab, und eine feste",
        "UUID waere beim naechsten Lauf ein 404.",
        "",
        "## Was hier *nicht* steht",
        "",
        "`tests/fixtures.py` bleibt daneben bestehen. Es traegt die Fehlerpfade und die",
        "gesperrten Rubriken — beides laesst sich nicht aufzeichnen, weil der Server sie",
        "gerade nicht abholt, und beides ist als Erfindung in Ordnung.",
        "",
        "Neu gesetzt ist die Einrueckung; gekuerzt ist allein die **Zahl** der",
        "Listeneintraege. Kein Feld eines behaltenen Eintrags ist angetastet, und `total`",
        "steht wie geliefert — die Quelle meint damit die Gesamtzahl der Treffer.",
        "",
    ]
    for a in antworten:
        zeilen += [
            f"## `{a.dateiname}`",
            "",
            f"- **Werkzeuge:** {', '.join(f'`{w}`' for w in sorted(a.werkzeuge))}",
            f"- **Schluessel:** `{a.schluessel}`",
        ]
        if a.gekuerzt_von > a.behalten:
            zeilen.append(
                f"- **Auswahl:** {a.behalten} von {a.gekuerzt_von} Listeneintraegen "
                f"(je Liste die ersten {ZEILEN}), aus {a.original_bytes} Bytes Rohantwort"
            )
        elif not a.darf_kuerzen:
            zeilen.append(
                "- **Auswahl:** ungekuerzt — der Server filtert *in* dieser Liste, "
                "ein Schnitt auf die ersten Zeilen erfaende einen Negativbefund"
            )
        else:
            zeilen.append("- **Auswahl:** ungekuerzt")
        zeilen += [
            f"- **Groesse:** {a.bytes} Bytes",
            f"- **SHA-256:** `{a.sha256}`",
            "",
        ]
    (FIXTURES / "PROVENANCE.md").write_text("\n".join(zeilen), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
