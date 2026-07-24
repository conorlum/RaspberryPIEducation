import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask

BASE_DIR = Path(__file__).resolve().parent.parent


def create_app():
    load_dotenv(BASE_DIR / "config" / "settings.env")

    app = Flask(__name__)
    app.config["PORTAL_TITLE"] = os.environ.get("PORTAL_TITLE", "RACHEL")
    app.config["CONTENT_DIR"] = os.environ.get(
        "CONTENT_DIR", str(BASE_DIR / "content" / "zim")
    )
    app.config["LIBRARY_XML"] = os.environ.get(
        "LIBRARY_XML", str(BASE_DIR / "content" / "library.xml")
    )
    app.config["KIWIX_PORT"] = int(os.environ.get("KIWIX_PORT", 8080))
    # kiwix-serve is started with --urlRootLocation matching this, so it
    # both expects requests prefixed with it and generates its own internal
    # links (content/search/viewer) the same way. Must stay in sync with
    # setup/systemd/kiwix-serve.service's --urlRootLocation value.
    app.config["KIWIX_URL_ROOT"] = os.environ.get("KIWIX_URL_ROOT", "/kiwix")
    app.config["RESULTS_PER_ZIM"] = int(os.environ.get("RESULTS_PER_ZIM", 5))
    # /content/ (plain server-rendered pages, real URLs) rather than /viewer#
    # (kiwix's JS single-page-app reader, hash-routed, with a toolbar that
    # resizes on scroll) - the latter triggers a known class of Chrome-for-
    # Android bug where a scroll-triggered resize leaves a blank gap over the
    # browser's own dynamic toolbar, blocking the back button until the user
    # swipes instead. Confirmed live: /content/ renders identical content,
    # in-article links and the book-root main-page redirect both still work.
    app.config["KIWIX_VIEWER_URL_TEMPLATE"] = os.environ.get(
        "KIWIX_VIEWER_URL_TEMPLATE", "/kiwix/content/{name}"
    )
    app.config["KIWIX_ARTICLE_URL_TEMPLATE"] = os.environ.get(
        "KIWIX_ARTICLE_URL_TEMPLATE", "/kiwix/content/{name}/{path}"
    )

    from app.routes import bp

    app.register_blueprint(bp)
    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORTAL_PORT", 5000)))
