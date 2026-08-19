#!/bin/sh
# SessionStart-Hook: meldet, wie viele Commits der ausgecheckte Stand hinter
# origin/<Default-Branch> liegt.
#
# WARUM (Vorfall 3.8.2026): ein veralteter Klon hat zweimal eine rote CI
# erzeugt, deren Ursache nicht im Diff stand — die fehlenden Commits waren
# jeweils genau die, die das Gate einfuehrten, an dem der Branch scheiterte.
# Die Pruefung kostet eine Sekunde und ersetzt eine Fehlersuche in den
# falschen Dateien.
#
# OBERSTE REGEL: dieser Hook blockiert die Session nie. Kein Netz, kein
# Remote, flatterndes DNS, kaputte Credentials, fehlendes git — jeder Fall
# geht still durch (Exit 0, keine Ausgabe). Ein Hook, der bei Netzproblemen
# die Arbeit anhaelt, wird nach dem zweiten Mal abgeschaltet und schuetzt
# danach gar nichts. Ausgabe gibt es nur, wenn wirklich Commits fehlen;
# bei 0 schweigt er.
#
# Absichtlich KEIN `set -e`: ein unerwarteter Rueckgabewert darf den Hook
# nicht mit Fehler beenden. Der Ablauf steckt in check(), deren Fehler
# verworfen werden; die letzte Zeile ist `exit 0`.

# Gesamtbudget in Sekunden, aufgeteilt auf die beiden Netzschritte.
LS_REMOTE_TIMEOUT=3
FETCH_TIMEOUT=5

# Git darf unter keinen Umstaenden interaktiv nachfragen — ein Prompt waere
# genau das Haengen am Sessionstart, das hier verhindert werden soll.
GIT_TERMINAL_PROMPT=0
GIT_ASKPASS=echo
SSH_ASKPASS=echo
SSH_ASKPASS_REQUIRE=never
export GIT_TERMINAL_PROMPT GIT_ASKPASS SSH_ASKPASS SSH_ASKPASS_REQUIRE

# BatchMode nur setzen, wenn der Nutzer nichts Eigenes vorgibt: GIT_SSH_COMMAND
# schlaegt core.sshCommand, wir wuerden sonst eine bewusste Konfiguration
# ueberstimmen.
if [ -z "${GIT_SSH_COMMAND:-}" ] &&
   [ -z "$(git config --get core.sshCommand 2>/dev/null)" ]; then
  GIT_SSH_COMMAND='ssh -oBatchMode=yes -oConnectTimeout=3'
  export GIT_SSH_COMMAND
fi

# `timeout` ist nicht ueberall vorhanden (macOS ohne coreutils). Fallback:
# Kommando im Hintergrund starten und nach Ablauf abschiessen.
run_limited() {
  limit=$1
  shift
  if command -v timeout >/dev/null 2>&1; then
    timeout "$limit" "$@"
    return $?
  fi
  if command -v gtimeout >/dev/null 2>&1; then
    gtimeout "$limit" "$@"
    return $?
  fi
  "$@" &
  limited_pid=$!
  waited=0
  while [ "$waited" -lt "$limit" ]; do
    kill -0 "$limited_pid" 2>/dev/null || break
    sleep 1
    waited=$((waited + 1))
  done
  if kill -0 "$limited_pid" 2>/dev/null; then
    kill -TERM "$limited_pid" 2>/dev/null
    kill -KILL "$limited_pid" 2>/dev/null
    wait "$limited_pid" 2>/dev/null
    return 124
  fi
  wait "$limited_pid" 2>/dev/null
  return $?
}

# Default-Branch ermitteln, nicht als "main" annehmen: drei Server im
# Portfolio heissen ihn `master`, und genau diese Annahme hat schon einmal
# einen Branch 15 Commits alt werden lassen.
resolve_default_branch() {
  branch=$(run_limited "$LS_REMOTE_TIMEOUT" git ls-remote --symref origin HEAD 2>/dev/null |
    sed -n 's|^ref: refs/heads/\([^[:space:]]*\)[[:space:]].*|\1|p' |
    head -n 1)
  if [ -z "$branch" ]; then
    # Fallback ohne Netz: was der Klon sich beim Klonen gemerkt hat.
    branch=$(git symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>/dev/null |
      sed -n 's|^origin/||p')
  fi
  # Bewusst ohne eigene Leer-Pruefung: die steht in check(), an genau einer
  # Stelle. Doppelt gefuehrt waere eine der beiden toter Code — und eine
  # Zusicherung, die keine Gegenprobe widerlegen kann, ist keine.
  printf '%s\n' "$branch"
}

check() {
  command -v git >/dev/null 2>&1 || return 0
  [ "$(git rev-parse --is-inside-work-tree 2>/dev/null)" = "true" ] || return 0

  git config --get remote.origin.url >/dev/null 2>&1 || return 0

  # Leerer Wert darf nicht durchfallen: `git fetch origin ""` faellt sonst
  # still auf den Remote-HEAD zurueck, endet mit 0 und meldet einen Rueckstand
  # gegen einen Branch, dessen Namen niemand kennt.
  default_branch=$(resolve_default_branch)
  [ -n "$default_branch" ] || return 0

  run_limited "$FETCH_TIMEOUT" git -c gc.auto=0 fetch --quiet --no-tags \
    origin "$default_branch" >/dev/null 2>&1 || return 0

  target="refs/remotes/origin/$default_branch"
  git rev-parse --verify --quiet "$target" >/dev/null 2>&1 || target=FETCH_HEAD
  git rev-parse --verify --quiet "$target" >/dev/null 2>&1 || return 0

  behind=$(git rev-list --count "HEAD..$target" 2>/dev/null)
  case "$behind" in
    '' | *[!0-9]*) return 0 ;;
    0) return 0 ;;
  esac

  if [ "$behind" = 1 ]; then
    commits='1 Commit'
  else
    commits="$behind Commits"
  fi
  printf '%s\n' "Klon-Aktualitaet: dieser Stand liegt $commits hinter origin/$default_branch."
  # Bei detached HEAD wird bewusst mitgezaehlt. Der Hinweis darauf gehoert
  # aber dazu: `git pull` laesst den Stand dort detached, und wer den
  # Rueckstand sieht, ohne zu wissen, dass er auf keinem Branch steht, sucht
  # den naechsten Fehler an der falschen Stelle.
  if git symbolic-ref --quiet HEAD >/dev/null 2>&1; then
    printf '%s\n' "Vor der Arbeit aktualisieren, z. B.: git pull --ff-only origin $default_branch"
  else
    printf '%s\n' "HEAD ist detached (kein Branch). Zum Aufholen z. B.: git checkout $default_branch && git pull --ff-only origin $default_branch"
  fi
  printf '%s\n' "Grund: ein veralteter Klon erzeugt eine rote CI, deren Ursache nicht im Diff steht (Vorfall 3.8.2026) — die fehlenden Commits sind oft genau die, die das Gate einfuehren, an dem der Branch scheitert."
}

check 2>/dev/null || true
exit 0
