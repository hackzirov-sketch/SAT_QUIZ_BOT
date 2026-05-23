from __future__ import annotations

import os
from pathlib import Path

from flask import Flask, render_template


BASE_DIR = Path(__file__).resolve().parent
PDF_FOLDER = BASE_DIR / "static" / "pdfs"

app = Flask(__name__)


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
    return "Teacher Saydullayev site is alive."


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
