from flask import Flask, send_from_directory, abort
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

app = Flask(__name__, static_folder=str(BASE_DIR))


@app.after_request
def add_headers(response):
    """
    Basic performance + security headers.
    """

    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Content-Type-Options"] = "nosniff"

    return response


@app.route("/", defaults={"path": "index.html"})
@app.route("/<path:path>")
def serve(path):
    """
    Serve frontend files safely.
    """

    requested = BASE_DIR / path

    # Prevent path traversal attacks
    if not requested.resolve().is_relative_to(BASE_DIR.resolve()):
        abort(403)

    # Serve existing file
    if requested.exists() and requested.is_file():
        return send_from_directory(BASE_DIR, path)

    # Fallback
    return send_from_directory(BASE_DIR, "index.html")


if __name__ == "__main__":
    print("Frontend server running at:")
    print("http://127.0.0.1:5500")

    app.run(
        host="0.0.0.0",
        port=5500,
        debug=False,
        threaded=True
    )