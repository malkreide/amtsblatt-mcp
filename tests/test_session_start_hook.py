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
        [str(HOOK)],
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


# --- Oberste Regel: blockiert nie --------------------------------------------


def test_detached_head_geht_still_durch(tmp_path: Path) -> None:
    clone = _world(tmp_path, behind=3)
    _git(clone, "checkout", "-q", "--detach", "HEAD")
    run = _run_hook(clone)
    assert run.returncode == 0
    assert run.silent, f"unerwartete Ausgabe: {run.stdout!r}"


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
        [str(HOOK)], cwd=clone, env=env, capture_output=True, text=True, timeout=120
    )
    assert done.returncode == 0
    assert done.stdout.strip() == "", f"unerwartete Ausgabe: {done.stdout!r}"
    assert done.stderr.strip() == "", f"unerwartetes Rauschen auf stderr: {done.stderr!r}"


def test_ohne_git_im_pfad_geht_still_durch(tmp_path: Path) -> None:
    clone = _world(tmp_path, behind=3)
    env = _git_env()
    env["PATH"] = str(tmp_path / "leer")
    env["CLAUDE_PROJECT_DIR"] = str(clone)
    done = subprocess.run(
        [str(HOOK)], cwd=clone, env=env, capture_output=True, text=True, timeout=120
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
        [str(HOOK)], cwd=clone, env=env, capture_output=True, text=True, timeout=120
    )
    assert done.returncode == 0
    assert done.stdout.strip() == "", f"unerwartete Ausgabe: {done.stdout!r}"


# --- Registrierung und Begruendung -------------------------------------------


def test_hook_ist_ausfuehrbar_eingecheckt() -> None:
    assert HOOK.is_file()
    assert os.access(HOOK, os.X_OK), "ohne Ausfuehrungsbit startet der Hook nie"


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
