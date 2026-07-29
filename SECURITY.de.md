# Sicherheitsrichtlinie

[🇬🇧 English Version](SECURITY.md)

## Unterstützte Versionen

| Version | Unterstützt |
|---|---|
| `main` | ✅ |
| `0.1.x` | ✅ |
| `< 0.1` | ❌ |

## Eine Schwachstelle melden

Bitte privat über ein
[GitHub Security Advisory](https://github.com/malkreide/amtsblatt-mcp/security/advisories/new)
melden, nicht über ein öffentliches Issue.

Wenn möglich angeben: betroffene Version, Reproduktionsschritte, den involvierten
Tool-Call oder Request und die beobachtete Auswirkung.

## Reaktionsziele

- Bestätigung: 5 Arbeitstage
- Erste Triage: 10 Arbeitstage

## Geltungsbereich

**Im Geltungsbereich:** das veröffentlichte Paket, das Docker-Image, die
GitHub-Workflows, die Durchsetzung der Green-Allow-List, die Egress-Allow-List
sowie die SSE-Auth- und Rate-Limit-Middleware.

**Ausserhalb des Geltungsbereichs:** das Verhalten von amtsblattportal.ch selbst;
Forks mit entfernter Allow-List oder Authentifizierung; Findings in
Abhängigkeiten ohne nachgewiesene Auswirkung auf diesen Server.

## Datenschutz-Findings sind Sicherheits-Findings

Ein Defekt, der eine gesperrte Rubrik abfragbar macht — oder der Inhalt einer
gesperrten Rubrik in eine Antwort durchsickern lässt — ist eine **Schwachstelle**,
kein Bug-Report. Bitte den privaten Advisory-Kanal dafür nutzen. Konkret jedes
der folgenden melden:

- Eine Rubrik ausserhalb von `GREEN_RUBRICS`, die den Query-String der Quelle
  erreicht.
- `gazette_get_publication`, das Inhalt aus einer nicht grünen Rubrik rendert.
- Eine Tool-Signatur, die einen personenidentifizierenden Parameter akzeptiert.
- Eine Absage-Meldung, die eine Umgehung offenlegt.

## Keine unscharfe Suche — bewusst (ARCH-003)

Keines der drei Such-Tools erweitert einen Suchbegriff automatisch. Alle drei
durchsuchen amtliche Publikationen über namentlich genannte Personen und Firmen:
Konkurse, Betreibungen, Erbenrufe, Baueinsprachen. Eine von `Muster AG` auf
`Muster` verbreiterte Suche liefert Meldungen über *andere* Firmen, und das
realistische Ergebnis ist, dass die falsche Firma als konkursit benannt wird.
«Keine Publikation gefunden» ist eine belastbare Antwort; eine erfundene nicht.

Stattdessen erklärt sich ein leeres Ergebnis selbst: es nennt die verwendeten
Filter und verweist auf zwei Dinge, die von aussen nicht sichtbar sind — die
Rubriken-Freigabe (`gazette_list_rubrics(rubric_class='all')` zeigt, ob die
passende Rubrik hier bewusst nicht erschlossen ist) und den Zustand der Quelle
(`gazette_source_status`; eine Störung sieht von hier aus gleich aus wie ein
leeres Ergebnis). Jede Antwort trägt `match_type` — `exact` oder `none`.

Der Schwesterserver (`swiss-procurement-mcp`) entscheidet aus demselben Grund
umgekehrt: dort erweitern die *Taxonomie*-Abfragen, weil an einem CPV-Code keine
Person hängt, die Ausschreibungssuche dagegen nicht.

## Härtungshinweise für Betreiber

1. **Ein Gateway vor den SSE-Transport setzen.** Die eingebaute Bearer-Auth und
   das Rate-Limit gelten nur pro Instanz; die Rate-Limit-Buckets liegen im
   Prozessspeicher und werden nicht instanzübergreifend geteilt oder aufgeräumt.
2. **Egress auch auf Netzwerkebene beschränken.** `ALLOWED_HOSTS` ist eine
   Defense-in-Depth-Massnahme im Prozess, kein Ersatz für eine Egress-Firewall.
   Es ist ein literales `frozenset` in `server.py` ohne Environment-Override
   (SEC-021) — eine Änderung ist bewusst ein Code-Change.
3. **`MCP_API_KEY` rotieren** und nie in ein Image einbacken.
4. **Die JSON-Logs an dein SIEM schicken** und auf `auth_failed`, `rate_limited`,
   `egress_denied`, `green_gate_violation` und `blocked_publication_requested`
   alarmieren. Die letzten beiden bedeuten, dass etwas eine Rubrik zu erreichen
   versucht hat, die der Server nicht bedient.
5. **Keine Antworten persistieren.** Publikationen tragen gesetzliche
   Löschfristen; der Server hält bewusst keinen Content-Cache, und nachgelagerte
   Speicherung würde das untergraben.

---

## Lethal-Trifecta-Bewertung (SEC-019)

Die «Lethal Trifecta» ist die gefährliche Kombination aus (1) Zugriff auf
private Daten, (2) Kontakt mit nicht vertrauenswürdigen Inhalten und (3) der
Fähigkeit zur Exfiltration. Ein Server mit allen dreien lässt sich durch
eingeschleusten Text dazu bringen, etwas Sensibles zu lesen und irgendwohin zu
senden. Dieser Server wird Leg für Leg bewertet, nicht pauschal freigesprochen.

| Leg | Vorhanden? | Begründung |
|---|---|---|
| Zugriff auf private/sensible Daten | **Nein, konstruktionsbedingt** | Der Amtsblatt-*Korpus* enthält Personendaten — Konkurse, Schuldbetreibungen, Erbschaft, Zivilstand, gerichtliche Vorladungen, Baugesuche. Nichts davon ist erreichbar: diese Rubriken sind nicht erschlossen, und eine Anfrage darauf liefert eine Erklärung statt Daten. Die grüne Freigabeliste wird vor der Anfrage durchgesetzt und nach dem Abruf erneut geprüft. |
| Kontakt mit nicht vertrauenswürdigen Inhalten | **Teilweise** | Tool-Ergebnisse enthalten Publikationstext, den das Modell aufnimmt. Es ist amtlicher, von Schweizer Behörden publizierter Text, nicht angreiferseitig gewählter privater Inhalt — aber nicht von uns verfasst und daher als nicht vertrauenswürdige Eingabe behandelt. |
| Fähigkeit zur Exfiltration | **Nein** | Egress ist per `frozenset`-Allow-List auf `amtsblattportal.ch` beschränkt und wird vor jeder Anfrage geprüft (`EgressDenied`). Keine Write-Endpoints, kein Dateisystem-Tool, und kein nutzergesteuerter Wert erreicht die Host-Komponente einer URL. |

**Höchstens ein Leg ist vorhanden, und zwar das schwächste.** Eingeschleuster
Text in einer Publikation könnte bestenfalls die Zusammenfassung genau dieser
Publikation beeinflussen; er hat nichts, wohin er senden könnte, und nichts
Sensibles zu lesen.

### Was diese Bewertung ändern würde

Jeder dieser Punkte erfordert vor dem Ausliefern eine neue Bewertung:

- Eine rote Rubrik erschliessen oder das Post-Fetch-Green-Gate lockern — das
  schaltet Leg 1 ein.
- Einen zweiten Upstream-Host aufnehmen oder Nutzereingaben in den URL-Host
  gelangen lassen — das schaltet Leg 3 ein.
- Ein Write-, Dateisystem- oder E-Mail-Tool ergänzen — Leg 3 unmittelbar.
- Sampling (`ctx.sample`) ergänzen, wodurch Upstream-Text einen Modellaufruf
  steuern könnte, statt nur von einem zusammengefasst zu werden.

### Verhältnis zum Schwesterserver

`swiss-procurement-mcp` trägt dieselbe Bewertung mit einem Unterschied: dort
gibt es gar keine Personendaten-Rubriken auszuschliessen, Leg 1 fehlt also von
Natur aus statt durch eine durchgesetzte Allow-List. Hier **ist** die
Allow-List die Kontrolle — deshalb läuft `tests/test_allowlist.py` als eigener
CI-Job.
