"""Der SessionStart-Hook `.claude/hooks/session-start.sh`.

Der Hook meldet, wie viele Commits der ausgecheckte Stand hinter
origin/<Default-Branch> liegt. Der Grund steht in `.claude/hooks/README.md`:
ein veralteter Klon hat am 3.8.2026 zweimal eine rote CI erzeugt, deren Ursache
nicht im Diff stand.

Die Tests fahren das Skript gegen echte, lokal angelegte Git-Repositories mit
`file://`-Remotes — kein Netz, keine handgeschriebene Fixture, die die Annahme
des Autors nur wiederholt. Geprueft wird die Eigenschaft, nicht die
Implementierung: dass der Hook zaehlt, wenn etwas fehlt, und dass er in jedem
anderen Fall still mit 0 endet.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOK = REPO_ROOT / ".claude" / "hooks" / "session-start.sh"
SETTINGS = REPO_ROOT / ".claude" / "settings.json"
HOOK_README = REPO_ROOT / ".claude" / "hooks" / "README.md"


def _posix_shell() -> str | None:
    """Eine Shell, die das Skript ausfuehren kann — oder None.

    Der Hook direkt als Programm zu starten geht nur auf POSIX. Auf Windows
    endet `subprocess.run([".../session-start.sh"])` mit
    `WinError 193: keine zulaessige Win32-Anwendung`; einen Shebang kennt
    Windows nicht. Also wird immer ausdruecklich eine Shell davorgesetzt.

    Auf Windows ist das `bash.exe` in System32 der WSL-Starter. Das ist die
    falsche Wahl: es sieht ein anderes Dateisystem und macht aus
    `C:\\Users\\...` nichts Brauchbares. Git for Windows bringt dagegen ein
    `sh.exe` mit, das mit Windows-Pfaden umgeht.
    """
    if os.name == "posix":
        return shutil.which("sh") or shutil.which("bash")

    return _waehle_shell(
        [
            shutil.which("sh"),
            shutil.which("bash"),
            r"C:\Program Files\Git\bin\sh.exe",
            r"C:\Program Files\Git\usr\bin\sh.exe",
        ],
        Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32",
    )


def _waehle_shell(kandidaten: list[str | None], system32: Path) -> str | None:
    """Den ersten brauchbaren Kandidaten waehlen, System32 uebergehen.

    Als eigene Funktion, damit die Auswahl auch auf Linux pruefbar ist. Sonst
    liefe der Zweig, der den WSL-Starter aussortiert, nur auf Windows — also
    genau dort, wo hier niemand testet.
    """
    for kandidat in kandidaten:
        if not kandidat:
            continue
        pfad = Path(kandidat)
        if not pfad.is_file():
            continue
        try:
            if pfad.parent.resolve() == system32.resolve():
                continue  # WSL-Starter, kein brauchbares sh
        except OSError:  # pragma: no cover - Pfadauflösung schlaegt selten fehl
            pass
        return str(pfad)
    return None


SHELL = _posix_shell()

# Kein blosses `skipif(os.name != "posix")`: mit Git for Windows laufen diese
# Tests dort sehr wohl. Uebersprungen wird nur, wenn wirklich keine Shell da
# ist — und dann mit einem Grund, der sagt, was fehlt.
pytestmark = pytest.mark.skipif(
    SHELL is None,
    reason=(
        "der Hook ist ein POSIX-Shell-Skript und braucht eine Shell zum "
        "Ausfuehren; keine gefunden (auf Windows: Git for Windows installieren)"
    ),
)

# Diese Tests legen zusaetzlich Shell-Skripte an, die *git selbst* ueber den
# PATH oder core.sshCommand startet, und brauchen `sleep`. Ob das unter Git
# Bash traegt, ist ungeprueft — ein ehrliches Skip ist besser als ein roter
# Test, den niemand einordnen kann.
braucht_posix = pytest.mark.skipif(
    os.name != "posix",
    reason="setzt Shell-Stubs voraus, die git selbst ausfuehrt (nur auf POSIX geprueft)",
)

# Der Hook raeumt sich selbst zwei Netz-Timeouts ein (ls-remote 3 s, fetch 5 s).
# Ein haengendes Remote darf also rund 8 s kosten und keine Sekunde mehr.
TIMEOUT_BUDGET_S = 20.0


def _git_env() -> dict[str, str]:
    """Eine Umgebung ohne die Git-Konfiguration des Entwicklers.

    Ohne das entscheidet `~/.gitconfig` mit — etwa `init.defaultBranch` — und
    die Tests wuerden auf einer anderen Maschine anderes pruefen.
    """
    env = dict(os.environ)
    env.pop("GIT_SSH_COMMAND", None)
    env.update(
        GIT_CONFIG_GLOBAL=os.devnull,
        GIT_CONFIG_SYSTEM=os.devnull,
        GIT_AUTHOR_NAME="Test",
        GIT_AUTHOR_EMAIL="test@example.invalid",
        GIT_COMMITTER_NAME="Test",
        GIT_COMMITTER_EMAIL="test@example.invalid",
        GIT_TERMINAL_PROMPT="0",
    )
    return env


def _git(cwd: Path, *args: str) -> str:
    done = subprocess.run(
        ("git", *args),
        cwd=cwd,
        env=_git_env(),
        capture_output=True,
        text=True,
        check=True,
    )
    return done.stdout.strip()


class HookRun:
    def __init__(self, returncode: int, stdout: str, stderr: str, seconds: float) -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.seconds = seconds

    @property
    def silent(self) -> bool:
        return self.stdout.strip() == ""


def _run_hook(cwd: Path) -> HookRun:
    """Den Hook so aufrufen, wie Claude Code es tut: im Projektverzeichnis."""
    env = _git_env()
    env["CLAUDE_PROJECT_DIR"] = str(cwd)
    started = time.monotonic()
    done = subprocess.run(
        [SHELL, str(HOOK)],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    return HookRun(done.returncode, done.stdout, done.stderr, time.monotonic() - started)


def _run_hook_branch_hint(clone: Path) -> str | None:
    """Was sich der Klon lokal als Default-Branch gemerkt hat, wenn ueberhaupt."""
    done = subprocess.run(
        ("git", "symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD"),
        cwd=clone,
        env=_git_env(),
        capture_output=True,
        text=True,
    )
    return done.stdout.strip() or None


def _world(
    tmp_path: Path,
    *,
    default_branch: str = "main",
    behind: int = 0,
    shallow: bool = False,
) -> Path:
    """Ein Upstream mit `default_branch` und ein Klon, der `behind` Commits fehlt."""
    upstream = tmp_path / "upstream.git"
    subprocess.run(
        ("git", "init", "-q", "--bare", "-b", default_branch, str(upstream)),
        env=_git_env(),
        check=True,
        capture_output=True,
    )

    seed = tmp_path / "seed"
    subprocess.run(
        ("git", "clone", "-q", str(upstream), str(seed)),
        env=_git_env(),
        check=True,
        capture_output=True,
    )
    _git(seed, "checkout", "-q", "-B", default_branch)
    _git(seed, "commit", "-q", "--allow-empty", "-m", "erster Commit")
    _git(seed, "push", "-q", "-u", "origin", default_branch)

    clone = tmp_path / "clone"
    clone_args = ["clone", "-q"]
    if shallow:
        clone_args += ["--depth", "1"]
    # file:// statt Pfad: nur so nimmt git den echten Transport und damit auch
    # --depth ernst.
    clone_args += [f"file://{upstream}", str(clone)]
    subprocess.run(("git", *clone_args), env=_git_env(), check=True, capture_output=True)

    for n in range(behind):
        _git(seed, "commit", "-q", "--allow-empty", "-m", f"spaeterer Commit {n + 1}")
    if behind:
        _git(seed, "push", "-q", "origin", default_branch)

    return clone


# --- Der eigentliche Zweck: fehlende Commits werden gemeldet ------------------


def test_meldet_die_anzahl_fehlender_commits(tmp_path: Path) -> None:
    run = _run_hook(_world(tmp_path, behind=3))
    assert run.returncode == 0
    assert "3 Commits" in run.stdout
    assert "origin/main" in run.stdout


def test_nennt_den_befehl_zum_aktualisieren(tmp_path: Path) -> None:
    """Eine Meldung ohne den naechsten Schritt kostet nur Zeit."""
    run = _run_hook(_world(tmp_path, behind=2))
    assert "git pull --ff-only origin main" in run.stdout


def test_nennt_den_grund_damit_niemand_die_meldung_wegklickt(tmp_path: Path) -> None:
    run = _run_hook(_world(tmp_path, behind=2))
    assert "3.8.2026" in run.stdout
    assert "CI" in run.stdout


def test_einzahl_bei_genau_einem_fehlenden_commit(tmp_path: Path) -> None:
    run = _run_hook(_world(tmp_path, behind=1))
    assert "1 Commit " in run.stdout
    assert "1 Commits" not in run.stdout


def test_zaehlt_auch_im_shallow_klon_richtig(tmp_path: Path) -> None:
    """Claude Code auf dem Web klont mit --depth 1 — der Normalfall, nicht der Rand."""
    clone = _world(tmp_path, behind=4, shallow=True)
    assert _git(clone, "rev-parse", "--is-shallow-repository") == "true"
    run = _run_hook(clone)
    assert run.returncode == 0
    assert "4 Commits" in run.stdout


# --- Bei 0 schweigt er -------------------------------------------------------


def test_schweigt_wenn_der_klon_aktuell_ist(tmp_path: Path) -> None:
    run = _run_hook(_world(tmp_path, behind=0))
    assert run.returncode == 0
    assert run.silent, f"unerwartete Ausgabe: {run.stdout!r}"


def test_eigene_commits_voraus_sind_kein_rueckstand(tmp_path: Path) -> None:
    """Wer vor dem Remote liegt, ist nicht veraltet."""
    clone = _world(tmp_path, behind=0)
    _git(clone, "commit", "-q", "--allow-empty", "-m", "eigene Arbeit")
    run = _run_hook(clone)
    assert run.silent, f"unerwartete Ausgabe: {run.stdout!r}"


# --- Detached HEAD: zaehlt mit -----------------------------------------------


def test_detached_head_wird_mitgezaehlt(tmp_path: Path) -> None:
    """Auch ohne Branch ist ein Rueckstand ein Rueckstand.

    Frueher schwieg der Hook hier. Ein detached HEAD ist aber genau die Lage,
    in der man am ehesten unbemerkt alt wird — er entsteht beim Auschecken
    eines Tags oder eines alten Commits, und nichts erinnert danach daran.
    """
    clone = _world(tmp_path, behind=3)
    _git(clone, "checkout", "-q", "--detach", "HEAD")
    run = _run_hook(clone)
    assert run.returncode == 0
    assert "3 Commits" in run.stdout
    assert "origin/main" in run.stdout


def test_detached_head_wird_als_solcher_benannt(tmp_path: Path) -> None:
    """Der Update-Befehl fuer einen Branch waere hier irrefuehrend: `git pull`
    laesst den Stand detached. Wer den Rueckstand sieht, ohne zu wissen, dass
    er auf keinem Branch steht, sucht den naechsten Fehler an der falschen
    Stelle."""
    clone = _world(tmp_path, behind=3)
    _git(clone, "checkout", "-q", "--detach", "HEAD")
    run = _run_hook(clone)
    assert "detached" in run.stdout
    assert "git checkout main" in run.stdout


def test_auf_einem_branch_bleibt_der_hinweis_weg(tmp_path: Path) -> None:
    """Gegenprobe zum vorigen Test: der Normalfall darf nicht plaudern."""
    run = _run_hook(_world(tmp_path, behind=3))
    assert "detached" not in run.stdout
    assert "git pull --ff-only origin main" in run.stdout


# --- Oberste Regel: blockiert nie --------------------------------------------


def test_ohne_remote_geht_still_durch(tmp_path: Path) -> None:
    clone = _world(tmp_path, behind=3)
    _git(clone, "remote", "remove", "origin")
    run = _run_hook(clone)
    assert run.returncode == 0
    assert run.silent, f"unerwartete Ausgabe: {run.stdout!r}"


def test_ohne_git_repository_geht_still_durch(tmp_path: Path) -> None:
    plain = tmp_path / "kein-repo"
    plain.mkdir()
    run = _run_hook(plain)
    assert run.returncode == 0
    assert run.silent, f"unerwartete Ausgabe: {run.stdout!r}"


def test_verschwundenes_remote_geht_still_durch(tmp_path: Path) -> None:
    clone = _world(tmp_path, behind=3)
    (tmp_path / "upstream.git").rename(tmp_path / "weg.git")
    run = _run_hook(clone)
    assert run.returncode == 0
    assert run.silent, f"unerwartete Ausgabe: {run.stdout!r}"


@braucht_posix
def test_haengendes_remote_wird_nach_wenigen_sekunden_abgebrochen(tmp_path: Path) -> None:
    """Flatterndes DNS ist der Fall, der den Hook sonst zum Blocker macht.

    Ein `ssh`, das nur schlaeft, haelt `ls-remote` und `fetch` beliebig lange
    auf. Ohne Timeout haengt der Sessionstart daran; mit Timeout kostet es die
    veranschlagten paar Sekunden.
    """
    clone = _world(tmp_path, behind=3)
    stub = tmp_path / "schlafendes-ssh.sh"
    stub.write_text("#!/bin/sh\nexec sleep 60 </dev/null >/dev/null 2>&1\n")
    stub.chmod(0o755)
    _git(clone, "config", "core.sshCommand", str(stub))
    _git(clone, "remote", "set-url", "origin", "ssh://git@remote.invalid/repo.git")

    run = _run_hook(clone)
    assert run.returncode == 0
    assert run.silent, f"unerwartete Ausgabe: {run.stdout!r}"
    assert run.seconds < TIMEOUT_BUDGET_S, f"Sessionstart {run.seconds:.1f}s aufgehalten"


@braucht_posix
def test_kaputtes_git_erzeugt_nicht_einmal_stderr(tmp_path: Path) -> None:
    """Still heisst auch: keine Fehlerzeilen.

    Ein Hook, der bei jedem Sessionstart Git-Fehler ausspuckt, ist Rauschen —
    und Rauschen wird abgeschaltet. Der Stub steht fuer alles, was `git`
    unerwartet scheitern laesst (kaputte Installation, fremdes `git` im PATH).
    """
    clone = _world(tmp_path, behind=3)
    stubdir = tmp_path / "bin"
    stubdir.mkdir()
    stub = stubdir / "git"
    stub.write_text("#!/bin/sh\necho 'git: alles kaputt' >&2\nexit 3\n")
    stub.chmod(0o755)

    env = _git_env()
    env["PATH"] = f"{stubdir}{os.pathsep}{env['PATH']}"
    env["CLAUDE_PROJECT_DIR"] = str(clone)
    done = subprocess.run(
        [SHELL, str(HOOK)], cwd=clone, env=env, capture_output=True, text=True, timeout=120
    )
    assert done.returncode == 0
    assert done.stdout.strip() == "", f"unerwartete Ausgabe: {done.stdout!r}"
    assert done.stderr.strip() == "", f"unerwartetes Rauschen auf stderr: {done.stderr!r}"


@braucht_posix
def test_ohne_git_im_pfad_geht_still_durch(tmp_path: Path) -> None:
    clone = _world(tmp_path, behind=3)
    env = _git_env()
    env["PATH"] = str(tmp_path / "leer")
    env["CLAUDE_PROJECT_DIR"] = str(clone)
    done = subprocess.run(
        [SHELL, str(HOOK)], cwd=clone, env=env, capture_output=True, text=True, timeout=120
    )
    assert done.returncode == 0
    assert done.stdout.strip() == ""


def test_veraendert_den_arbeitsstand_nicht(tmp_path: Path) -> None:
    """Der Hook meldet, er aktualisiert nicht — sonst waere er gefaehrlicher als
    der veraltete Klon, den er anzeigt."""
    clone = _world(tmp_path, behind=3)
    vorher = _git(clone, "rev-parse", "HEAD")
    branch_vorher = _git(clone, "rev-parse", "--abbrev-ref", "HEAD")

    run = _run_hook(clone)
    assert "3 Commits" in run.stdout

    assert _git(clone, "rev-parse", "HEAD") == vorher
    assert _git(clone, "rev-parse", "--abbrev-ref", "HEAD") == branch_vorher
    assert _git(clone, "status", "--porcelain") == ""


# --- Der Default-Branch wird ermittelt, nicht angenommen ----------------------


@pytest.mark.parametrize("default_branch", ["main", "master", "trunk"])
def test_ermittelt_den_default_branch_statt_main_anzunehmen(
    tmp_path: Path, default_branch: str
) -> None:
    """`openlex-mcp`, `swiss-courts-mcp` und `swisstopo-mcp` heissen ihn `master`.

    Ein fest verdrahtetes `main` liess dort schon einmal einen Branch 15 Commits
    alt werden, weil der Vergleich still ins Leere lief.
    """
    clone = _world(tmp_path, default_branch=default_branch, behind=2)
    run = _run_hook(clone)
    assert run.returncode == 0
    assert f"origin/{default_branch}" in run.stdout
    assert "2 Commits" in run.stdout


def test_raet_nicht_auf_main_wenn_der_default_branch_unbekannt_ist(tmp_path: Path) -> None:
    """Kein Name ermittelbar heisst schweigen, nicht `main` einsetzen.

    Der Upstream fuehrt hier ausgerechnet `main` und liegt zwei Commits vorn,
    verraet seinen HEAD aber nicht mehr, und der Klon hat sich nichts gemerkt.
    Ein Hook, der in dieser Lage `main` einsetzt, meldet zwei Commits — dieser
    schweigt. Damit haengt der Test an der Ermittlung, nicht am Zaehlen.

    Ein leerer Branchname darf ebenfalls nicht einfach durchfallen: `git fetch
    origin ""` faellt still auf den Remote-HEAD zurueck und endet mit 0, was
    wie ein aktueller Klon aussieht.
    """
    clone = _world(tmp_path, default_branch="main", behind=2)
    # symbolic-ref --delete, nicht update-ref -d: letzteres laesst den
    # symbolischen Ref stehen, und der Hook faende ueber den Fallback doch einen
    # Namen — der Test pruefte dann nichts.
    _git(clone, "symbolic-ref", "--delete", "refs/remotes/origin/HEAD")
    assert _run_hook_branch_hint(clone) is None, (
        "Vorbedingung: der Klon darf sich keinen Default-Branch gemerkt haben"
    )
    # Der Upstream verraet seinen HEAD nicht mehr: die Referenz zeigt ins Leere.
    (tmp_path / "upstream.git" / "HEAD").write_text("ref: refs/heads/gibt-es-nicht\n")

    run = _run_hook(clone)
    assert run.returncode == 0
    assert run.silent, f"unerwartete Ausgabe: {run.stdout!r}"


@braucht_posix
def test_leerer_branchname_faellt_nicht_durch(tmp_path: Path) -> None:
    """Der Fall, vor dem der `:?`-Schutz in CLAUDE.md warnt.

    Hier verrraet das Remote seinen Default-Branch nicht (kein `ref:` in
    `ls-remote --symref`), funktioniert sonst aber tadellos, und der Klon hat
    sich nichts gemerkt. Der Name ist also leer — und `git fetch origin ""`
    endet dann nicht etwa mit Fehler, sondern holt still den Remote-HEAD und
    gibt 0 zurueck. Wer den leeren Wert durchfallen laesst, meldet einen
    Rueckstand gegen einen Branch, dessen Namen niemand kennt.
    """
    clone = _world(tmp_path, behind=2)
    _git(clone, "symbolic-ref", "--delete", "refs/remotes/origin/HEAD")

    echtes_git = shutil.which("git")
    assert echtes_git is not None
    stubdir = tmp_path / "bin"
    stubdir.mkdir()
    stub = stubdir / "git"
    stub.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "ls-remote" ]; then\n'
        f'  "{echtes_git}" "$@" | grep -v "^ref:" || true\n'
        "  exit 0\n"
        "fi\n"
        f'exec "{echtes_git}" "$@"\n'
    )
    stub.chmod(0o755)

    env = _git_env()
    env["PATH"] = f"{stubdir}{os.pathsep}{env['PATH']}"
    env["CLAUDE_PROJECT_DIR"] = str(clone)
    done = subprocess.run(
        [SHELL, str(HOOK)], cwd=clone, env=env, capture_output=True, text=True, timeout=120
    )
    assert done.returncode == 0
    assert done.stdout.strip() == "", f"unerwartete Ausgabe: {done.stdout!r}"


# --- Die Shell-Auswahl selbst ------------------------------------------------


def _fake_shell(ordner: Path, name: str = "bash.exe") -> Path:
    ordner.mkdir(parents=True, exist_ok=True)
    pfad = ordner / name
    pfad.write_text("")
    return pfad


def test_shell_auswahl_uebergeht_den_wsl_starter(tmp_path: Path) -> None:
    """Das `bash.exe` in System32 startet WSL.

    Es sieht ein anderes Dateisystem und macht aus `C:\\Users\\...` nichts
    Brauchbares — beim Handtest kam dort `C:UsershayalAppDataLocalTemphook.sh`
    heraus. Wird es gewaehlt, sind die Tests rot ohne erkennbaren Grund.
    """
    system32 = tmp_path / "Windows" / "System32"
    wsl = _fake_shell(system32)
    git_sh = _fake_shell(tmp_path / "Git" / "bin", "sh.exe")

    gewaehlt = _waehle_shell([str(wsl), str(git_sh)], system32)
    assert gewaehlt == str(git_sh), "der WSL-Starter wurde nicht uebergangen"


def test_shell_auswahl_nimmt_den_ersten_brauchbaren(tmp_path: Path) -> None:
    erste = _fake_shell(tmp_path / "a", "sh.exe")
    zweite = _fake_shell(tmp_path / "b", "sh.exe")
    assert _waehle_shell([str(erste), str(zweite)], tmp_path / "System32") == str(erste)


def test_shell_auswahl_ueberspringt_fehlende_und_leere_eintraege(tmp_path: Path) -> None:
    """`shutil.which` liefert None, wenn nichts gefunden wird."""
    echt = _fake_shell(tmp_path / "git", "sh.exe")
    kandidaten = [None, str(tmp_path / "gibt-es-nicht.exe"), str(echt)]
    assert _waehle_shell(kandidaten, tmp_path / "System32") == str(echt)


def test_shell_auswahl_meldet_nichts_statt_zu_raten(tmp_path: Path) -> None:
    """Nur der WSL-Starter da heisst: keine brauchbare Shell.

    Dann muessen die Tests uebersprungen werden — mit Grund — und nicht mit
    einer Shell laufen, die den Hook nicht ausfuehren kann.
    """
    system32 = tmp_path / "System32"
    wsl = _fake_shell(system32)
    assert _waehle_shell([None, str(wsl)], system32) is None


def test_die_tests_laufen_hier_wirklich_und_werden_nicht_stillschweigend_uebersprungen() -> None:
    """Sonst haette das ganze Modul gruen ausgesehen, ohne etwas zu pruefen."""
    assert SHELL is not None
    assert Path(SHELL).is_file()


# --- Registrierung und Begruendung -------------------------------------------


def test_hook_ist_ausfuehrbar_eingecheckt() -> None:
    """Das Ausfuehrungsbit im git-Index, nicht im Dateisystem.

    `os.access(..., os.X_OK)` beantwortet die Frage auf Windows nicht — dort
    gibt es kein Exec-Bit, und der Aufruf meldet fuer jede vorhandene Datei
    Erfolg. Der Test waere dort gruen, ohne etwas zu pruefen. Was zaehlt, ist
    der Modus, mit dem die Datei eingecheckt ist: den tragen alle Klone.
    """
    assert HOOK.is_file()
    done = subprocess.run(
        ("git", "ls-files", "-s", "--", ".claude/hooks/session-start.sh"),
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    modus = done.stdout.split()[0] if done.stdout.split() else ""
    assert modus == "100755", (
        f"Modus im git-Index ist {modus!r}, erwartet '100755' — "
        "ohne Ausfuehrungsbit startet der Hook auf POSIX nie"
    )


def test_hook_ist_als_sessionstart_registriert() -> None:
    settings = json.loads(SETTINGS.read_text())
    eintraege = settings["hooks"]["SessionStart"]
    befehle = [h["command"] for gruppe in eintraege for h in gruppe["hooks"]]
    assert any("session-start.sh" in b for b in befehle)
    timeouts = [h.get("timeout") for gruppe in eintraege for h in gruppe["hooks"]]
    assert all(t is not None for t in timeouts), "aeusserer Riegel gegen Haenger fehlt"


def test_die_begruendung_steht_beim_hook() -> None:
    """Ohne den Grund wird die Meldung beim zweiten Mal weggeklickt."""
    text = HOOK_README.read_text()
    assert "3.8.2026" in text
    assert "master" in text
