"""Strict input models — one per tool, `extra="forbid"` throughout.

Extracted from `server.py` for `ARCH-011`.

`SEC-018` is why these are Pydantic models rather than validated keyword
arguments: `strict=True` and `extra="forbid"` are model-level settings, so
without a `BaseModel` there is nothing to configure and the check could only ever
be `partial`.

`DetailedSearchInput` subclasses `SearchInput` deliberately — the aggregated tool
has to accept exactly the same query surface, or callers would have to learn two
dialects of the same search.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .constants import (
    CANTON_CODES,
    GAZETTE_MAX_DETAIL_N,
    GAZETTE_MAX_LIMIT,
    ResponseFormat,
    RubricClass,
)

# ---------------------------------------------------------------------------
# Input models
# ---------------------------------------------------------------------------


class SearchInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    keyword: str | None = Field(
        default=None,
        description=(
            "Volltext-Suchbegriff, z.B. 'Informatik', 'Zonenplan', 'Trambeschaffung'. "
            "Sucht über den Publikationstext, NICHT über Personennamen."
        ),
        min_length=2,
        max_length=200,
    )
    rubric: str | None = Field(
        default=None,
        description=(
            "Rubrik-Code, z.B. 'HR' (Handelsregister), 'OB-BS' (Beschaffung "
            "Basel-Stadt), 'RP-ZH' (Raumplanung Zürich). Nur freigegebene Rubriken "
            "sind zulässig — `gazette_list_rubrics` zeigt sie. Ohne Angabe wird über alle "
            "freigegebenen Rubriken gesucht."
        ),
        max_length=12,
    )
    sub_rubric: str | None = Field(
        default=None,
        description="Subrubrik-Code, z.B. 'HR01' oder 'AR-NW40'. Wird vorab validiert.",
        max_length=12,
    )
    canton: str | None = Field(
        default=None,
        description="Kantonskürzel, z.B. 'ZH'. Beispiel: 'BS'.",
        min_length=2,
        max_length=2,
    )
    date_start: str | None = Field(
        default=None,
        description="Zeitraum-Start (YYYY-MM-DD).",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
    )
    date_end: str | None = Field(
        default=None,
        description="Zeitraum-Ende (YYYY-MM-DD).",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
    )
    limit: int = Field(
        default=20,
        description="Maximale Anzahl Ergebnisse (1–100). Standard: 20.",
        ge=1,
        le=GAZETTE_MAX_LIMIT,
    )
    page: int = Field(
        default=0,
        description="Seitenzahl für Pagination, 0-basiert. Standard: 0.",
        ge=0,
    )
    language: str = Field(
        default="de",
        description="Bevorzugte Sprache für Titel und Deduplikation. Standard: 'de'.",
        pattern=r"^(de|fr|it|en)$",
    )
    only_language: bool = Field(
        default=False,
        description=(
            "Nur Publikationen in der unter `language` gewählten Sprache zurückgeben. "
            "Mehrsprachige Kantone (TI, teilweise AR) publizieren dieselbe "
            "Bekanntmachung je Sprache als eigenen Datensatz; True liefert genau "
            "eine Sprachfassung, kann aber Bekanntmachungen ausblenden, die es in "
            "dieser Sprache nicht gibt. Standard: False."
        ),
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Ausgabeformat: 'markdown' oder 'json'",
    )

    @field_validator("canton")
    @classmethod
    def validate_canton(cls, v: str | None) -> str | None:
        if v and v.upper() not in CANTON_CODES:
            raise ValueError(f"Ungültiges Kantonskürzel '{v}'. Gültig: {', '.join(CANTON_CODES)}")
        return v.upper() if v else v


class DetailedSearchInput(SearchInput):
    """`SearchInput` plus the fan-out bound for the aggregated tool.

    Inherits every filter and validator from `SearchInput` deliberately: the
    aggregated tool must accept exactly the same query surface, or callers would
    have to learn two dialects of the same search.
    """

    top_n: int = Field(
        default=3,
        description=(
            f"Wie viele der obersten Treffer im Volltext geliefert werden "
            f"(1–{GAZETTE_MAX_DETAIL_N}). Jeder kostet eine zusätzliche "
            "Upstream-Anfrage; sie laufen parallel."
        ),
        ge=1,
        le=GAZETTE_MAX_DETAIL_N,
    )


class ProcurementInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    keyword: str | None = Field(
        default=None,
        description=(
            "Freitext-Suchbegriff, z.B. 'Informatik', 'Schulmobiliar', 'Reinigung'. "
            "HINWEIS: Die Quelle kennt KEINE CPV-Codes — nur Volltextsuche."
        ),
        min_length=2,
        max_length=200,
    )
    canton: str | None = Field(
        default=None,
        description=(
            "Kantonskürzel, z.B. 'TI'. Beschaffungsrubriken gibt es nur für "
            "AR und TI (aktiv) sowie BS, BL, VS, ZG (inaktiv; ZG leer, BS/BL/VS "
            "nur Archiv). Andere Kantone — inklusive ZH — publizieren über "
            "simap.ch, nicht hier. Ohne Kanton wird über alle aktiven "
            "Beschaffungsrubriken gesucht."
        ),
        min_length=2,
        max_length=2,
    )
    date_start: str | None = Field(
        default=None,
        description="Zeitraum-Start (YYYY-MM-DD).",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
    )
    date_end: str | None = Field(
        default=None,
        description="Zeitraum-Ende (YYYY-MM-DD).",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
    )
    include_inactive: bool = Field(
        default=False,
        description=(
            "Auch inaktive Beschaffungsrubriken (BS, BL, VS) einbeziehen — nur "
            "historische Daten. Standard: False."
        ),
    )
    limit: int = Field(
        default=20,
        description="Maximale Anzahl Ergebnisse (1–100). Standard: 20.",
        ge=1,
        le=GAZETTE_MAX_LIMIT,
    )
    page: int = Field(default=0, description="Seitenzahl für Pagination, 0-basiert.", ge=0)
    language: str = Field(
        default="de",
        description="Bevorzugte Sprache. Standard: 'de'.",
        pattern=r"^(de|fr|it|en)$",
    )
    only_language: bool = Field(
        default=False,
        description=(
            "Nur Ausschreibungen in der unter `language` gewählten Sprache. "
            "Ticino publiziert überwiegend it/fr, Appenzell A.Rh. de/fr — je "
            "Sprache ein eigener Datensatz. True liefert genau eine Sprachfassung. "
            "Standard: False."
        ),
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Ausgabeformat: 'markdown' oder 'json'",
    )

    @field_validator("canton")
    @classmethod
    def validate_canton(cls, v: str | None) -> str | None:
        if v and v.upper() not in CANTON_CODES:
            raise ValueError(f"Ungültiges Kantonskürzel '{v}'. Gültig: {', '.join(CANTON_CODES)}")
        return v.upper() if v else v


class PublicationInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    id: str = Field(
        ...,
        description=(
            "Publikations-ID (UUID) aus `gazette_search_publications` oder "
            "`gazette_search_procurement`. Beispiel: 'fbf0ff9e-3e28-4e09-8a1e-32a7aa4cea8f'."
        ),
        min_length=8,
        max_length=64,
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Ausgabeformat: 'markdown' oder 'json'",
    )


class RubricsInput(BaseModel):
    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    language: str = Field(
        default="de",
        description="Sprache der Rubrik-Namen: 'de', 'fr', 'it', 'en'. Standard: 'de'.",
        pattern=r"^(de|fr|it|en)$",
    )
    rubric_class: RubricClass = Field(
        default=RubricClass.GREEN,
        description=(
            "'green' zeigt nur die erschlossenen Rubriken (Standard). 'all' zeigt "
            "die vollständige Taxonomie mit Ampel-Klassierung — blockierte Rubriken "
            "erscheinen mit Begründung, bleiben aber nicht durchsuchbar."
        ),
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Ausgabeformat: 'markdown' oder 'json'",
    )


class StatusInput(BaseModel):
    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Ausgabeformat: 'markdown' oder 'json'",
    )


# ---------------------------------------------------------------------------
