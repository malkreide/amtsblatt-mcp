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

Der Hook **blockiert die Session nie.** Kein Netz, kein Remote, flatterndes
DNS, abgelaufene Credentials, fehlendes `git` — jeder dieser Fälle endet
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
| detached HEAD, n > 0 zurück | Meldung mit Anzahl **und** dem Hinweis, dass HEAD detached ist |
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
| detached-HEAD-Hinweis in der Meldung | `…detached_head_wird_als_solcher_benannt` |
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

## Detached HEAD

Ursprünglich schwieg der Hook hier. Auf Wunsch zählt er jetzt mit: ein
detached HEAD ist gerade die Lage, in der man unbemerkt alt wird — er
entsteht beim Auschecken eines Tags oder eines alten Commits, und nichts
erinnert danach daran. `git rev-list --count HEAD..origin/<branch>` ist dort
ohnehin wohldefiniert.

Die Meldung nennt den Zustand aber ausdrücklich und schlägt einen anderen
Befehl vor. `git pull --ff-only` lässt den Stand detached; wer den Rückstand
sieht, ohne zu wissen, dass er auf keinem Branch steht, sucht den nächsten
Fehler an der falschen Stelle.

## Windows: Zeilenenden

Der Hook ist ein `#!/bin/sh`-Skript. Wird er mit **CRLF** ausgecheckt, ist er
tot — `$'\r': command not found`, Zeile für Zeile. Auf Windows ist genau das
der Standard (`core.autocrlf=true`), und am 19.08.2026 ist es auf einem
frischen Klon passiert.

Das ist die gefährlichste Ausfallart, die dieser Hook hat: er blockiert nie
und schweigt, wenn nichts zu melden ist. Ein Hook, der wegen CRLF gar nicht
startet, sieht deshalb **exakt aus wie ein aktueller Klon**. Man verlässt sich
auf eine Prüfung, die nicht läuft.

Abgesichert ist das über `.gitattributes` (`* text=auto eol=lf`) und
`tests/test_line_endings.py` — der Test schlägt auf einem CRLF-Klon fehl,
bevor jemand dem Schweigen glaubt.

Ein bereits falsch ausgecheckter Klon lässt sich renormalisieren:

```bash
git rm --cached -r .
git reset --hard
```

## Von Hand prüfen, richtig

`git checkout <alter-commit>` ist als Test **ungeeignet**: liegt der Commit vor
der Einführung des Hooks, verschwindet dabei die Datei selbst. Stattdessen eine
Kopie ausserhalb des Repos verwenden:

```bash
cp .claude/hooks/session-start.sh /tmp/hook.sh && chmod +x /tmp/hook.sh
git checkout --detach HEAD~3
CLAUDE_PROJECT_DIR="$PWD" /tmp/hook.sh    # erwartet: "3 Commits hinter ..."
git checkout -
```

## Windows: die Tests

Die Tests rufen den Hook **immer über eine ausdrücklich aufgelöste Shell** auf,
nie direkt. Ein `subprocess.run([".../session-start.sh"])` endet auf Windows mit
`WinError 193: keine zulässige Win32-Anwendung` — einen Shebang kennt Windows
nicht, und mit LF-Zeilenenden hat das nichts zu tun.

Gewählt wird `sh`, dann `bash`, dann Git for Windows. Das `bash.exe` in
`System32` wird **übergangen**: es startet WSL, sieht ein anderes Dateisystem
und macht aus `C:\Users\…` nichts Brauchbares (`C:UsershayalAppData…`). Findet
sich keine brauchbare Shell, überspringt das Modul mit einem Grund, der sagt,
was fehlt — es fällt nicht rot aus.

Die Auswahl steckt in `_waehle_shell()` und ist mit erfundenen Pfaden geprüft,
damit der WSL-Ausschluss auch auf Linux eine Gegenprobe hat. Sonst liefe genau
dieser Zweig nur auf Windows, also dort, wo hier niemand testet. Ein
Wächter-Test stellt sicher, dass das Modul nicht unbemerkt komplett
übersprungen wird.

Vier Tests legen Shell-Stubs an, die *git selbst* über `PATH` oder
`core.sshCommand` startet, und brauchen `sleep`. Ob das unter Git Bash trägt,
ist ungeprüft; sie überspringen ausserhalb von POSIX mit Begründung.

### Das Ausführungsbit

`os.access(HOOK, os.X_OK)` beantwortet die Frage auf Windows nicht — dort gibt
es kein Exec-Bit, und der Aufruf meldet für jede vorhandene Datei Erfolg. Der
Test war dort grün, ohne etwas zu prüfen. Geprüft wird deshalb der Modus im
git-Index (`100755`); den tragen alle Klone.
