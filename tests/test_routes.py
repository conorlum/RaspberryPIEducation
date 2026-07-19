import pytest

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
