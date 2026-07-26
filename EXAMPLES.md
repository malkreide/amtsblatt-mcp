# Use Cases & Examples — amtsblatt-mcp

Realitätsnahe Anfragen nach Zielgruppe. Der Server erschliesst **amtsblattportal.ch** — das Schweizer Amtsblattportal (SHAB + 27 kantonale Amtsblätter): öffentliche Beschaffungen und amtliche Bekanntmachungen. **API-Key nötig: Nein** — der Lese-Zugang der Amtsblattportal-API ist frei zugänglich; ein Bearer-Token (`MCP_API_KEY`) wird ausschliesslich beim Selbst-Betrieb über SSE verlangt, nicht für die Datenquelle.

> Datenschutz by Design: Rubriken mit systematischen Personendaten (Konkurse, Betreibungen, Erbschaft, Zivilstand, Baugesuche u. a.) sind **bewusst nicht abfragbar**. Kein Tool nimmt einen Personennamen, ein Geburtsdatum oder eine Adresse entgegen. Gesperrte Rubriken liefern eine Erklärung statt eines stillen Leerergebnisses.

## 🏫 Bildung & Schule

**«Welche öffentlichen IT-Ausschreibungen gab es zuletzt in einem Kanton?»**
- **API-Key nötig:** Nein
- → `search_procurement(canton="BS", keyword="Informatik")`
- → `get_publication(id="<id aus dem Treffer>")`
- Warum nützlich: Zeigt an einem konkreten Beispiel, wie öffentliche Beschaffung funktioniert — geeignet für Unterricht zu Verwaltung, Wirtschaft und Staatskunde. Aktive Beschaffungs-Rubriken bestehen nur in AR, BS und TI.

**«Was ist auf diesem Portal überhaupt abfragbar — und was nicht?»**
- **API-Key nötig:** Nein
- → `list_rubrics(rubric_class="all")`
- Warum nützlich: Macht die Ampel-Klassierung (grün/gelb/rot) mit Begründung sichtbar — ein anschauliches Lehrbeispiel dafür, wie Datenschutz eine technische Schnittstelle formt: gelistet heisst nicht abfragbar.

## 👨‍👩‍👧 Eltern & Schulgemeinde

**«Gibt es Bekanntmachungen zu Raumplanung oder Nutzungsplänen in unserem Kanton?»**
- **API-Key nötig:** Nein
- → `search_publications(rubric="RP-ZH")`
- → `get_publication(id="<id>")`
- Warum nützlich: Eltern und Schulgemeinden können amtliche Planungsvorhaben im eigenen Umfeld nachverfolgen — mit Quellenangabe und vollständigem amtlichem Text.

**«Ist die Amtsblatt-Quelle gerade erreichbar und aktuell?»**
- **API-Key nötig:** Nein
- → `source_status()`
- Warum nützlich: Liefert Erreichbarkeit, Latenz, Cache-Alter und Umfangs-Kennzahlen — so weiss man, ob eine leere Trefferliste «nichts gefunden» oder «Quelle gestört» bedeutet.

## 🗳️ Bevölkerung & öffentliches Interesse

**«Welche amtlichen Bekanntmachungen zu einem Stichwort gab es in einem Zeitraum?»**
- **API-Key nötig:** Nein
- → `search_publications(keyword="Ausschreibung", canton="BS", date_start="2026-04-01", date_end="2026-06-30")`
- Warum nützlich: Ohne Angabe einer Rubrik werden automatisch alle freigegebenen (grünen) Rubriken einbezogen — eine reine Stichwortsuche kann nie versehentlich eine gesperrte Rubrik erreichen.

**«Ich möchte auch ältere/archivierte Beschaffungen sehen.»**
- **API-Key nötig:** Nein
- → `search_procurement(canton="VS", include_inactive=True)`
- Warum nützlich: Mit `include_inactive=True` werden die Archive (z. B. BL und VS) erreichbar; ein Kanton ohne aktive `OB-*`-Rubrik erhält einen simap.ch-Hinweis statt eines leeren Ergebnisses — ganz ohne HTTP-Aufruf.

## 🤖 KI-Interessierte & Entwickler:innen

**«Wie hole ich den vollständigen amtlichen Text einer Bekanntmachung als JSON?»**
- **API-Key nötig:** Nein
- → `get_publication(id="fbf0ff9e-…", response_format="json")`
- Warum nützlich: Der Volltext kommt defensiv aus dem XML; nach dem Abruf wird die Rubrik erneut geprüft, sodass Inhalt aus einer gesperrten Rubrik verworfen wird. `response_format` erlaubt Markdown oder JSON für die Weiterverarbeitung.

**«Alles, was zu einer bestimmten Firma publiziert wurde?»**
- **API-Key nötig:** Nein
- → für unternehmensbezogene Abfragen: [`register-mcp`](https://github.com/malkreide/register-mcp) (Zefix, Join über die Firmen-UID)
- Warum nützlich: Portfolio-Kombination mit klarer Grenze — `amtsblatt-mcp` bietet breite Suche über enge, personendaten-freie Rubriken; unternehmensbezogene Recherche (inkl. Firmenkonkurs) läuft UID-gebunden über `register-mcp`, was namensbasierte Profilbildung ausschliesst.

## 🔧 Technische Referenz: Tool-Auswahl nach Anwendungsfall

| Ich möchte… | Tool(s) | Auth nötig? |
|---|---|---|
| Amtliche Bekanntmachungen in freigegebenen (grünen) Rubriken suchen | `search_publications` | Nein |
| Öffentliche Beschaffungen/Ausschreibungen (`OB-*`) suchen | `search_procurement` | Nein |
| Den vollständigen amtlichen Text einer Publikation abrufen | `get_publication` | Nein |
| Die abfragbaren Rubriken (bzw. die volle Taxonomie mit Ampel) auflisten | `list_rubrics` | Nein |
| Erreichbarkeit, Latenz und Cache-Zustand der Quelle prüfen | `source_status` | Nein |
