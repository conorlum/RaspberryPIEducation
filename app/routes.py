from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import quote

from flask import Blueprint, current_app, jsonify, redirect, render_template, request, url_for

from app.kiwix_client import suggest
from app.library import load_library

bp = Blueprint("portal", __name__)

# Search results are interleaved rather than grouped-by-book so a match in a
# small ZIM isn't buried below a large one - kiwix's /suggest exposes no
# relevance score at all (confirmed against a live response), so there's no
# real signal to rank across books by, only within one book's own results.
# These are matched by name prefix (not full name, which includes a
# version/date suffix that changes when a ZIM is re-downloaded) and capped at
# 2 results each before any other book's results appear, in this order. Note:
# ted_mul_ted-ed is multilingual (no Spanish-only variant exists in Kiwix's
# catalog, and kiwix's /suggest doesn't expose per-article language), so it's
# included as a whole book rather than filtered to Spanish content.
_PRIORITY_NAME_PREFIXES = [
    "khanacademy_es",
    "phet_es",
    "ted_mul_ted-ed",
    "wikipedia_es_all",
    "wikipedia_en_all",
    "medlineplus",
    "crashcourse_en",
]
_PRIORITY_RESULT_CAP = 2

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
    books = sorted(books, key=_library_sort_key)
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
    books = sorted(books, key=_library_sort_key)
    return render_template(
        "search.html",
        portal_title=current_app.config["PORTAL_TITLE"],
        has_books=bool(books),
        books=books,
        selected_book=request.args.get("book", ""),
    )


@bp.route("/api/search-suggest")
def search_suggest():
    term = request.args.get("q", "")
    if not term.strip():
        return jsonify({"results": []})

    books = load_library(current_app.config["LIBRARY_XML"])
    if not books:
        return jsonify({"results": []})

    book_filter = request.args.get("book", "").strip()
    if book_filter:
        books = [b for b in books if b.name == book_filter]
        if not books:
            return jsonify({"results": []})

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

    book_articles = [(book, a) for book, a in zip(books, results) if a]
    # A single explicitly-selected book has nothing to interleave against -
    # keep kiwix's own relevance order rather than running it through the
    # priority-tier logic, which only matters when mixing multiple books.
    if book_filter:
        interleaved = [(book, a) for book, articles in book_articles for a in articles]
    else:
        interleaved = _interleave_results(book_articles)

    results_out = [
        {
            "book_title": book.title,
            "title": article["title"],
            "url": article_template.format(
                name=quote(book.name), path=quote(article["path"])
            ),
        }
        for book, article in interleaved
    ]
    return jsonify({"results": results_out})


def _priority_rank(book_name):
    for rank, prefix in enumerate(_PRIORITY_NAME_PREFIXES):
        if book_name.startswith(prefix):
            return rank
    return None


def _library_sort_key(book):
    """Same priority tier as search (see _PRIORITY_NAME_PREFIXES), in that
    order, followed by every other book alphabetically by title."""
    rank = _priority_rank(book.name)
    if rank is not None:
        return (0, rank)
    return (1, book.title.lower())


def _interleave_results(book_articles):
    """book_articles: list of (Book, [article, ...]) for books with >=1 hit.

    Priority books (see _PRIORITY_NAME_PREFIXES) contribute up to
    _PRIORITY_RESULT_CAP results each, one round at a time in priority order,
    before any other book's results appear. After that, remaining books are
    round-robined in their existing order so a match in a small ZIM isn't
    buried below a large one.
    """
    priority = sorted(
        (ba for ba in book_articles if _priority_rank(ba[0].name) is not None),
        key=lambda ba: _priority_rank(ba[0].name),
    )
    other = [ba for ba in book_articles if _priority_rank(ba[0].name) is None]

    interleaved = []
    for round_index in range(_PRIORITY_RESULT_CAP):
        for book, articles in priority:
            if round_index < len(articles):
                interleaved.append((book, articles[round_index]))

    max_len = max((len(articles) for _, articles in other), default=0)
    for round_index in range(max_len):
        for book, articles in other:
            if round_index < len(articles):
                interleaved.append((book, articles[round_index]))

    return interleaved


def _redirect_to_home(**_kwargs):
    hostname = current_app.config.get("PORTAL_HOSTNAME")
    if hostname:
        return redirect(f"http://{hostname}/")
    return redirect(url_for("portal.index"))


for _probe in CAPTIVE_PORTAL_PROBES:
    _endpoint = "probe_" + _probe.strip("/").replace("/", "_").replace(".", "_")
    bp.add_url_rule(_probe, endpoint=_endpoint, view_func=_redirect_to_home)


@bp.route("/<path:_unmatched>")
def catch_all(_unmatched):
    return redirect(url_for("portal.index"))
