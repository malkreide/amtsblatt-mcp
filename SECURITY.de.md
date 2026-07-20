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
- `get_publication`, das Inhalt aus einer nicht grünen Rubrik rendert.
- Eine Tool-Signatur, die einen personenidentifizierenden Parameter akzeptiert.
- Eine Absage-Meldung, die eine Umgehung offenlegt.

## Härtungshinweise für Betreiber

1. **Ein Gateway vor den SSE-Transport setzen.** Die eingebaute Bearer-Auth und
   das Rate-Limit gelten nur pro Instanz; die Rate-Limit-Buckets liegen im
   Prozessspeicher und werden nicht instanzübergreifend geteilt oder aufgeräumt.
2. **Egress auch auf Netzwerkebene beschränken.** `MCP_ALLOWED_HOSTS` ist eine
   Defense-in-Depth-Massnahme im Prozess, kein Ersatz für eine Egress-Firewall.
   Beachte: eine Überschreibung *ersetzt* den Standard vollständig — sie muss
   `amtsblattportal.ch` enthalten.
3. **`MCP_API_KEY` rotieren** und nie in ein Image einbacken.
4. **Die JSON-Logs an dein SIEM schicken** und auf `auth_failed`, `rate_limited`,
   `egress_denied`, `green_gate_violation` und `blocked_publication_requested`
   alarmieren. Die letzten beiden bedeuten, dass etwas eine Rubrik zu erreichen
   versucht hat, die der Server nicht bedient.
5. **Keine Antworten persistieren.** Publikationen tragen gesetzliche
   Löschfristen; der Server hält bewusst keinen Content-Cache, und nachgelagerte
   Speicherung würde das untergraben.
