import base64
import binascii
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

_TAG_SPLIT_RE = re.compile(r"[;,]")

_LANGUAGE_NAMES = {
    "spa": "Español",
    "eng": "Inglés",
}


@dataclass
class Book:
    name: str
    title: str
    description: str
    language: str
    tags: list = field(default_factory=list)
    article_count: int = None
    favicon_data_uri: str = None


def load_library(library_xml_path):
    """Parse content/library.xml into Book objects.

    Defensive by design: there's no real library.xml sample in this repo and
    kiwix-tools' attribute set/naming isn't guaranteed across versions. Any
    of missing file, empty <library/>, malformed XML, or missing/renamed
    attributes must degrade to sane defaults rather than raising.
    """
    path = Path(library_xml_path)
    if not path.is_file():
        return []
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        return []
    books = [_parse_book(el) for el in root.findall("book")]
    _disambiguate_titles(books)
    return books


def _disambiguate_titles(books):
    """Two ZIMs can share the exact same title metadata (e.g. Wikipedia ES/EN
    both report "Wikipedia") - append the language so /library cards and
    /search's book-grouping headers (both keyed on Book.title) can tell them
    apart, instead of a student clicking a "Wikipedia" result and silently
    landing on the wrong language.
    """
    counts = {}
    for book in books:
        key = book.title.lower()
        counts[key] = counts.get(key, 0) + 1
    for book in books:
        if counts[book.title.lower()] > 1 and book.language:
            primary = book.language.split(",")[0].strip()
            name = _LANGUAGE_NAMES.get(primary, primary)
            book.title = f"{book.title} ({name})"


def _parse_book(el):
    attrs = el.attrib
    # kiwix-serve routes /content, /suggest, /viewer etc. by the ZIM's
    # filename stem (confirmed against a real kiwix-serve instance), not by
    # the `name` metadata attribute - the two can differ (e.g. library.xml's
    # name="wikipedia_en_all" for a file actually served as
    # "wikipedia_en_all_mini_2026-06"). The filename stem must come first.
    name = (
        Path(attrs.get("path", "")).stem
        or attrs.get("name")
        or attrs.get("id")
        or "unknown"
    )
    title = attrs.get("title") or attrs.get("name") or name
    tags_raw = attrs.get("tags", "")
    tags = [t.strip() for t in _TAG_SPLIT_RE.split(tags_raw) if t.strip()]

    return Book(
        name=name,
        title=title,
        description=attrs.get("description", ""),
        language=attrs.get("language", ""),
        tags=tags,
        article_count=_safe_int(attrs.get("articleCount")),
        favicon_data_uri=_build_favicon_data_uri(attrs),
    )


def _safe_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _build_favicon_data_uri(attrs):
    # Attribute name has varied across kiwix-tools versions; try known aliases.
    favicon_b64 = attrs.get("favicon") or attrs.get("faviconData")
    if not favicon_b64:
        return None
    mime = attrs.get("faviconMimeType") or "image/png"
    try:
        base64.b64decode(favicon_b64, validate=True)
    except (binascii.Error, ValueError):
        return None  # never emit a broken <img src> for bad/partial data
    return f"data:{mime};base64,{favicon_b64}"
