import json
import re
import urllib.parse
import urllib.request
from urllib.error import HTTPError, URLError

_TAG_RE = re.compile(r"<[^>]+>")


def suggest(base_url, book_name, term, count, timeout=2.0):
    """Query kiwix-serve's /suggest endpoint for one book.

    Never raises - returns [] on an empty term, network error, timeout, or
    unparseable response, since a down/slow ZIM shouldn't break search
    results from the others.
    """
    term = term.strip()
    if not term:
        return []
    query = urllib.parse.urlencode({"content": book_name, "term": term, "count": count})
    url = f"{base_url}/suggest?{query}"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            data = json.load(resp)
    except (URLError, HTTPError, TimeoutError, ValueError, OSError):
        return []
    if not isinstance(data, list):
        return []

    results = []
    for item in data:
        if not isinstance(item, dict):
            continue
        path = item.get("path")
        if not path or item.get("kind") == "pattern":
            continue  # kiwix's generic "search all articles for X" filler entry, not a real article
        title = _TAG_RE.sub("", item.get("value") or item.get("label") or path)
        results.append({"title": title, "path": path})
    return results
