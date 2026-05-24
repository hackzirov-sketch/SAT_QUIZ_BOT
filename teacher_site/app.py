from __future__ import annotations

import os
from pathlib import Path

import asyncio

from flask import Flask, jsonify, render_template


BASE_DIR = Path(__file__).resolve().parent
PDF_FOLDER = BASE_DIR / "static" / "pdfs"

app = Flask(__name__)

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Content-Security-Policy": (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data:; "
        "connect-src 'self' https://cdnjs.cloudflare.com; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    ),
}


@app.after_request
def add_security_headers(response):
    for header, value in SECURITY_HEADERS.items():
        response.headers.setdefault(header, value)
    return response


def pretty_name(filename: str) -> str:
    name = Path(filename).stem
    return (
        name.replace("_", " ")
        .replace("-", " ")
        .replace("Teacher", "Teacher ")
        .replace("SAT", "SAT")
        .strip()
        .title()
    )


def is_teacher_document(filename: str) -> bool:
    lowered = filename.lower()
    teacher_words = ("teacher", "sat", "milliy", "natija", "diplom")
    return any(word in lowered for word in teacher_words)


@app.route("/")
def index():
    PDF_FOLDER.mkdir(parents=True, exist_ok=True)
    pdfs = sorted(path.name for path in PDF_FOLDER.glob("*.pdf"))
    teachers = [pdf for pdf in pdfs if is_teacher_document(pdf)]
    students = [pdf for pdf in pdfs if pdf not in teachers]
    return render_template(
        "index.html",
        teachers=teachers,
        students=students,
        pretty_name=pretty_name,
        total_count=len(pdfs),
    )


@app.route("/health")
def health():
    try:
        from bot.services.health_service import health_snapshot

        snapshot = asyncio.run(health_snapshot())
        status = 200 if snapshot.get("ok") else 503
        return jsonify(snapshot), status
    except Exception as exc:
        return jsonify({"ok": False, "flask_alive": True, "error": type(exc).__name__}), 503


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
