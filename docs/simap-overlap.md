# Spiegel oder Original? Die Überlappung mit simap.ch

Wie viel der Beschaffungspublikationen dieses Portals auch auf simap.ch steht —
gemessen, nicht geschätzt.

## Der Schlüssel

Das XML einer Publikation (`/publications/{id}/xml`) trägt bei
Zweitpublikationen ein Feld, das die Frage exakt beantwortet:

```xml
<simapPublicationNumber>#41510-01</simapPublicationNumber>
```

Der Wert ist simaps eigene `publicationNumber` im Format
`projectNumber-Sequenz`. Ein Join über Titel oder Fuzzy-Matching ist damit
unnötig — was gut ist, denn beides wäre hier unbrauchbar: die Titel sind
teilweise übersetzt, und simaps Volltextsuche ist ein lockerer OR-Match mit
20 Treffern Deckel.

`get_publication` weist das Feld als `simap_publication_number` aus.

## Messung vom 2026-07-27

**`OB-TI`, Jahrgang 2026** — alle 546 Datensätze einzeln über ihr XML aufgelöst,
gegen ein simap-TI-Universum von 974 Projekten
(`issuedByOrganizations` ∪ `orderAddressCantons`, ohne Datumsfilter, vollständig
paginiert):

| | Anzahl | Anteil |
|---|---|---|
| simap-Referenz vorhanden **und** auflösbar | **503** | **92,1 %** |
| Feld mit Platzhalter `--` gefüllt | 3 | 0,5 % |
| **keine simap-Referenz** | **40** | **7,3 %** |

Und der Schnitt verläuft entlang genau einer Subrubrik:

| Subrubrik | mit Referenz | ohne |
|---|---|---|
| `OB-TI10` Bando di concorso | 460 | 0 |
| `OB-TI20` Concorso | 20 | 0 |
| **`OB-TI65` Avvisi di gara *non CIAP*** | **0** | **39** |
| `OB-TI70` Altro avviso | 26 | 1 |

`OB-TI65` heisst wörtlich «Ausschreibungen **nicht über CIAP**» — die Taxonomie
benennt den Nicht-simap-Kanal selbst.

**Alle Beschaffungsrubriken**, Stichprobe der jeweils neuesten Datensätze:

| Rubrik | Total | mit simap-Referenz | Charakter |
|---|---|---|---|
| `OB-AR` | 384 | 25/25 | Spiegel |
| `OB-BS` | 3 047 | 24/25 | Spiegel |
| `OB-BL` | 74 | 25/25 | Spiegel |
| `OB-VS` | 1 053 | 25/25 | Spiegel |
| `AR-VS40` | 150 | **0/25** | **eigenständig** |
| `AR-OW40` | 7 | **0/7** | **eigenständig** |
| `BA-SH40` | 2 | **0/2** | **eigenständig** |

## Was daraus folgt

**Die `OB-*`-Hauptrubriken sind simap-Spiegel.** Drei von ihnen sagen das im
eigenen Label — `OB-BL`: «über Simap importiert (I N A K T I V)», `OB-VS`: «bis
Ende 2023 über simap.ch importiert», `OB-ZG`: «bis Ende Februar 2024 via
simap.ch importiert». Die Messung zeigt, dass es auch für die beiden aktiven
Rubriken gilt, die es nicht sagen.

Für Beschaffungsfragen ist deshalb
[`swiss-procurement-mcp`](https://github.com/malkreide/swiss-procurement-mcp)
die Primärquelle: alle 26 Kantone plus Bund, mit CPV- und BKP-Codes, Zuschlägen
und Publikationsverlauf — statt drei Kantonen ohne Klassifikation.

**Die Beschaffungs-Subrubriken sind das Gegenteil.** `AR-VS40` (Wallis, 150
Zuschläge), `AR-OW40` (Obwalden) und `BA-SH40` (Schaffhausen) tragen keine
einzige simap-Referenz. Sie sind der einzige Teil der hiesigen
Beschaffungsabdeckung, den simap.ch nicht hat — und liegen in Kantonen **ohne**
aktive `OB-*`-Rubrik. `search_gazette_procurement(canton="VS"|"OW"|"SH")`
liefert sie seit v0.3.0; vorher waren sie nur über
`search_publications(sub_rubric=…)` erreichbar.

Sie werden ausschliesslich als `subRubrics` gesendet, nie als `rubrics`: Die
Elternrubriken `AR-VS`, `AR-OW` und `BA-SH` sind Sammelrubriken mit
Arbeitsvergaben bzw. Baugesuchen und bleiben gesperrt.

`AR-NW40` (Nidwalden) steht auf der Freigabe-Liste, wird aber nicht durchsucht:
0 Publikationen. Leere ist eine Abdeckungs-, keine Datenschutzfrage — die
Freigabe bleibt, nur der Filterplatz wird gespart.

## Methodische Warnung für eine Neumessung

Der erste Anlauf dieser Messung war unbrauchbar, weil das simap-Universum über
`orderAddressCantons` gezogen wurde. Dieser Filter selektiert den **Leistungs-
ort**, und rund 60 % der simap-Publikationen tragen keine strukturierte
Bestelladresse — sie fehlen dann still. Wer neu misst:

1. simap-Korpus über `issuedByOrganizations=<Wurzel-Institution des Kantons>`
   ziehen, unioniert mit `orderAddressCantons`, **ohne Datumsfilter**
   (`project-search` filtert auf das *neueste* Publikationsdatum, ein Fenster
   verliert also ältere Publikationen noch laufender Projekte).
2. Über `<simapPublicationNumber>` joinen, nie über Titel.
3. Platzhalterwerte (`--`) als «keine Referenz» behandeln, nicht als
   unauflösbare ID.

Reproduzieren: siehe `scripts/measure_procurement_coverage.py` für die
Volumina; der Overlap-Join war eine einmalige Auswertung über ~750 XML-Abrufe.
