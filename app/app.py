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
    app.config["RESULTS_PER_ZIM"] = int(os.environ.get("RESULTS_PER_ZIM", 5))
    app.config["KIWIX_VIEWER_URL_TEMPLATE"] = os.environ.get(
        "KIWIX_VIEWER_URL_TEMPLATE", "/kiwix/viewer#{name}"
    )
    app.config["KIWIX_ARTICLE_URL_TEMPLATE"] = os.environ.get(
        "KIWIX_ARTICLE_URL_TEMPLATE", "/kiwix/viewer#{name}/{path}"
    )

    from app.routes import bp

    app.register_blueprint(bp)
    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORTAL_PORT", 5000)))
