import io
import json
import urllib.request
from urllib.error import URLError

import pytest

from app.kiwix_client import suggest


class _FakeResponse:
    def __init__(self, payload):
        self._buf = io.BytesIO(json.dumps(payload).encode("utf-8"))

    def read(self, *args, **kwargs):
        return self._buf.read(*args, **kwargs)

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


def test_empty_term_returns_empty_without_request(monkeypatch):
    def _boom(*args, **kwargs):
        raise AssertionError("urlopen should not be called for an empty term")

    monkeypatch.setattr(urllib.request, "urlopen", _boom)
    assert suggest("http://127.0.0.1:8080", "wikipedia", "   ", 5) == []


def test_parses_results_and_strips_html_tags(monkeypatch):
    payload = [
        {"value": "<b>Octopus</b>", "label": "<b>Octopus</b> (Cephalopoda)", "kind": "path", "path": "A/Octopus"},
        {"value": "Octopus wrestling", "kind": "path", "path": "A/Octopus_wrestling"},
    ]
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: _FakeResponse(payload))

    results = suggest("http://127.0.0.1:8080", "wikipedia", "octopus", 5)

    assert results == [
        {"title": "Octopus", "path": "A/Octopus"},
        {"title": "Octopus wrestling", "path": "A/Octopus_wrestling"},
    ]


def test_pattern_kind_entries_are_excluded(monkeypatch):
    payload = [
        {"value": "octopus", "kind": "pattern", "path": None},
        {"value": "Octopus", "kind": "path", "path": "A/Octopus"},
    ]
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: _FakeResponse(payload))

    results = suggest("http://127.0.0.1:8080", "wikipedia", "octopus", 5)

    assert results == [{"title": "Octopus", "path": "A/Octopus"}]


def test_network_error_returns_empty_list(monkeypatch):
    def _raise(*args, **kwargs):
        raise URLError("connection refused")

    monkeypatch.setattr(urllib.request, "urlopen", _raise)
    assert suggest("http://127.0.0.1:8080", "wikipedia", "octopus", 5) == []


def test_non_list_response_returns_empty_list(monkeypatch):
    monkeypatch.setattr(
        urllib.request, "urlopen", lambda *a, **k: _FakeResponse({"not": "a list"})
    )
    assert suggest("http://127.0.0.1:8080", "wikipedia", "octopus", 5) == []


def test_non_json_response_returns_empty_list(monkeypatch):
    class _BadResponse:
        def read(self, *a, **k):
            return b"not json at all"

        def __enter__(self):
            return self

        def __exit__(self, *exc_info):
            return False

    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: _BadResponse())
    assert suggest("http://127.0.0.1:8080", "wikipedia", "octopus", 5) == []
