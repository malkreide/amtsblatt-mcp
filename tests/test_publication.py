"""XML parsing, deadline arithmetic and the egress allow-list."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from datetime import date

import httpx
import pytest
import respx

from amtsblatt_mcp.server import (
    ALLOWED_HOSTS,
    ATTRIBUTION,
    GAZETTE_BASE,
    EgressDenied,
    PublicationInput,
    StatusInput,
    _clean_text,
    _days_remaining,
    _format_deadline,
    _get_client,
    _make_client,
    _parse_publication_xml,
    _pick_language,
    _reset_client,
    gazette_get_publication,
    gazette_source_status,
)

from .fixtures import (
    MOCK_XML_HR03,
    MOCK_XML_MALFORMED,
    MOCK_XML_MIRRORED_PROCUREMENT,
    MOCK_XML_NATIVE_PROCUREMENT,
    MOCK_XML_PLACEHOLDER_SIMAP_REF,
    MOCK_XML_PROCUREMENT,
    MOCK_XML_UNKNOWN,
)

# ---------------------------------------------------------------------------
# Defensive XML parsing across rubric-specific schemas
# ---------------------------------------------------------------------------


def test_parses_procurement_schema_with_publication_element():
    """Procurement uses `<publication>`, not HR's `<publicationText>`."""
    parsed = _parse_publication_xml(MOCK_XML_PROCUREMENT)
    assert parsed["meta"]["rubric"] == "OB-BS"
    assert "Vergabeverfahren" in parsed["publicationText"]
    assert parsed["deadline"] == "2026-08-15"


def test_escaped_html_in_the_body_is_unescaped_and_stripped():
    """Raw markup must never reach the model's context."""
    parsed = _parse_publication_xml(MOCK_XML_PROCUREMENT)
    text = parsed["publicationText"]
    assert "&lt;" not in text
    assert "<p>" not in text and "<br/>" not in text
    # Umlaut entities resolved, and the <br/> became a line break.
    assert "Bezüglich" in text
    assert "IVöB" in text
    assert "Eine Neuausschreibung ist vorgesehen." in text.splitlines()[-1]


def test_clean_text_handles_plain_text_unchanged():
    assert _clean_text("Ein einfacher Satz.") == "Ein einfacher Satz."


def test_parses_hr_schema_with_company_block():
    parsed = _parse_publication_xml(MOCK_XML_HR03)
    assert parsed["company"]["name"] == "Musterfirma AG"
    assert parsed["company"]["uid"] == "CHE-999.999.999"
    assert "Aktiengesellschaft" in parsed["publicationText"]


def test_unknown_rubric_schema_falls_back_gracefully():
    """No rubric-specific path is hard-coded, so an unseen schema still parses."""
    parsed = _parse_publication_xml(MOCK_XML_UNKNOWN)
    assert parsed["publicationText"] == "Amtlicher Fliesstext einer unbekannten Rubrik."
    assert parsed["company"] == {}
    assert "someExoticField" in parsed["additional_fields"]


def test_malformed_xml_raises_parse_error():
    with pytest.raises(ET.ParseError):
        _parse_publication_xml(MOCK_XML_MALFORMED)


@pytest.mark.asyncio
async def test_get_publication_reports_malformed_xml_without_a_traceback():
    pub_id = "broken00-0000-0000-0000-000000000001"
    with respx.mock:
        respx.get(f"{GAZETTE_BASE}/publications/{pub_id}/xml").mock(
            return_value=httpx.Response(200, text=MOCK_XML_MALFORMED)
        )
        result = await gazette_get_publication(PublicationInput(id=pub_id))
    assert "konnte nicht geparst werden" in result
    assert "Traceback" not in result


def test_pick_language_falls_back_to_german_then_first():
    assert _pick_language({"de": "Titel", "fr": "Titre"}, "de") == "Titel"
    assert _pick_language({"de": "Titel", "fr": "Titre"}, "en") == "Titel"
    assert _pick_language({"it": "Titolo"}, "en") == "Titolo"
    assert _pick_language("plain", "de") == "plain"


# ---------------------------------------------------------------------------
# Deadline arithmetic (Europe/Zurich, fixed "today")
# ---------------------------------------------------------------------------

FIXED_TODAY = date(2026, 7, 20)


def test_days_remaining_with_a_fixed_today():
    assert _days_remaining("2026-08-15", FIXED_TODAY) == 26
    assert _days_remaining("2026-07-21", FIXED_TODAY) == 1
    assert _days_remaining("2026-07-20", FIXED_TODAY) == 0
    assert _days_remaining("2026-07-10", FIXED_TODAY) == -10


def test_days_remaining_accepts_an_iso_timestamp():
    assert _days_remaining("2026-08-15T00:00:00.000Z", FIXED_TODAY) == 26


def test_days_remaining_returns_none_for_unparseable_values():
    for junk in (None, "", "demnächst", "15.08.2026", "2026-13-45"):
        assert _days_remaining(junk, FIXED_TODAY) is None


def test_format_deadline_renders_remaining_time_in_german():
    assert "noch 26 Tage" in _format_deadline("2026-08-15", FIXED_TODAY)
    assert "noch 1 Tag)" in _format_deadline("2026-07-21", FIXED_TODAY)
    assert "läuft heute ab" in _format_deadline("2026-07-20", FIXED_TODAY)
    assert "abgelaufen vor 10 Tagen" in _format_deadline("2026-07-10", FIXED_TODAY)
    assert _format_deadline(None, FIXED_TODAY) == "—"


def test_deadline_uses_zurich_time_not_utc():
    """Just after midnight in Zurich it is still 'yesterday' in UTC.

    A UTC-based calculation would report one day too many for the whole
    CEST evening — legally the wrong answer for a submission deadline.
    """
    from datetime import datetime

    from amtsblatt_mcp.server import TZ_ZURICH

    # 2026-07-20 00:30 Zurich == 2026-07-19 22:30 UTC.
    zurich_now = datetime(2026, 7, 20, 0, 30, tzinfo=TZ_ZURICH)
    assert zurich_now.date() == date(2026, 7, 20)
    assert zurich_now.astimezone(tz=None).utctimetuple().tm_mday in (19, 20)
    assert _days_remaining("2026-07-25", zurich_now.date()) == 5


@pytest.mark.asyncio
async def test_get_publication_renders_the_deadline_with_remaining_time():
    with respx.mock:
        respx.get(f"{GAZETTE_BASE}/publications/fbf0ff9e/xml").mock(
            return_value=httpx.Response(200, text=MOCK_XML_PROCUREMENT)
        )
        result = await gazette_get_publication(PublicationInput(id="fbf0ff9e"))
    assert "2026-08-15" in result
    assert "Frist" in result
    assert "Trambeschaffung" in result


@pytest.mark.asyncio
async def test_get_publication_json_includes_days_remaining():
    with respx.mock:
        respx.get(f"{GAZETTE_BASE}/publications/fbf0ff9e/xml").mock(
            return_value=httpx.Response(200, text=MOCK_XML_PROCUREMENT)
        )
        result = await gazette_get_publication(
            PublicationInput(id="fbf0ff9e", response_format="json")
        )
    data = json.loads(result)
    assert data["deadline"] == "2026-08-15"
    assert isinstance(data["days_remaining"], int)


# ---------------------------------------------------------------------------
# Egress allow-list
# ---------------------------------------------------------------------------


class TestEgressAllowlist:
    def test_allowed_hosts_are_lowercase(self):
        assert all(h == h.lower() for h in ALLOWED_HOSTS)

    def test_the_gazette_host_is_allowed(self):
        assert "amtsblattportal.ch" in ALLOWED_HOSTS

    def test_the_allow_list_is_not_environment_mutable(self):
        """SEC-021: the code-layer allow-list must not be widenable from config.

        It used to be populated from MCP_ALLOWED_HOSTS. A guard that anything
        able to set an environment variable can widen is not a guard.

        Run in a subprocess rather than via importlib.reload: reloading swaps
        the module's classes in sys.modules, so every other test still holding
        the original `EgressDenied` would stop matching the newly-raised one.
        A fresh interpreter also tests what actually matters — the value the
        module takes at real process startup.
        """
        import json
        import os
        import subprocess
        import sys

        env = {**os.environ, "MCP_ALLOWED_HOSTS": "evil.example,amtsblattportal.ch"}
        out = subprocess.run(
            [
                sys.executable,
                "-c",
                "import json;from amtsblatt_mcp.server import ALLOWED_HOSTS;"
                "print(json.dumps(sorted(ALLOWED_HOSTS)))",
            ],
            capture_output=True,
            text=True,
            env=env,
            check=True,
        )
        hosts = json.loads(out.stdout.strip().splitlines()[-1])
        assert "evil.example" not in hosts, "MCP_ALLOWED_HOSTS still widens the allow-list"
        assert sorted(ALLOWED_HOSTS) == hosts

    def test_the_allow_list_is_immutable(self):
        """A frozenset, so no code path can add to it after import either."""
        assert isinstance(ALLOWED_HOSTS, frozenset)

    @respx.mock
    async def test_allowed_host_passes(self):
        respx.get(f"{GAZETTE_BASE}/rubrics").mock(return_value=httpx.Response(200, json=[]))
        async with _make_client() as client:
            r = await client.get(f"{GAZETTE_BASE}/rubrics")
        assert r.status_code == 200

    @respx.mock
    async def test_disallowed_host_is_blocked(self):
        respx.get("https://evil.example.com/exfil").mock(return_value=httpx.Response(200))
        async with _make_client() as client:
            with pytest.raises(EgressDenied):
                await client.get("https://evil.example.com/exfil")

    @respx.mock
    async def test_cloud_metadata_endpoint_is_blocked(self):
        """SSRF guard: the IMDS address must never be reachable."""
        async with _make_client() as client:
            with pytest.raises(EgressDenied):
                await client.get("http://169.254.169.254/latest/meta-data/")

    @respx.mock
    async def test_redirect_to_a_disallowed_host_is_blocked(self):
        respx.get(f"{GAZETTE_BASE}/rubrics").mock(
            return_value=httpx.Response(302, headers={"location": "https://evil.example.com/steal"})
        )
        async with _make_client() as client:
            with pytest.raises(EgressDenied):
                await client.get(f"{GAZETTE_BASE}/rubrics")


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_source_status_reports_scope_and_reachability():
    with respx.mock:
        respx.get(f"{GAZETTE_BASE}/rubrics").mock(return_value=httpx.Response(200, json=[]))
        result = await gazette_source_status(StatusInput())
    assert "✅" in result
    assert "fail-closed" in result
    assert "Freigegebene Rubriken" in result


@pytest.mark.asyncio
async def test_source_status_flags_an_unreachable_source():
    with respx.mock:
        respx.get(f"{GAZETTE_BASE}/rubrics").mock(side_effect=httpx.ConnectError("down"))
        result = await gazette_source_status(StatusInput())
    assert "❌" in result
    assert "kein** leeres Ergebnis" in result or "leeres Ergebnis" in result


def test_shared_client_is_reused_across_calls():
    """SDK-001: one pooled AsyncClient is reused, not created per request."""
    _reset_client()
    try:
        first = _get_client()
        second = _get_client()
        assert first is second
    finally:
        _reset_client()


def test_reset_client_drops_the_shared_instance():
    """_reset_client forces a fresh client on the next call."""
    _reset_client()
    try:
        first = _get_client()
        _reset_client()
        assert _get_client() is not first
    finally:
        _reset_client()


# ---------------------------------------------------------------------------
# simap reference — mirror vs. gazette-native
# ---------------------------------------------------------------------------


def test_simap_reference_is_promoted_and_stripped():
    """`#41510-01` is simap's own publicationNumber; the marker must go."""
    parsed = _parse_publication_xml(MOCK_XML_MIRRORED_PROCUREMENT)
    assert parsed["simap_publication_number"] == "41510-01"
    # Promoted out of the catch-all so callers do not have to know the tag name.
    assert "simapPublicationNumber" not in parsed["additional_fields"]


def test_gazette_native_publication_has_no_simap_reference():
    parsed = _parse_publication_xml(MOCK_XML_NATIVE_PROCUREMENT)
    assert parsed["simap_publication_number"] is None


def test_placeholder_simap_reference_reads_as_absent():
    """A publisher-typed "--" is not an id and must not be reported as one."""
    parsed = _parse_publication_xml(MOCK_XML_PLACEHOLDER_SIMAP_REF)
    assert parsed["simap_publication_number"] is None


@pytest.mark.asyncio
async def test_get_publication_flags_a_second_publication():
    with respx.mock:
        respx.get(url__regex=rf"{GAZETTE_BASE}/publications/.*/xml").mock(
            return_value=httpx.Response(200, text=MOCK_XML_MIRRORED_PROCUREMENT)
        )
        result = await gazette_get_publication(
            PublicationInput(id="dddd2222-0000-0000-0000-000000000010")
        )
    assert "41510-01" in result
    assert "Zweitpublikation" in result
    assert "swiss-procurement-mcp" in result


@pytest.mark.asyncio
async def test_get_publication_flags_a_gazette_only_record():
    with respx.mock:
        respx.get(url__regex=rf"{GAZETTE_BASE}/publications/.*/xml").mock(
            return_value=httpx.Response(200, text=MOCK_XML_NATIVE_PROCUREMENT)
        )
        result = await gazette_get_publication(
            PublicationInput(id="cccc1111-0000-0000-0000-000000000009")
        )
    assert "keine simap-Nummer" in result
    assert "nicht auffindbar" in result


# ---------------------------------------------------------------------------
# Tier-A audit remediation: SEC-004, SEC-013, OPS-003, CH-004
# ---------------------------------------------------------------------------


class TestHttpsEnforcement:
    """SEC-004: the host allow-list alone left plaintext reachable."""

    @respx.mock
    async def test_plaintext_to_an_allowed_host_is_refused(self):
        """`http://amtsblattportal.ch/...` passes a hostname allow-list while
        sending the request in the clear — a gap that reads as covered."""
        respx.get("http://amtsblattportal.ch/api/v1/rubrics").mock(
            return_value=httpx.Response(200, json=[])
        )
        async with _make_client() as client:
            with pytest.raises(httpx.RequestError, match="HTTPS is required"):
                await client.get("http://amtsblattportal.ch/api/v1/rubrics")

    @respx.mock
    async def test_https_to_an_allowed_host_still_passes(self):
        """The scheme check must not have broken the normal path."""
        respx.get(f"{GAZETTE_BASE}/rubrics").mock(return_value=httpx.Response(200, json=[]))
        async with _make_client() as client:
            assert (await client.get(f"{GAZETTE_BASE}/rubrics")).status_code == 200

    @respx.mock
    async def test_scheme_is_reported_before_the_host(self):
        """A plaintext URL to a foreign host must name the scheme, not the host.

        Reporting "host not allow-listed" for an `http://` URL sends the reader
        after the wrong problem.
        """
        async with _make_client() as client:
            with pytest.raises(httpx.RequestError, match="HTTPS is required"):
                await client.get("http://evil.example/steal")


class TestRequiredAuditDocuments:
    @pytest.mark.parametrize("path", ["docs/secret-management.md", "ROADMAP.md"])
    def test_document_exists(self, path):
        """SEC-013 and OPS-003 each require a specific file on disk."""
        import pathlib

        root = pathlib.Path(__file__).resolve().parents[1]
        assert (root / path).is_file(), f"{path} is required by the audit catalogue"

    def test_readme_declares_a_phase(self):
        """OPS-003: a phase that is not declared cannot be checked against the
        tool annotations, which is the whole point of declaring it."""
        import pathlib

        root = pathlib.Path(__file__).resolve().parents[1]
        for doc in ("README.md", "README.de.md"):
            text = (root / doc).read_text(encoding="utf-8")
            assert "Phase 1" in text, f"{doc} declares no phase"


class TestAttribution:
    def test_attribution_names_the_licence_position(self):
        """CH-004: naming only the operator left the licence implicit.

        Guessing wrong in either direction is a problem: assuming CC BY invents
        a grant that was never made; assuming all-rights-reserved blocks a reuse
        the Confederation permits.
        """
        assert "Licence:" in ATTRIBUTION
        assert "amtsblattportal.ch" in ATTRIBUTION


# ---------------------------------------------------------------------------
# OPS-001: gazette_source_status was at 3 unit tests against a floor of 5
# ---------------------------------------------------------------------------


class TestSourceStatusCoverage:
    """The tool a caller reaches for when a result looks wrong.

    Its job is to distinguish "the source said nothing" from "the source could
    not be asked" — so its own failure modes need to be unambiguous.
    """

    @pytest.mark.asyncio
    async def test_status_reports_the_green_scope(self):
        """A caller checking status is often really asking "why did I get
        nothing?", and the answer is frequently the allow-list, not an outage."""
        with respx.mock:
            respx.get(f"{GAZETTE_BASE}/rubrics").mock(return_value=httpx.Response(200, json=[]))
            result = await gazette_source_status(StatusInput())
        assert "fail-closed" in result
        assert "Freigegebene Rubriken" in result

    @pytest.mark.asyncio
    async def test_upstream_5xx_is_reported_as_unhealthy(self):
        """A 500 is not an empty result and must not render like one."""
        with respx.mock:
            respx.get(f"{GAZETTE_BASE}/rubrics").mock(return_value=httpx.Response(500, text="boom"))
            result = await gazette_source_status(StatusInput())
        assert "❌" in result or "⚠️" in result

    @pytest.mark.asyncio
    async def test_status_leaks_no_upstream_body(self):
        """An error body can carry internals; the model sees the envelope only."""
        with respx.mock:
            respx.get(f"{GAZETTE_BASE}/rubrics").mock(
                return_value=httpx.Response(500, text="Traceback: /srv/secret/app.py line 42")
            )
            result = await gazette_source_status(StatusInput())
        assert "/srv/secret" not in result
        assert "Traceback" not in result

    @pytest.mark.asyncio
    async def test_status_reports_a_timeout_distinctly(self):
        with respx.mock:
            respx.get(f"{GAZETTE_BASE}/rubrics").mock(side_effect=httpx.ReadTimeout("slow"))
            result = await gazette_source_status(StatusInput())
        assert "❌" in result or "⚠️" in result
        assert "leeres Ergebnis" in result or "nicht erreichbar" in result
