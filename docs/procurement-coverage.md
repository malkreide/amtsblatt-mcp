# Beschaffungsabdeckung der `OB-*`-Rubriken

Warum `PROCUREMENT_RUBRICS` gemessen und nicht gelesen wird — und wie die Zahlen
zustande kommen.

Reproduzieren:

```bash
python scripts/measure_procurement_coverage.py          # Tabelle
python scripts/measure_procurement_coverage.py --json   # maschinenlesbar
```

## Messung vom 2026-07-27

`publicationStates=PUBLISHED`, Zählung über `total` je Kalenderjahr.

| Rubrik | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 | Letzte Publikation | `active` |
|---|---|---|---|---|---|---|---|---|
| `OB-TI` | 146 | 517 | 491 | 625 | 607 | 546 | 2026-07-27 | ✅ `True` |
| `OB-AR` | 29 | 95 | 85 | 79 | 56 | 40 | 2026-05-22 | ✅ `True` |
| `OB-BS` | 504 | 1 149 | 1 058 | 319 | 15 | **2** | 2026-05-20 | ❌ `False` |
| `OB-VS` | 0 | 0 | 1 052 | 1 | 0 | 0 | 2024-01-05 | ❌ `False` |
| `OB-BL` | 0 | 0 | 74 | 0 | 0 | 0 | 2023-03-30 | ❌ `False` |
| `OB-ZG` | 0 | 0 | 0 | 0 | 0 | 0 | — | ❌ `False` |

**Aktiv publizieren nur noch Ticino und Appenzell Ausserrhoden.**

## Warum das Rubrik-Label nicht genügt

Drei der sechs Rubriken kündigen ihre Stilllegung im eigenen Namen an:

```
OB-BL: Öffentliches Beschaffungswesen über Simap importiert (I N A K T I V)
OB-VS: Öffentliches Beschaffungswesen (bis Ende 2023 über simap.ch importiert)
OB-ZG: Öffentliches Beschaffungswesen (bis Ende Februar 2024 via simap.ch importiert)
```

`OB-BS` heisst dagegen schlicht **«Öffentliches Beschaffungswesen»** — ohne jeden
Hinweis, obwohl das Volumen zwischen 2022 und 2026 von 1 149 auf 2 gefallen ist.
Basel-Stadt ist im Lauf von 2024 zu simap.ch gewechselt, ohne die Rubrik
umzubenennen.

Damit ist der Grundsatz belegt, den v0.1.3 schon für `OB-ZG` gezogen hatte, aber
noch nicht verallgemeinert hatte: **Aktivität ist eine Messgrösse, keine
Textangabe.** Ein Server, der `active` aus dem Label ableitet, hätte den
Basler Fall nicht bemerkt und würde eine tote Rubrik weiter mitdurchsuchen —
womit `search_gazette_procurement(canton="BS")` zwei Alt-Treffer statt der
Erklärung liefert, dass Basel-Stadt heute über simap.ch publiziert.

## Was die drei Import-Labels nebenbei belegen

`OB-BL`, `OB-VS` und `OB-ZG` sagen selbst, dass ihre Inhalte **aus simap.ch
importiert** wurden. Die Beschaffungsrubriken des Amtsblattportals sind also
grösstenteils Zweitpublikationen derselben Ausschreibungen, die
[`swiss-procurement-mcp`](https://github.com/malkreide/swiss-procurement-mcp)
direkt an der Quelle abruft — dort für alle 26 Kantone und den Bund, mit
CPV- und BKP-Codes, Zuschlägen und Publikationsverlauf.

Für Beschaffungsfragen ist simap.ch daher die Primärquelle. Diese Rubriken
bleiben trotzdem erschlossen, weil sie den historischen Bestand abdecken.

Eine Lücke der `OB-*`-Rubriken ist dabei messbar: `OB-TI` enthält 2026 **keinen
einzigen Zuschlag** (alle 546 Datensätze sind Ausschreibungen, Berichtigungen,
Abbrüche oder Widerrufe), während die Subrubrik `AR-VS40` (Wallis, 150
Datensätze) ausschliesslich aus Zuschlägen besteht. `AR-VS40` ist heute nur über
`search_publications(sub_rubric="AR-VS40")` erreichbar, nicht über
`search_gazette_procurement` — siehe `PROCUREMENT_SUB_RUBRICS` in `server.py`.

## Sprachvarianten

Die Trefferzahlen oben zählen **Datensätze, nicht Bekanntmachungen**. Das Portal
publiziert eine Bekanntmachung je Sprache als eigenen Datensatz mit eigener
Publikationsnummer:

| Rubrik | Datensätze 2026 | Sprachen |
|---|---|---|
| `OB-TI` | 546 | it 359 · fr 161 · en 18 · de 8 |
| `OB-AR` | 40 | de 32 · fr 6 · en 2 |
| `OB-BS` | 2 | de 2 |

`search_publications` und `search_gazette_procurement` fassen identische
Sprachfassungen zusammen und weisen den Rest über `language_mix` plus eine
Warnung aus; `only_language=True` erzwingt eine einzelne Sprachfassung. Siehe
den `_FORM_CLASSES`-Block in `server.py` für die Details.

## Wann neu messen

- Vor jeder Änderung an `PROCUREMENT_RUBRICS`
- Wenn Nutzer:innen für einen als aktiv geführten Kanton auffällig wenige
  Treffer melden
- Mindestens einmal jährlich — der Übergang zu simap.ch läuft kantonsweise
  weiter, und keiner dieser Wechsel wird im Rubrik-Label angekündigt
