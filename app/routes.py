from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import quote

from flask import Blueprint, current_app, jsonify, redirect, render_template, request, url_for

from app.kiwix_client import suggest
from app.library import load_library

bp = Blueprint("portal", __name__)

# Paths that phones/laptops probe right after joining WiFi to check for
# internet access. Redirecting them to the portal home is what makes the OS
# pop a browser open automatically instead of the user having to find the
# portal themselves.
CAPTIVE_PORTAL_PROBES = [
    "/generate_204",  # Android
    "/gen_204",  # Android (older)
    "/hotspot-detect.html",  # Apple
    "/library/test/success.html",  # Apple (older)
    "/connecttest.txt",  # Windows
    "/ncsi.txt",  # Windows
]


@bp.route("/")
def index():
    zim_dir = Path(current_app.config["CONTENT_DIR"])
    has_content = zim_dir.is_dir() and any(zim_dir.glob("*.zim"))
    return render_template(
        "index.html",
        portal_title=current_app.config["PORTAL_TITLE"],
        has_content=has_content,
    )


@bp.route("/about")
def about():
    return render_template(
        "about.html",
        portal_title=current_app.config["PORTAL_TITLE"],
    )


@bp.route("/library")
def library():
    books = load_library(current_app.config["LIBRARY_XML"])
    template = current_app.config["KIWIX_VIEWER_URL_TEMPLATE"]
    entries = [
        {"book": book, "viewer_url": template.format(name=quote(book.name))}
        for book in books
    ]
    return render_template(
        "library.html",
        portal_title=current_app.config["PORTAL_TITLE"],
        entries=entries,
    )


@bp.route("/search")
def search():
    books = load_library(current_app.config["LIBRARY_XML"])
    return render_template(
        "search.html",
        portal_title=current_app.config["PORTAL_TITLE"],
        has_books=bool(books),
    )


@bp.route("/api/search-suggest")
def search_suggest():
    term = request.args.get("q", "")
    if not term.strip():
        return jsonify({"groups": []})

    books = load_library(current_app.config["LIBRARY_XML"])
    if not books:
        return jsonify({"groups": []})

    base_url = (
        f"http://127.0.0.1:{current_app.config['KIWIX_PORT']}"
        f"{current_app.config['KIWIX_URL_ROOT']}"
    )
    count = current_app.config["RESULTS_PER_ZIM"]
    article_template = current_app.config["KIWIX_ARTICLE_URL_TEMPLATE"]

    # Query every book's kiwix-serve /suggest endpoint concurrently rather than
    # one at a time - each call blocks on its own network I/O, so total latency
    # would otherwise be the sum of every book's response time instead of the
    # slowest one.
    with ThreadPoolExecutor(max_workers=min(len(books), 32)) as executor:
        results = list(
            executor.map(lambda book: suggest(base_url, book.name, term, count), books)
        )

    groups = []
    for book, articles in zip(books, results):
        if not articles:
            continue
        groups.append(
            {
                "book_title": book.title,
                "articles": [
                    {
                        "title": a["title"],
                        "url": article_template.format(
                            name=quote(book.name), path=quote(a["path"])
                        ),
                    }
                    for a in articles
                ],
            }
        )
    return jsonify({"groups": groups})


def _redirect_to_home(**_kwargs):
    return redirect(url_for("portal.index"))


for _probe in CAPTIVE_PORTAL_PROBES:
    _endpoint = "probe_" + _probe.strip("/").replace("/", "_").replace(".", "_")
    bp.add_url_rule(_probe, endpoint=_endpoint, view_func=_redirect_to_home)


@bp.route("/<path:_unmatched>")
def catch_all(_unmatched):
    return redirect(url_for("portal.index"))
