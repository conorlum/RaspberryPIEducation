import json

import pytest

import app.routes as routes
from app.app import create_app


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_index_renders(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"RACHEL" in response.data


def test_index_shows_empty_state_without_content(client):
    response = client.get("/")
    assert b"No content installed yet" in response.data


@pytest.mark.parametrize(
    "path",
    [
        "/generate_204",
        "/gen_204",
        "/hotspot-detect.html",
        "/library/test/success.html",
        "/connecttest.txt",
        "/ncsi.txt",
    ],
)
def test_captive_portal_probes_redirect_home(client, path):
    response = client.get(path)
    assert response.status_code == 302
    assert response.headers["Location"] == "/"


def test_unmatched_path_redirects_home(client):
    response = client.get("/some/random/path")
    assert response.status_code == 302
    assert response.headers["Location"] == "/"


def test_index_links_to_library_route_when_content_present(client, tmp_path):
    (tmp_path / "demo.zim").touch()
    client.application.config["CONTENT_DIR"] = str(tmp_path)

    response = client.get("/")

    assert b'href="/library"' in response.data
    assert b'href="/kiwix/"' not in response.data


def test_library_route_empty_state(client):
    response = client.get("/library")
    assert response.status_code == 200
    assert b"No content installed yet" in response.data


SAMPLE_LIBRARY_XML = """<?xml version="1.0" encoding="UTF-8" ?>
<library version="20110515">
  <book id="abc123" name="wikipedia_en_octopus" title="Wikipedia (Octopus)"
        description="All about octopuses" language="eng" articleCount="42">
  </book>
</library>
"""


def test_library_route_renders_book_card(client, tmp_path):
    library_xml = tmp_path / "library.xml"
    library_xml.write_text(SAMPLE_LIBRARY_XML, encoding="utf-8")
    client.application.config["LIBRARY_XML"] = str(library_xml)

    response = client.get("/library")

    assert response.status_code == 200
    assert b"Wikipedia (Octopus)" in response.data
    assert b"/kiwix/content/wikipedia_en_octopus" in response.data


def test_library_route_renders_search_this_book_link(client, tmp_path):
    library_xml = tmp_path / "library.xml"
    library_xml.write_text(SAMPLE_LIBRARY_XML, encoding="utf-8")
    client.application.config["LIBRARY_XML"] = str(library_xml)

    response = client.get("/library")

    assert b"/search?book=wikipedia_en_octopus" in response.data


def test_library_route_no_broken_img_without_favicon(client, tmp_path):
    library_xml = tmp_path / "library.xml"
    library_xml.write_text(SAMPLE_LIBRARY_XML, encoding="utf-8")
    client.application.config["LIBRARY_XML"] = str(library_xml)

    response = client.get("/library")

    assert b"<img" not in response.data


def test_search_route_empty_state(client):
    response = client.get("/search")
    assert response.status_code == 200
    assert b"No content installed yet" in response.data


def test_search_route_renders_input_and_browse_link(client, tmp_path):
    library_xml = tmp_path / "library.xml"
    library_xml.write_text(SAMPLE_LIBRARY_XML, encoding="utf-8")
    client.application.config["LIBRARY_XML"] = str(library_xml)

    response = client.get("/search")

    assert response.status_code == 200
    assert b'id="search-input"' in response.data
    assert b'href="/library"' in response.data
    assert b'id="search-book"' in response.data
    assert b'value="wikipedia_en_octopus"' in response.data


def test_search_route_preselects_book_from_query_param(client, tmp_path):
    library_xml = tmp_path / "library.xml"
    library_xml.write_text(SAMPLE_LIBRARY_XML, encoding="utf-8")
    client.application.config["LIBRARY_XML"] = str(library_xml)

    response = client.get("/search?book=wikipedia_en_octopus")

    assert b'value="wikipedia_en_octopus" selected' in response.data


def test_search_suggest_empty_query_returns_no_results(client, monkeypatch):
    def _boom(*args, **kwargs):
        raise AssertionError("suggest() should not be called for an empty query")

    monkeypatch.setattr(routes, "suggest", _boom)

    response = client.get("/api/search-suggest?q=")

    assert response.status_code == 200
    assert json.loads(response.data) == {"results": []}


def test_search_suggest_returns_results_per_book(client, tmp_path, monkeypatch):
    library_xml = tmp_path / "library.xml"
    library_xml.write_text(SAMPLE_LIBRARY_XML, encoding="utf-8")
    client.application.config["LIBRARY_XML"] = str(library_xml)

    monkeypatch.setattr(
        routes,
        "suggest",
        lambda base_url, book_name, term, count: [{"title": "Octopus", "path": "A/Octopus"}],
    )

    response = client.get("/api/search-suggest?q=octopus")
    data = json.loads(response.data)

    assert data == {
        "results": [
            {
                "book_title": "Wikipedia (Octopus)",
                "title": "Octopus",
                "url": "/kiwix/content/wikipedia_en_octopus/A/Octopus",
            }
        ]
    }


def test_search_suggest_book_filter_queries_only_that_book(client, tmp_path, monkeypatch):
    library_xml = tmp_path / "library.xml"
    library_xml.write_text(PRIORITY_AND_OTHER_LIBRARY_XML, encoding="utf-8")
    client.application.config["LIBRARY_XML"] = str(library_xml)

    queried_books = []

    def _suggest(base_url, book_name, term, count):
        queried_books.append(book_name)
        if book_name == "other_book_a":
            return [
                {"title": "A 1", "path": "a1"},
                {"title": "A 2", "path": "a2"},
            ]
        return []

    monkeypatch.setattr(routes, "suggest", _suggest)

    response = client.get("/api/search-suggest?q=x&book=other_book_a")
    data = json.loads(response.data)

    # Only the requested book is queried at all (not every installed book),
    # and its own result order is preserved rather than run through the
    # priority-tier interleaving used for whole-library searches.
    assert queried_books == ["other_book_a"]
    assert [item["title"] for item in data["results"]] == ["A 1", "A 2"]


def test_search_suggest_unknown_book_filter_returns_no_results(client, tmp_path, monkeypatch):
    library_xml = tmp_path / "library.xml"
    library_xml.write_text(SAMPLE_LIBRARY_XML, encoding="utf-8")
    client.application.config["LIBRARY_XML"] = str(library_xml)

    def _boom(*args, **kwargs):
        raise AssertionError("suggest() should not be called for an unknown book filter")

    monkeypatch.setattr(routes, "suggest", _boom)

    response = client.get("/api/search-suggest?q=octopus&book=does-not-exist")

    assert json.loads(response.data) == {"results": []}


def test_search_suggest_omits_books_with_no_results(client, tmp_path, monkeypatch):
    library_xml = tmp_path / "library.xml"
    library_xml.write_text(SAMPLE_LIBRARY_XML, encoding="utf-8")
    client.application.config["LIBRARY_XML"] = str(library_xml)

    monkeypatch.setattr(routes, "suggest", lambda base_url, book_name, term, count: [])

    response = client.get("/api/search-suggest?q=octopus")

    assert json.loads(response.data) == {"results": []}


PRIORITY_AND_OTHER_LIBRARY_XML = """<?xml version="1.0" encoding="UTF-8" ?>
<library version="20110515">
  <book id="a" name="khanacademy_es_test" title="Khan Academy" language="spa" articleCount="1">
  </book>
  <book id="b" name="other_book_a" title="Other A" language="spa" articleCount="1">
  </book>
  <book id="c" name="other_book_b" title="Other B" language="spa" articleCount="1">
  </book>
</library>
"""


def test_search_suggest_caps_priority_books_before_others(client, tmp_path, monkeypatch):
    library_xml = tmp_path / "library.xml"
    library_xml.write_text(PRIORITY_AND_OTHER_LIBRARY_XML, encoding="utf-8")
    client.application.config["LIBRARY_XML"] = str(library_xml)

    by_book = {
        "khanacademy_es_test": [
            {"title": "Khan 1", "path": "k1"},
            {"title": "Khan 2", "path": "k2"},
            {"title": "Khan 3", "path": "k3"},
        ],
        "other_book_a": [
            {"title": "A 1", "path": "a1"},
            {"title": "A 2", "path": "a2"},
        ],
        "other_book_b": [{"title": "B 1", "path": "b1"}],
    }
    monkeypatch.setattr(
        routes, "suggest", lambda base_url, book_name, term, count: by_book[book_name]
    )

    response = client.get("/api/search-suggest?q=x")
    titles = [item["title"] for item in json.loads(response.data)["results"]]

    # Khan Academy (priority) contributes at most 2 results, both before any
    # non-priority book's results appear; its 3rd result is never included.
    # The two non-priority books are then round-robined.
    assert titles == ["Khan 1", "Khan 2", "A 1", "B 1", "A 2"]


LIBRARY_ORDER_XML = """<?xml version="1.0" encoding="UTF-8" ?>
<library version="20110515">
  <book id="a" name="zzz_book" title="Zebra Books" language="spa" articleCount="1">
  </book>
  <book id="b" name="khanacademy_es_test" title="Khan Academy" language="spa" articleCount="1">
  </book>
  <book id="c" name="aaa_book" title="Aardvark Facts" language="spa" articleCount="1">
  </book>
</library>
"""


def test_library_route_orders_priority_books_then_alphabetical(client, tmp_path):
    library_xml = tmp_path / "library.xml"
    library_xml.write_text(LIBRARY_ORDER_XML, encoding="utf-8")
    client.application.config["LIBRARY_XML"] = str(library_xml)

    response = client.get("/library")
    body = response.data.decode("utf-8")

    # Document order is Zebra, Khan, Aardvark - the rendered order should be
    # the priority book first (regardless of its position in the XML), then
    # the two non-priority books alphabetically by title, not document order.
    khan_pos = body.index("Khan Academy")
    aardvark_pos = body.index("Aardvark Facts")
    zebra_pos = body.index("Zebra Books")
    assert khan_pos < aardvark_pos < zebra_pos
