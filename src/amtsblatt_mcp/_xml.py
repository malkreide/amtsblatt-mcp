"""XML parsing — the only route to a publication's full text.

Extracted from `server.py` for `ARCH-011`. The upstream serves publication
bodies as XML with inconsistent namespacing, so every lookup here is by *local*
name; `_localname` is why this module exists as a unit rather than inline.

Pure functions over strings and elements, with no network and no package
imports, so the parser can be exercised on captured fixtures alone.
"""

from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from typing import Any

# ---------------------------------------------------------------------------
# XML parsing (the only source of full publication text)
# ---------------------------------------------------------------------------


def _localname(tag: str) -> str:
    """Strip any XML namespace, returning the bare local element name."""
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else tag


_TAG_RE = re.compile(r"<[^>]+>")


def _clean_text(raw: str) -> str:
    """Unescape entity-encoded HTML and strip its markup.

    Procurement bodies arrive as HTML escaped into a text node
    (`&lt;p>Bezüglich…&lt;br/>`). Passing that through verbatim would put raw
    markup into the model's context, so it is unescaped, tags are dropped and
    block boundaries become newlines.
    """
    if "&lt;" in raw or "&amp;" in raw:
        raw = html.unescape(raw)
    raw = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>", "\n", raw)
    raw = _TAG_RE.sub("", raw)
    raw = html.unescape(raw)
    lines = [ln.strip() for ln in raw.splitlines()]
    return "\n".join(ln for ln in lines if ln).strip()


def _el_text(el: ET.Element) -> str:
    """Collapse an element's full text content, cleaned of inline markup."""
    return _clean_text("".join(el.itertext()).strip())


def _first_local(root: ET.Element, name: str) -> ET.Element | None:
    """First descendant (or self) whose local name matches — namespace-agnostic."""
    for c in root.iter():
        if _localname(c.tag) == name:
            return c
    return None


def _node_to_value(el: ET.Element) -> Any:
    """Leaf element -> text; container -> {localName: value} (best-effort)."""
    children = list(el)
    if not children:
        return _el_text(el)
    return {_localname(c.tag): _node_to_value(c) for c in children}


# Element names that carry the official body text, in preference order. The
# schema is per-subRubric: HR uses `publicationText`, procurement uses
# `publication`. Never hard-code a rubric-specific *path*.
_TEXT_ELEMENTS = ("publicationText", "publication", "text", "body")
# Element names that plausibly carry a submission deadline.
_DEADLINE_ELEMENTS = (
    "deadline",
    "submitDeadline",
    "offerDeadline",
    "applicationDeadline",
    "entryDeadline",
    "closingDate",
)


def _parse_publication_xml(xml_text: str) -> dict:
    """Defensively parse a single-publication XML.

    The schema is rubric-specific (`HR03-export`, `OB-BS70-export`, …) with a
    per-subRubric namespace whose middle path segment is the *tenant*, so no
    rubric-specific path is ever hard-coded. Only two things are reliably
    present and treated as mandatory: the meta block and a body-text element.
    Everything else lands best-effort in `additional_fields`. Malformed XML
    raises ET.ParseError to the caller.
    """
    root = ET.fromstring(xml_text)

    meta_el = _first_local(root, "meta")
    meta: dict[str, Any] = {}
    if meta_el is not None:
        for child in meta_el:
            meta[_localname(child.tag)] = _node_to_value(child)

    content_el = _first_local(root, "content")
    search_root = content_el if content_el is not None else root

    publication_text = None
    text_element_name = None
    for name in _TEXT_ELEMENTS:
        el = _first_local(search_root, name)
        if el is not None and _el_text(el):
            publication_text = _el_text(el)
            text_element_name = name
            break

    company: dict[str, Any] = {}
    comp_el = _first_local(search_root, "company")
    if comp_el is not None:
        for key in ("name", "uid", "seat", "legalForm", "address"):
            el = _first_local(comp_el, key)
            if el is not None:
                company[key] = _node_to_value(el)

    deadline = None
    for name in _DEADLINE_ELEMENTS:
        el = _first_local(search_root, name)
        if el is not None and _el_text(el):
            deadline = _el_text(el)
            break

    # Procurement publications that originate on simap.ch carry the simap
    # publication number, e.g. "#41510-01" (projectNumber-sequence). Its
    # presence is the only reliable way to tell a second publication from a
    # gazette-native one — measured over the whole 2026 OB-TI corpus, 92.1% of
    # records carry it and every record that lacks one sits in a sub-rubric
    # simap does not cover. Promoted out of `additional_fields` because that
    # distinction decides whether `swiss-procurement-mcp` has the same record.
    simap_ref = None
    simap_el = _first_local(search_root, "simapPublicationNumber")
    if simap_el is not None:
        simap_ref = _el_text(simap_el).lstrip("#").strip() or None
        # Some publishers fill the field with a placeholder rather than leaving
        # it out; treat that as absent rather than as an unresolvable id.
        if simap_ref in {"-", "--", "---", "n/a", "N/A"}:
            simap_ref = None

    additional: dict[str, Any] = {}
    if content_el is not None:
        for child in content_el:
            ln = _localname(child.tag)
            if ln in (text_element_name, "simapPublicationNumber"):
                continue
            additional[ln] = _node_to_value(child)

    return {
        "meta": meta,
        "publicationText": publication_text,
        "company": company,
        "deadline": deadline,
        "simap_publication_number": simap_ref,
        "additional_fields": additional,
    }


# ---------------------------------------------------------------------------
