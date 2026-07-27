# Security Policy

[🇩🇪 Deutsche Version](SECURITY.de.md)

## Supported Versions

| Version | Supported |
|---|---|
| `main` | ✅ |
| `0.1.x` | ✅ |
| `< 0.1` | ❌ |

## Reporting a Vulnerability

Please report privately via a
[GitHub Security Advisory](https://github.com/malkreide/amtsblatt-mcp/security/advisories/new)
rather than a public issue.

Include if possible: affected version, reproduction steps, the tool call or
request involved, and the impact you observed.

## Response Targets

- Acknowledgement: 5 working days
- Initial triage: 10 working days

## Scope

**In scope:** the published package, the Docker image, the GitHub workflows,
the green allow-list enforcement, the egress allow-list, and the SSE auth and
rate-limit middleware.

**Out of scope:** the behaviour of amtsblattportal.ch itself; forks with the
allow-list or authentication removed; findings in dependencies without a
demonstrated impact on this server.

## Data-protection findings are security findings

A defect that lets a blocked rubric be queried — or that leaks content from a
blocked rubric into a response — is a **vulnerability**, not a bug report.
Please use the private advisory channel for it. Concretely, report any of:

- A rubric outside `GREEN_RUBRICS` reaching the upstream query string.
- `gazette_get_publication` rendering content from a rubric that is not green.
- A tool signature accepting a person-identifying parameter.
- A refusal message that discloses a circumvention.

## Hardening Notes for Operators

1. **Put a gateway in front of the SSE transport.** The built-in bearer auth and
   rate limit are single-instance only; the rate-limit buckets are held in
   process memory and are not shared or garbage-collected across instances.
2. **Restrict egress at the network layer too.** `MCP_ALLOWED_HOSTS` is a
   defence-in-depth measure inside the process, not a substitute for an egress
   firewall. Note that setting it *replaces* the default entirely — it must
   include `amtsblattportal.ch`.
3. **Rotate `MCP_API_KEY`** and never bake it into an image.
4. **Ship the JSON logs to your SIEM** and alert on `auth_failed`,
   `rate_limited`, `egress_denied`, `green_gate_violation` and
   `blocked_publication_requested`. The last two mean something tried to reach a
   rubric the server does not serve.
5. **Do not persist responses.** Publications carry statutory deletion periods;
   the server deliberately keeps no content cache, and downstream storage would
   undo that.

---

## Lethal-trifecta assessment (SEC-019)

The "lethal trifecta" is the dangerous combination of (1) access to private
data, (2) exposure to untrusted content, and (3) the ability to exfiltrate. A
server holding all three can be steered by injected content into reading
something sensitive and sending it somewhere. This server is assessed leg by
leg rather than declared safe.

| Leg | Present? | Why |
|---|---|---|
| Access to private / sensitive data | **No, by construction** | The gazette *corpus* contains personal data — bankruptcies, debt enforcement, inheritance, civil status, court summonses, building applications. None of it is reachable: those rubrics are not indexed, and a request for one returns an explanation instead of data. The green allow-list is enforced before the request and re-checked after the fetch. |
| Exposure to untrusted content | **Partial** | Tool results contain upstream publication text, which the model ingests. It is official gazette text published by Swiss authorities, not attacker-chosen private content — but it is not authored by us, so it is treated as untrusted input. |
| Ability to exfiltrate | **No** | Egress is restricted to `amtsblattportal.ch` by a `frozenset` allow-list checked before every request (`EgressDenied`). No write endpoints are wrapped, no filesystem tool exists, and no user-controlled value reaches the host component of a URL. |

**At most one leg is present, and it is the weakest one.** Injected text in a
publication could at worst influence the model's summary of that publication;
it has nowhere to send anything and nothing sensitive to read.

### What would change this assessment

Each of these would need a fresh assessment before shipping:

- Indexing any red rubric, or relaxing the post-fetch green gate — that turns
  leg 1 on.
- Adding a second upstream host, or letting any user input reach a URL host —
  that turns leg 3 on.
- Adding a write, filesystem or email tool — leg 3 outright.
- Adding sampling (`ctx.sample`), which would let upstream text steer a
  model call rather than only be summarised by one.

### Relationship to the companion server

`swiss-procurement-mcp` carries the same assessment with one difference: it has
no personal-data rubrics to exclude in the first place, so its leg 1 is absent
by nature rather than by an enforced allow-list. Here the allow-list *is* the
control, which is why `tests/test_allowlist.py` runs as its own CI job.
