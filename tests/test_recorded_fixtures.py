"""Jedes Werkzeug, gefahren aus einer aufgezeichneten Antwort.

`tests/fixtures.py` haelt die gekuerzten, anonymisierten Stubs — die
Fehlerpfade, die leeren Trefferlisten und die gesperrten Rubriken. Die kann man
nicht aufzeichnen: der Server holt sie ja gerade nicht ab, und als Erfindung
sind sie in Ordnung. Was sie nicht koennen: die Form einer Erfolgs-Antwort
belegen. Sie stimmen mit dem ueberein, was ihr Autor annahm.

Aufgezeichnet ist deshalb eine Antwort je **Abfrage** — Suche nach Rubrik, nach
Stichwort, nach Beschaffungskanton; Volltext; Taxonomie; Erreichbarkeitsprobe.
Zugeordnet wird beim Abspielen nach der Anfrage und nicht nach der Reihenfolge:
`gazette_search_detailed` holt seine Volltexte parallel.

## Personendaten

Der Ordner enthaelt keine. Aufgezeichnet wurde ausschliesslich durch die
Werkzeuge, also durch die Freigabeliste; die Volltexte stammen bewusst aus
einer Beschaffungsrubrik. `test_keine_aufzeichnung_traegt_eine_gesperrte_rubrik`
haelt das fest — eine Aufzeichnung ist eine Datei im Repository, und was der
Server im Betrieb nicht ausliefert, hat hier erst recht nichts zu suchen.

Herkunft, Datum, Auswahlregel und SHA-256 je Datei stehen in
`tests/fixtures/PROVENANCE.md`; neu aufzeichnen mit
`PYTHONPATH=src python scripts/record_fixtures.py`.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from typing import Any

import httpx
import pytest
import respx

from amtsblatt_mcp import inputs
from amtsblatt_mcp.constants import GAZETTE_BASE
from amtsblatt_mcp.rubrics import GREEN_RUBRICS, is_green
from amtsblatt_mcp.tools import publication, rubrics, search, status
from tests.fixture_data import (
    fixture_json,
    fixture_text,
    provenance,
    recorded_names,
    recorder,
    schluesselverzeichnis,
)

ZEITRAUM = {"date_start": "2026-08-01", "date_end": "2026-08-14"}

# Werkzeug → (Modul, Eingabeklasse, Eingabe). Bewusst noch einmal
# hingeschrieben und nicht aus dem Recorder-Plan abgeleitet: die Tests sollen
# eine eigene Aussage machen. Dass beide dieselben Aufrufe fahren, prueft
# `test_der_recorder_faehrt_dieselben_aufrufe`.
WERKZEUGE: dict[str, tuple[Any, str, str, dict[str, Any]]] = {
    "rubrics": (rubrics, "gazette_list_rubrics", "RubricsInput", {"rubric_class": "all"}),
    "search_hr": (
        search,
        "gazette_search_publications",
        "SearchInput",
        {"rubric": "HR", "limit": 5, **ZEITRAUM},
    ),
    "search_keyword": (
        search,
        "gazette_search_publications",
        "SearchInput",
        {"keyword": "Informatik", "limit": 5, **ZEITRAUM},
    ),
    "search_procurement": (
        search,
        "gazette_search_procurement",
        "ProcurementInput",
        {"canton": "TI", "limit": 5, **ZEITRAUM},
    ),
    "search_detailed": (
        search,
        "gazette_search_detailed",
        "DetailedSearchInput",
        {"rubric": "OB-TI", "limit": 2, **ZEITRAUM},
    ),
    "status": (status, "gazette_source_status", "StatusInput", {}),
}

# `gazette_get_publication` steht ausserhalb der Tabelle: seine Publikations-ID
# wird beim Aufzeichnen gesucht, nicht fest verdrahtet. Der Test liest sie
# deshalb aus dem Nachweis — dieselbe Quelle, aus der auch der Dispatcher liest.
DETAIL_MODUL = (publication, "gazette_get_publication", "PublicationInput")


def _publikations_id() -> str:
    """Die aufgezeichnete Publikations-ID, gelesen aus PROVENANCE.md."""
    treffer = re.search(r"/publications/([0-9a-f-]{16,})/xml", provenance())
    assert treffer, "PROVENANCE.md nennt keinen Volltext-Abruf"
    return treffer.group(1)


@pytest.fixture
def quelle():
    """Beantwortet jede Anfrage aus ihrer eigenen Aufzeichnung und protokolliert mit.

    Nach der *Anfrage* zugeordnet, nicht nach der Reihenfolge: sonst waere
    `gazette_search_detailed` mit seinen parallelen Volltext-Abrufen ein
    Gluecksspiel und die Zuordnung im gruenen Fall zufaellig richtig. Eine
    Anfrage ohne Aufzeichnung faellt hier laut auf, statt still eine fremde
    Datei zu bekommen.
    """
    protokoll: list[httpx.Request] = []
    verzeichnis = schluesselverzeichnis()

    def antwort(request: httpx.Request) -> httpx.Response:
        protokoll.append(request)
        name = verzeichnis.get(str(request.url))
        if name is None:
            raise AssertionError(
                f"keine Aufzeichnung fuer diese Anfrage:\n  {request.url}\n"
                "Neu aufzeichnen mit `PYTHONPATH=src python scripts/record_fixtures.py`."
            )
        return httpx.Response(200, text=fixture_text(name))

    with respx.mock:
        respx.route().mock(side_effect=antwort)
        yield protokoll


async def _fahre(name: str) -> str:
    """Ruft ein Werkzeug mit der Eingabe aus der Tabelle."""
    if name == "publication":
        modul, werkzeug, klasse = DETAIL_MODUL
        eingabe: dict[str, Any] = {"id": _publikations_id()}
    else:
        modul, werkzeug, klasse, eingabe = WERKZEUGE[name]
    return await getattr(modul, werkzeug)(getattr(inputs, klasse)(**eingabe))


# --------------------------------------------------------------------------
# Herkunft
# --------------------------------------------------------------------------
def test_provenance_nennt_ein_brauchbares_aufnahmedatum():
    """Eine Aufzeichnung ohne Datum ist eine undatierte Behauptung ueber die Quelle."""
    treffer = re.search(r"Aufgezeichnet am \*\*(\d{4}-\d{2}-\d{2})\*\*", provenance())
    assert treffer, "PROVENANCE.md nennt kein Aufnahmedatum im erwarteten Format"
    wann = dt.date.fromisoformat(treffer.group(1))
    assert wann <= dt.datetime.now(dt.UTC).date(), "Aufnahmedatum liegt in der Zukunft"


def test_jede_fixture_steht_in_der_provenance():
    """Sonst waechst der Ordner und der Nachweis bleibt zurueck."""
    text = provenance()
    fehlend = [n for n in recorded_names() if f"## `{n}`" not in text]
    assert not fehlend, f"ohne Eintrag in PROVENANCE.md: {fehlend}"


def test_jeder_schluessel_zeigt_auf_eine_vorhandene_datei():
    """Der Nachweis traegt hier den Abspielbetrieb — er darf nicht ins Leere zeigen."""
    fehlend = sorted(set(schluesselverzeichnis().values()) - set(recorded_names()))
    assert not fehlend, f"im Nachweis genannt, aber nicht vorhanden: {fehlend}"


def test_keine_aufzeichnung_liegt_unbenutzt_herum():
    """Die Gegenrichtung — eine Datei, die kein Schluessel erreicht, belegt nichts."""
    ueberzaehlig = sorted(set(recorded_names()) - set(schluesselverzeichnis().values()))
    assert not ueberzaehlig, f"von keinem Schluessel erreicht: {ueberzaehlig}"


def test_der_recorder_faehrt_dieselben_aufrufe():
    """Recorder und Tests duerfen nicht auseinanderlaufen.

    Laedt `scripts/record_fixtures.py` als Modul — `main()` wird nicht gerufen,
    es geht keine Anfrage raus.
    """
    im_plan = {a.name for a in recorder().plan("00000000-0000-0000-0000-000000000000")}
    assert im_plan == set(WERKZEUGE) | {"publication"}, (
        "Recorder und Testtabelle nennen verschiedene Aufrufe"
    )


# --------------------------------------------------------------------------
# Personendaten
# --------------------------------------------------------------------------
def test_keine_aufzeichnung_traegt_eine_gesperrte_rubrik():
    """Eine Aufzeichnung ist eine Datei im Repository, kein fluechtiger Abruf.

    Was der Server im Betrieb nicht ausliefert — Konkurse, Betreibungen,
    Erbschaften, Zivilstand —, hat hier erst recht nichts zu suchen. Der
    Recorder faehrt ausschliesslich durch die Werkzeuge und damit durch das
    Green-Gate; diese Zusicherung prueft das Ergebnis statt dem Verfahren zu
    vertrauen.

    Die Taxonomie ist ausgenommen: sie *listet* die gesperrten Rubriken, damit
    der Server sie erkennen und begruendet abweisen kann — sie enthaelt aber
    keine Publikation daraus.
    """
    for name in recorded_names():
        if name.startswith("rubrics_"):
            continue
        text = fixture_text(name)
        for treffer in re.findall(r'"rubric"\s*:\s*"([A-Z0-9-]+)"', text):
            assert is_green(treffer), f"{name} traegt eine Publikation der Rubrik {treffer}"
        for treffer in re.findall(r"<rubric>([A-Z0-9-]+)</rubric>", text):
            assert is_green(treffer), f"{name} traegt eine Publikation der Rubrik {treffer}"


def test_die_volltexte_stammen_aus_der_beschaffung():
    """Nicht aus dem Handelsregister — ein HR-Detaileintrag nennt die Organe mit Namen.

    Die Trefferlisten duerfen aus HR kommen: sie fuehren Firmen und Amtsstellen.
    Der Volltext ist die Stelle, an der Personen auftauchen.
    """
    volltexte = [n for n in recorded_names() if n.endswith(".xml")]
    assert volltexte, "kein Volltext aufgezeichnet"
    for name in volltexte:
        rubrik = re.search(r"<rubric>([A-Z0-9-]+)</rubric>", fixture_text(name))
        assert rubrik, f"{name} nennt keine Rubrik"
        assert rubrik.group(1).startswith("OB-"), (
            f"{name} ist kein Beschaffungs-Volltext, sondern {rubrik.group(1)}"
        )


# --------------------------------------------------------------------------
# Der Nutzen der aufgezeichneten Taxonomie: sie merkt Drift in der Freigabeliste
# --------------------------------------------------------------------------
def test_jede_freigegebene_rubrik_gibt_es_in_der_taxonomie():
    """Die Freigabeliste ist ein Literal — die Quelle ist es nicht.

    Verschwindet ein Code upstream oder wird er umbenannt, fragt der Server
    weiter danach und bekommt eine leere Antwort: ein Negativbefund, den die
    Quelle nie gegeben hat. Genau dafuer liegt die Taxonomie ungekuerzt im
    Ordner. Stand der Aufzeichnung: alle 49 gruenen Codes vorhanden.
    """
    taxonomie = fixture_json("rubrics_1.json")
    vorhanden = {r["code"] for r in taxonomie} | {
        s["code"] for r in taxonomie for s in (r.get("subRubrics") or [])
    }
    fehlend = sorted(c for c in GREEN_RUBRICS if c not in vorhanden)
    assert not fehlend, f"freigegeben, aber upstream nicht (mehr) vorhanden: {fehlend}"


def test_die_taxonomie_ist_ungekuerzt():
    """Gekuerzt taugte sie nicht — der Server klassiert jede Rubrik gegen die Liste.

    Auf die ersten Zeilen geschnitten faende die Zusicherung darueber ihre
    eigenen Codes nicht mehr und meldete eine Drift, die es nicht gibt.
    """
    taxonomie = fixture_json("rubrics_1.json")
    assert len(taxonomie) > 100, f"nur {len(taxonomie)} Rubriken — die Datei ist gekuerzt"
    nachweis = provenance()
    block = nachweis.split("## `rubrics_1.json`", 1)[1].split("## ", 1)[0]
    assert "ungekuerzt" in block, block


# --------------------------------------------------------------------------
# Die Werkzeuge, jedes an seiner eigenen Antwort
# --------------------------------------------------------------------------
@pytest.mark.parametrize("name", sorted([*WERKZEUGE, "publication"]))
async def test_jedes_werkzeug_liest_seine_aufgezeichnete_antwort(quelle, name):
    """Der eigentliche Punkt: jede Abfrage bekommt *ihre* Antwort.

    Alle mit derselben zu bedienen hiesse, die Aufzeichnung gegen eine Abfrage
    zu halten, die sie nicht beantwortet. Der Dispatcher faellt laut, wenn eine
    Anfrage keine Aufzeichnung hat.
    """
    ergebnis = await _fahre(name)
    assert isinstance(ergebnis, str) and ergebnis.strip(), f"{name} liefert nichts"
    assert not ergebnis.lstrip().startswith("Fehler"), ergebnis[:300]
    assert quelle, f"{name} hat gar keine Anfrage abgeschickt"


async def test_die_trefferliste_traegt_titel_in_mehreren_sprachen(quelle):
    """`meta.title` ist ein Sprach-Dict, keine Zeichenkette.

    Ein Stub mit `"title": "…"` sieht einfacher aus und ist falsch; wer darauf
    `.get("de")` ruft, bekaeme im Betrieb einen Fehler statt eines Titels.
    """
    zeile = fixture_json("search_hr_1.json")["content"][0]["meta"]
    assert isinstance(zeile["title"], dict), "der Titel ist kein Sprach-Dict mehr"
    assert {"de", "fr", "it"} & set(zeile["title"]), zeile["title"]
    ergebnis = await _fahre("search_hr")
    assert "Löschung" in ergebnis or "Handelsregister" in ergebnis


def test_total_ist_die_gesamtzahl_und_nicht_die_zeilenzahl():
    """Der Grund, warum `total` beim Kuerzen stehen bleibt.

    Die Quelle meldet dort die Treffer im ganzen Korpus. Wer `total` auf die
    Zeilen der Seite kuerzt, macht aus «10 012 Treffer, davon 3 gezeigt» ein
    «3 Treffer» — und die Antwort behauptet dann etwas ueber die Welt.
    """
    daten = fixture_json("search_hr_1.json")
    assert daten["total"] > len(daten["content"]), (
        "total wurde mitgekuerzt — dann behauptet die Antwort einen kleineren Korpus"
    )


async def test_der_volltext_kommt_als_xml_nicht_als_json(quelle):
    """Zwei Formen, ein Server: die Suche antwortet JSON, der Volltext XML.

    Ein Loader, der ueberall JSON erwartet, liefert hier still nichts.
    """
    volltexte = [n for n in recorded_names() if n.endswith(".xml")]
    assert volltexte
    for name in volltexte:
        assert fixture_text(name).lstrip().startswith("<?xml")
    ergebnis = await _fahre("publication")
    assert "Fehler" not in ergebnis[:200], ergebnis[:300]


# --------------------------------------------------------------------------
# Die Gegenrichtung
# --------------------------------------------------------------------------
@respx.mock
async def test_eine_leere_trefferliste_bleibt_eine_leere_trefferliste():
    """`content: []` ist eine Aussage der Quelle: dazu gibt es nichts.

    Das darf nicht als Fehler herauskommen — sonst kann das Modell einen echten
    Negativtreffer nicht von einem Ausfall unterscheiden.
    """
    respx.get(f"{GAZETTE_BASE}/publications").mock(
        return_value=httpx.Response(200, text=json.dumps({"content": [], "total": 0}))
    )
    ergebnis = await _fahre("search_hr")
    assert not ergebnis.lstrip().startswith("Fehler"), ergebnis[:200]
    assert "0" in ergebnis or "keine" in ergebnis.lower()


@respx.mock
async def test_ein_abbruch_bleibt_ein_fehler():
    """Und die andere Haelfte: ein Ausfall darf nicht als leeres Ergebnis erscheinen."""
    respx.get(f"{GAZETTE_BASE}/publications").mock(side_effect=httpx.ConnectError("weg"))
    ergebnis = await _fahre("search_hr")
    # Der Server sagt es selbst, und zwar woertlich — das ist die Zusicherung
    # wert: ein Modell, das «keine Treffer» liest, wo die Quelle gar nicht
    # geantwortet hat, gibt die Nicht-Antwort als Befund weiter.
    assert "KEIN leeres Ergebnis" in ergebnis, ergebnis[:200]
    assert "degraded" in ergebnis, ergebnis[-200:]
