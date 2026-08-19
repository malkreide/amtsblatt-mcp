# SessionStart-Hook: Klon-Aktualität

`session-start.sh` meldet beim Sessionstart, wie viele Commits der
ausgecheckte Stand hinter `origin/<Default-Branch>` liegt. Registriert ist er
in `.claude/settings.json` (`SessionStart`, `timeout: 15`).

## Warum

Ein veralteter Klon hat am **3.8.2026 zweimal eine rote CI erzeugt, deren
Ursache nicht im Diff stand** — die fehlenden Commits waren jeweils genau
die, die das Gate einführten, an dem der Branch scheiterte. Man sucht den
Fehler dann in den Dateien, die man selbst geändert hat, und dort ist er
nicht. Die Prüfung kostet eine Sekunde und ersetzt eine Fehlersuche in den
falschen Dateien.

Der Hook ist die automatische Fassung des ersten Absatzes von `CLAUDE.md`
(«Vor der Arbeit»).

## Verhalten

Der Hook **blockiert die Session nie.** Kein Netz, kein Remote, detached
HEAD, flatterndes DNS, abgelaufene Credentials — jeder dieser Fälle endet
mit Exit 0 und ohne Ausgabe. Das ist keine Kosmetik: ein Hook, der bei
Netzproblemen die Arbeit anhält, wird nach dem zweiten Mal abgeschaltet und
schützt danach gar nichts.

Ausgabe gibt es **nur, wenn wirklich Commits fehlen.** Bei 0 schweigt er.

| Fall | Verhalten |
| --- | --- |
| n > 0 Commits hinter dem Default-Branch | Meldung mit Anzahl, Branchname und Update-Befehl |
| aktuell (0 Commits hinter) | still |
| kein Git-Repository, `git` nicht im `PATH` | still |
| kein Remote `origin` | still |
| detached HEAD | still — kein Branch, den man aktualisieren würde (Tag, alter Commit, Bisect) |
| Netz weg, DNS flattert, Remote weg, Auth kaputt | still, nach Timeout |
| Default-Branch nicht ermittelbar | still — es wird **nicht** auf `main` geraten |

Timeouts: `git ls-remote` 3 s, `git fetch` 5 s, dazu 15 s als äusserer
Riegel in `settings.json`. Der `fetch` holt nur den Default-Branch,
ohne Tags und mit `gc.auto=0`.

## Der Default-Branch wird ermittelt, nicht angenommen

Drei Server im Portfolio (`openlex-mcp`, `swiss-courts-mcp`,
`swisstopo-mcp`) heissen ihren Default-Branch `master`. Ein fest
verdrahtetes `main` hat dort schon einmal einen Branch 15 Commits alt werden
lassen, weil der Vergleich still ins Leere lief.

Reihenfolge: `git ls-remote --symref origin HEAD` (autoritativ), bei
Netzfehler der lokal gemerkte `refs/remotes/origin/HEAD`. Bleibt der Name
leer, bricht der Hook ab — ein leerer Wert darf nicht durchfallen, weil
`git fetch origin ""` still auf den Remote-HEAD zurückfällt und mit 0 endet
(dasselbe, was in `CLAUDE.md` der `:?`-Schutz abfängt).

## Nicht-Ziele

Der Hook **aktualisiert nichts.** Er zieht keinen `pull`, keinen `rebase`,
keinen `merge` — was mit den fehlenden Commits passiert, entscheidet, wer
arbeitet. Ein Hook, der ungefragt den Arbeitsstand verändert, ist gefährlicher
als der veraltete Klon, den er meldet.

## Tests

`tests/test_session_start_hook.py` fährt das Skript gegen echte, lokal
angelegte Git-Repositories (kein Netz nötig, `file://`-Remotes) und prüft
jede Zeile der Tabelle oben. Läuft mit den normalen Gates:

```bash
PYTHONPATH=src pytest tests/test_session_start_hook.py -m "not live" -v
```

Von Hand ausprobieren — im aktuellen Klon, so wie Claude Code ihn aufruft:

```bash
CLAUDE_PROJECT_DIR="$PWD" .claude/hooks/session-start.sh; echo "exit=$?"
```

### Gegenprobe

Jede Zusicherung wurde einzeln aus dem Skript entfernt; es fielen genau die
zugehörigen Tests:

| Entfernt | Es fiel |
| --- | --- |
| Default-Branch ermitteln (fest `main`) | `…default_branch_statt_main…[master]`, `[trunk]`, `…raet_nicht_auf_main…` |
| Schweigen bei 0 | `…klon_aktuell_ist`, `…commits_voraus…` |
| Timeouts auf ls-remote/fetch | `…haengendes_remote…` |
| detached-HEAD-Wache | `…detached_head…` |
| Leer-Prüfung des Branchnamens | `…leerer_branchname_faellt_nicht_durch` |
| Einzahl-Behandlung | `…einzahl_bei_genau_einem…` |
| Begründung in der Meldung | `…nennt_den_grund…` |
| Update-Befehl in der Meldung | `…nennt_den_befehl…` |
| stderr-Unterdrückung (alle Stellen) | `…kaputtes_git_erzeugt_nicht_einmal_stderr` |

Zwei Konstrukte bleiben **bewusst ungeprüft**, weil sie doppelt gesichert und
von aussen nicht unterscheidbar sind: die `command -v git`-Wache und
`check … || true` (kein `set -e`). Einzeln entfernt fällt kein Test — die
jeweils andere Sicherung fängt den Fall ab. Sie bleiben trotzdem stehen: sie
tragen die oberste Regel («blockiert nie»), und die ist mehr wert als eine
aufgeräumte Mutationsstatistik. Wer hier kürzt, entfernt die zweite Sicherung
einer Eigenschaft, die im Fehlerfall niemand mehr prüft.

Die Leer-Prüfung stand anfangs doppelt (in `resolve_default_branch` **und** in
`check`) und war damit toter Code, den keine Gegenprobe widerlegen konnte. Sie
steht jetzt an genau einer Stelle.
