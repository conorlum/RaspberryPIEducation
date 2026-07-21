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
    assert b"/kiwix/viewer#wikipedia_en_octopus" in response.data


def test_library_route_no_broken_img_without_favicon(client, tmp_path):
    library_xml = tmp_path / "library.xml"
    library_xml.write_text(SAMPLE_LIBRARY_XML, encoding="utf-8")
    client.application.config["LIBRARY_XML"] = str(library_xml)

    response = client.get("/library")

    assert b"<img" not in response.data


def test_search_suggest_empty_query_returns_no_groups(client, monkeypatch):
    def _boom(*args, **kwargs):
        raise AssertionError("suggest() should not be called for an empty query")

    monkeypatch.setattr(routes, "suggest", _boom)

    response = client.get("/api/search-suggest?q=")

    assert response.status_code == 200
    assert json.loads(response.data) == {"groups": []}


def test_search_suggest_groups_results_per_book(client, tmp_path, monkeypatch):
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
        "groups": [
            {
                "book_title": "Wikipedia (Octopus)",
                "articles": [
                    {"title": "Octopus", "url": "/kiwix/viewer#wikipedia_en_octopus/A/Octopus"}
                ],
            }
        ]
    }


def test_search_suggest_omits_books_with_no_results(client, tmp_path, monkeypatch):
    library_xml = tmp_path / "library.xml"
    library_xml.write_text(SAMPLE_LIBRARY_XML, encoding="utf-8")
    client.application.config["LIBRARY_XML"] = str(library_xml)

    monkeypatch.setattr(routes, "suggest", lambda base_url, book_name, term, count: [])

    response = client.get("/api/search-suggest?q=octopus")

    assert json.loads(response.data) == {"groups": []}
