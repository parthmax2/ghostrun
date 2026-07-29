from pathlib import Path

from flask import Flask, abort, send_from_directory


BASE_DIR = Path(__file__).resolve().parent

app = Flask(__name__, static_folder=None)


@app.get("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")


@app.get("/<path:path>")
def serve_site_file(path):
    target = (BASE_DIR / path).resolve()
    if not target.is_file() or BASE_DIR not in target.parents:
        abort(404)
    return send_from_directory(BASE_DIR, path)

