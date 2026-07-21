# MCP Audit Report — amtsblatt-mcp

**Run-ID:** `2026-07-20T212024-Z-amtsblatt-mcp` · **Skill-Version:** 1.0.0 · **Katalog-Checks:** 68 · **MCP-Spec-Baseline:** 2025-11-25
**Katalog-Hash:** `091f446b27965044ce658a1d5f4b2cabe2b0ab5661dcc1a53b6be8f1f2e093c0`
**Auditierter Commit:** `1a0a2b4` (main) + Remediation in dieser Session

---

## 1. Executive Summary

`amtsblatt-mcp` wurde gegen **46 anwendbare** von 68 Katalog-Checks geprüft. As-found: **7 Findings** (1 × high, 1 × critical-Severity, 5 × medium), davon **ein produktionsblockierendes** (SDK-001). Alle Blocker wurden in dieser Session behoben und verifiziert (Test-Suite 77 grün, ruff clean); es verbleiben **4 akzeptierte Medium-Findings** ohne Risiko für den Produktivbetrieb.

**Production-ready: JA** (nach Remediation — keine offenen critical/high Findings).

## 2. Profil-Snapshot

| Feld | Wert |
|---|---|
| Transport | dual (stdio + SSE) |
| SDK | Python (FastMCP, Pydantic v2) |
| Auth-Modell | API-Key (Bearer, nur SSE; stdio lokal) |
| Datenklasse | Public Open Data (amtsblattportal.ch) |
| Schreibzugriff | read-only |
| Deployment | local-stdio + cloud-fähig (Docker/SSE) |
| Datenquelle Schweiz | ja (SECO / Bund) |

## 3. Applicability

Anwendbar: **46 / 68**. Nicht anwendbar u.a. HITL (read-only, kein Sampling), OAuth-Checks (kein OAuth-Proxy), TypeScript-SDK-Checks.

| Kategorie | Anwendbar | Ergebnis (final) |
|---|---|---|
| ARCH | 11 | 9 pass · 2 partial (ARCH-008, ARCH-012) |
| SDK | 4 | 2 pass · 2 partial (SDK-002, SDK-003) |
| SEC | 17 | 17 pass |
| SCALE | 5 | 5 pass |
| OBS | 5 | 5 pass |
| OPS | 3 | 3 pass |
| CH | 1 | 1 pass |
| **Total** | **46** | **42 pass · 4 partial · 0 fail** |

## 4. Findings-Tabelle

| ID | Severity | Titel | As-found | Disposition |
|---|---|---|---|---|
| SDK-001 | high | Shared HTTP client / Lifespan | fail | ✅ remediated |
| SEC-016 | critical | 0.0.0.0-Binding (NeighborJack) | partial | ✅ remediated |
| SCALE-006 | medium | Container-Resource-Limits | partial | ✅ remediated |
| ARCH-008 | medium | Nur Tools-Primitive | partial | accepted-risk |
| ARCH-012 | medium | protocolVersion-Pin | partial | accepted-risk |
| SDK-002 | medium | Strukturierte Return-Types | partial | accepted-risk |
| SDK-003 | medium | Context-Injection | partial | accepted-risk |

Detail-Findings: siehe [`findings/`](findings/).

## 5. Remediation (in dieser Session angewandt)

| Finding | Fix | Evidenz |
|---|---|---|
| **SDK-001** (high, Blocker) | Shared `httpx.AsyncClient` (`_get_client`/`_close_client`) + FastMCP `lifespan`; `_get_json`/`_get_text`/`_probe_endpoint` reuse it | server.py; neue Tests `test_shared_client_is_reused_across_calls`, `test_reset_client_drops_the_shared_instance` |
| **SEC-016** (critical) | Default-Bind `127.0.0.1`, opt-in `MCP_HOST=0.0.0.0`; Container setzt es explizit | server.py:748; compose.yaml |
| **SCALE-006** (medium) | `mem_limit`/`cpus`/`pids_limit` ergänzt | compose.yaml |

Verifikation: `pytest -m "not live"` → **77 passed**, `ruff check` → clean.

## 6. Akzeptierte Medium-Findings (0.1.x)

ARCH-008 (tools-only), ARCH-012 (kein Spec-Pin — FastMCP verhandelt), SDK-002 (Markdown-first Returns, JSON optional), SDK-003 (kein `ctx` — strukturiertes Logging deckt Observability). Alle bewusste Design-Entscheidungen ohne Produktionsrisiko; Kandidaten für ein späteres Minor.

## 7. Besonders starke Punkte

- **SEC-019/SEC-020/SEC-021** — read-only by design (keine Lethal Trifecta), keine Injection-Primitive, Egress-Allow-List (frozenset) auf jedem Hop inkl. Redirects.
- **SEC-018** — Pydantic v2 `extra='forbid'` + Validatoren + Regex/Bounds auf jedem Input-Modell.
- **SEC-007** — gehärteter Container (non-root, read_only, cap_drop ALL, no-new-privileges).
- **CH-004 / Datenschutz** — fail-closed Green-Allow-List, kein Personen-Sucheinstieg, keine Content-Persistenz (revDSG); Attribution pro Response.
- **OBS-004** — stderr-Logging, stdout dem Protokoll vorbehalten.

## 8. Audit-Metadata

- Auditor: mcp-audit-skill v1.0.0 (automatisiert, Claude-gestützt)
- Datum: 2026-07-20 (UTC)
- Findings-Policy: `fail-or-partial`
- Single-Source-of-Truth: `summary.json` (as-found) / `summary-post.json` (nach Remediation)
- Gate: production_ready = true (nach Remediation), keine offenen critical/high Findings
