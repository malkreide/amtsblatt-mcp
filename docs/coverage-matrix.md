# Abdeckungs-Matrix — welcher Teil des Bestands erreichbar ist

> **Gemessen:** 2026-08-03, live gegen `https://amtsblattportal.ch/api/v1`
> **Quelle der Wahrheit im Code:** [`src/amtsblatt_mcp/rubrics.py`](../src/amtsblatt_mcp/rubrics.py)
> **Verfahren:** [`mcp-data-source-probe`](https://github.com/malkreide/mcp-data-source-probe-skill) 1.3b

[`rubric-classification.md`](rubric-classification.md) hält fest, **warum** eine
Rubrik grün oder gesperrt ist. Dieses Dokument hält fest, **wie viel** hinter
jedem Entscheid steht.

Der Unterschied ist nicht kosmetisch. «Konkurse liegen ausserhalb des Scopes»
und «Konkurse sind nicht in der Quelle» lesen sich in einem Review gleich — der
erste Satz ist ein Entscheid, der zweite ist falsch, und nur eine Messung
trennt sie. Genau diese Verwechslung ist in der `ARCH-003`-Begründung dieses
Servers einmal passiert und stand bis 0.22.0 im `SECURITY.md`.

Reproduzieren:

```bash
python scripts/measure_coverage_matrix.py          # Tabelle
python scripts/measure_coverage_matrix.py --json   # maschinenlesbar
```

## Ergebnis

| | Rubriken | Publikationen | Anteil |
|---|---:|---:|---:|
| **Über die Tools erreichbar** | 49 + 4 Sub | 2 359 907 | 84,2 % |
| Bewusst gesperrt (revDSG, `RED_RUBRICS`) | 56 | 352 164 | 12,6 % |
| Noch offen (unklassifiziert, fail-closed) | 47 | 92 151 | 3,3 % |
| **Bestand gesamt** | **152** | **2 804 063** | 100 % |

**Die Achse kommt aus der Quelle, nicht aus dem Code.** `GET /rubrics` liefert
152 Top-Level-Rubriken; die grüne Menge wird in diese Liste **hineinmarkiert**.
Der umgekehrte Weg — die Liste aus `rubrics.py` bilden — könnte per Konstruktion
keine Rubrik finden, welche die Klassifikation übersehen hat.

**Konsistenzprüfung:** Die Summe über alle 152 Rubriken ergibt exakt den
ungefilterten Gesamtwert (2 804 063). Die Achse partitioniert den Bestand —
keine Publikation ohne Rubrik, keine Doppelzählung. Das Skript prüft diese
Gleichheit bei jedem Lauf und meldet eine Abweichung als Warnung.

## Erreichbar — 🟢 grün

| Gruppe | Rubriken | Publikationen |
|---|---:|---:|
| Handelsregister + Bekanntmachungen HRegV | 2 | 2 316 847 |
| Beschlüsse, Erlasse, Rechtsetzung | 13 | 16 037 |
| Umwelt, Verkehr, Energie | 6 | 9 653 |
| Öffentliches Beschaffungswesen | 6 | 7 468 |
| Raumplanung | 7 | 4 199 |
| Kantonale Bekanntmachungen | 6 | 2 775 |
| Politische Rechte | 3 | 1 431 |
| Kommunale Bekanntmachungen | 6 | 1 338 |
| Sub-Rubriken unter gesperrten Eltern (`AR-NW40`, `AR-OW40`, `AR-VS40`, `BA-SH40`) | 4 | 159 |
| **Summe** | **53** | **2 359 907** |

**Die Abdeckung hängt an einer einzigen Rubrik.** `HR` trägt allein 2 275 546
Publikationen — 81,2 % des Gesamtbestands. Alle übrigen 48 grünen Rubriken
zusammen bringen 84 361. Die 84,2 % beschreiben deshalb keine Breite: Sie sind
Handelsregister plus Rest. Für die Anchor-Query ist das genau richtig, als
Aussage über Vielfalt wäre es irreführend.

## Nicht erreichbar — Grund 1: bewusst ausserhalb des Scopes

Systematische Personendaten natürlicher Personen, gesperrt nach revDSG.
Begründungstexte aus `RED_RUBRICS`, Mengen live gemessen.

| Begründung | Rubriken | Publikationen | grösste Einzelrubrik |
|---|---:|---:|---|
| Konkurse, Schuldbetreibungen und Schuldenrufe | 5 | 321 704 | `KK` — 214 297 |
| Baugesuche nennen Grundeigentümer:innen | 7 | 18 135 | `BP-BE` — 8 184 |
| Gerichtliche Vorladungen und Entscheide | 15 | 4 853 | `GB-ZH` — 1 283 |
| Erbschaft, Testament, Ableben | 13 | 3 683 | `ES` — 2 659 |
| Grundbuch und Handänderungen | 2 | 3 480 | `GR-BL` — 3 274 |
| Bürgerrecht und Zivilstandswesen | 13 | 309 | `BU-SZ` — 93 |
| Meldungskatalog GR (gebündelt) | 1 | 0 | `AA-GR` — 0 |

Die Insolvenz-Gruppe ist mit 11,5 % des Bestands der grösste Einzelverzicht
dieses Servers. Das ist die Zahl, die eine Scope-Begründung zitieren sollte.

## Nicht erreichbar — Grund 3: noch offen

47 Rubriken sind weder grün noch mit Begründung rot. Sie sind gesperrt, weil die
Allow-List fail-closed arbeitet — aber ihre Klassifikation steht aus. Nach 1.3b
ist «noch offen» ein zulässiger Grund und ein **offener Befund**, kein
erledigter Punkt.

| Rubrik | Publikationen | Name |
|---|---:|---|
| `AW` | 26 246 | Abhandengekommene Wertpapiere und andere Titel |
| `EK` | 19 472 | Edelmetallkontrolle |
| `AB` | 17 926 | Arbeit |
| `BA-VS` | 11 260 | Bau, Raum, Verkehr und Energie |
| `AM-DA` | 8 010 | ePublikation für Gemeinden und Städte |
| `BA-SH` | 1 684 | Bau, Raum, Verkehr und Energie |
| … 41 weitere | 7 553 | |

Die drei grössten — `AW`, `EK`, `AB` — betreffen dem Namen nach keine
natürlichen Personen und wären Kandidaten für eine Prüfung. Ob sie grün werden
können, entscheidet der Inhalt, nicht das Label: Dieselbe Lehre wie bei den
`OB-*`-Rubriken in [`procurement-coverage.md`](procurement-coverage.md).

## Grund 2 kommt nicht vor

«Technisch nicht erreichbar» trifft auf keine Rubrik zu. Alle 152 sind über die
öffentliche API ohne Authentifizierung abfragbar. Was dieser Server nicht
liefert, liefert er aufgrund eines Entscheids — nicht, weil die Quelle es
verwehrt.

## Nebenbefund: ein fehlender Parameter sieht aus wie fehlende Berechtigung

`GET /publications` **ohne** `publicationStates=PUBLISHED` antwortet mit
**HTTP 401** und `org.springframework.security.access.AccessDeniedException`:

```console
$ curl -s -G https://amtsblattportal.ch/api/v1/publications \
       --data-urlencode "rubrics=HR" --data-urlencode "pageRequest.size=1"
{"exception":"org.springframework.security.access.AccessDeniedException",
 "exceptionMessage":"Access is denied", ...}
```

Ein weggelassener Pflichtparameter ist damit vom Fehlen einer Berechtigung nicht
zu unterscheiden. Wer nur `content` liest und den Status-Code nicht prüft,
bekommt eine leere Liste und hält sie für eine Aussage über den Bestand — die
Verwechslung, gegen die `FID-003` und die Trennung von Ausfall und Abweisung
geschrieben sind. `_http.py` sendet den Parameter in jedem Suchpfad; dieser
Eintrag hält fest, warum er nicht optional ist.
