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

    from app.routes import bp

    app.register_blueprint(bp)
    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORTAL_PORT", 5000)))
