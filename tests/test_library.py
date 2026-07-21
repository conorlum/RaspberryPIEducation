import base64

from app.library import load_library

EMPTY_STUB = """<?xml version="1.0" encoding="UTF-8" ?>
<library version="20110515">
</library>
"""

ONE_PIXEL_PNG_B64 = base64.b64encode(
    bytes.fromhex(
        "89504e470d0a1a0a0000000d4948445200000001000000010802000000907753"
        "de0000000c4944415478da6360606060000000050001a5f645400000000049454e44ae426082"
    )
).decode("ascii")


def test_missing_file_returns_empty_list(tmp_path):
    assert load_library(tmp_path / "does-not-exist.xml") == []


def test_empty_library_stub_returns_empty_list(tmp_path):
    library_xml = tmp_path / "library.xml"
    library_xml.write_text(EMPTY_STUB, encoding="utf-8")
    assert load_library(library_xml) == []


def test_parses_two_books_with_expected_fields(tmp_path):
    xml = f"""<?xml version="1.0" encoding="UTF-8" ?>
<library version="20110515">
  <book id="abc123" path="content/zim/wikipedia_en_octopus.zim" name="wikipedia_en_octopus"
        title="Wikipedia (Octopus)" description="All about octopuses" language="eng"
        tags="wikipedia;nature" articleCount="42"
        favicon="{ONE_PIXEL_PNG_B64}" faviconMimeType="image/png">
  </book>
  <book path="content/zim/minimal.zim">
  </book>
</library>
"""
    library_xml = tmp_path / "library.xml"
    library_xml.write_text(xml, encoding="utf-8")

    books = load_library(library_xml)
    assert len(books) == 2

    first = books[0]
    assert first.name == "wikipedia_en_octopus"
    assert first.title == "Wikipedia (Octopus)"
    assert first.description == "All about octopuses"
    assert first.language == "eng"
    assert first.tags == ["wikipedia", "nature"]
    assert first.article_count == 42
    assert first.favicon_data_uri == f"data:image/png;base64,{ONE_PIXEL_PNG_B64}"

    second = books[1]
    assert second.name == "minimal"  # falls back to path stem
    assert second.title == "minimal"  # falls back to name
    assert second.description == ""
    assert second.tags == []
    assert second.article_count is None
    assert second.favicon_data_uri is None


def test_malformed_favicon_data_yields_none_not_exception(tmp_path):
    xml = """<?xml version="1.0" encoding="UTF-8" ?>
<library version="20110515">
  <book id="abc123" name="broken" title="Broken" favicon="not-valid-base64!!"
        faviconMimeType="image/png">
  </book>
</library>
"""
    library_xml = tmp_path / "library.xml"
    library_xml.write_text(xml, encoding="utf-8")

    books = load_library(library_xml)
    assert len(books) == 1
    assert books[0].favicon_data_uri is None


def test_malformed_xml_returns_empty_list(tmp_path):
    library_xml = tmp_path / "library.xml"
    library_xml.write_text("this is not xml <<<", encoding="utf-8")
    assert load_library(library_xml) == []
