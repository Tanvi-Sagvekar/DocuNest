import os
import sqlite3
from datetime import datetime
from typing import Tuple, Dict

from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash
from werkzeug.utils import secure_filename
from PyPDF2 import PdfReader
from docx import Document
from PIL import Image
import pytesseract

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_ROOT = os.path.join(BASE_DIR, "uploads")
DB_PATH = os.path.join(BASE_DIR, "documents.db")

ALLOWED_EXTENSIONS = {"pdf", "docx", "png", "jpg", "jpeg"}

app = Flask(__name__)
app.config["SECRET_KEY"] = "change-this-in-production"
app.config["UPLOAD_ROOT"] = UPLOAD_ROOT


def ensure_directories() -> None:
    os.makedirs(UPLOAD_ROOT, exist_ok=True)
    for category in ["Academic", "Finance", "Medical", "Personal", "Uncategorized"]:
        os.makedirs(os.path.join(UPLOAD_ROOT, category), exist_ok=True)


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_name TEXT NOT NULL,
            original_filename TEXT NOT NULL,
            category TEXT NOT NULL,
            confidence REAL NOT NULL,
            upload_date TEXT NOT NULL,
            file_path TEXT NOT NULL,
            text_excerpt TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def extract_text_from_pdf(path: str) -> str:
    text = ""
    try:
        reader = PdfReader(path)
        for page in reader.pages:
            page_text = page.extract_text() or ""
            text += page_text + "\n"
    except Exception:
        return ""
    return text


def extract_text_from_docx(path: str) -> str:
    try:
        doc = Document(path)
        return "\n".join(p.text for p in doc.paragraphs)
    except Exception:
        return ""


def extract_text_from_image(path: str) -> str:
    try:
        image = Image.open(path)
        return pytesseract.image_to_string(image)
    except Exception:
        return ""


def extract_text(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        return extract_text_from_pdf(path)
    if ext == ".docx":
        return extract_text_from_docx(path)
    if ext in {".png", ".jpg", ".jpeg"}:
        return extract_text_from_image(path)
    return ""


categories_keywords: Dict[str, list] = {
    "Academic": ["certificate", "university", "marks", "grade", "college", "semester", "degree", "course"],
    "Finance": ["invoice", "bank", "account", "payment", "amount", "transaction", "statement", "salary"],
    "Medical": ["hospital", "doctor", "diagnosis", "medicine", "report", "prescription", "test", "lab"],
    "Personal": ["aadhaar", "passport", "birth", "address", "license", "id card", "pan card"],
}


def classify_text(text: str) -> Tuple[str, float]:
    if not text:
        return "Uncategorized", 0.0

    lower_text = text.lower()
    scores: Dict[str, int] = {cat: 0 for cat in categories_keywords}

    for category, keywords in categories_keywords.items():
        for word in keywords:
            if word.lower() in lower_text:
                scores[category] += 1

    best_category = max(scores, key=scores.get)
    best_score = scores[best_category]
    total_hits = sum(scores.values())

    if best_score == 0:
        return "Uncategorized", 0.0

    confidence = (best_score / (total_hits if total_hits > 0 else best_score)) * 100.0
    return best_category, round(confidence, 2)


@app.route("/")
def index():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS total FROM documents")
    total = cur.fetchone()["total"]

    cur.execute(
        """
        SELECT category, COUNT(*) as count
        FROM documents
        GROUP BY category
        """
    )
    counts = {row["category"]: row["count"] for row in cur.fetchall()}
    conn.close()

    summary = {
        "total": total,
        "Academic": counts.get("Academic", 0),
        "Finance": counts.get("Finance", 0),
        "Medical": counts.get("Medical", 0),
        "Personal": counts.get("Personal", 0),
        "Uncategorized": counts.get("Uncategorized", 0),
    }

    conn = get_db_connection()
    docs = conn.execute(
        "SELECT id, original_filename, category, upload_date FROM documents ORDER BY datetime(upload_date) DESC LIMIT 5"
    ).fetchall()
    conn.close()

    return render_template("index.html", summary=summary, recent_docs=docs)


@app.route("/upload", methods=["GET", "POST"])
def upload():
    if request.method == "POST":
        if "file" not in request.files:
            flash("No file part in the request.", "danger")
            return redirect(request.url)

        file = request.files["file"]
        if file.filename == "":
            flash("No file selected.", "warning")
            return redirect(request.url)

        if not allowed_file(file.filename):
            flash("Unsupported file type.", "danger")
            return redirect(request.url)

        original_filename = file.filename
        filename = secure_filename(file.filename)
        temp_path = os.path.join(UPLOAD_ROOT, filename)
        file.save(temp_path)

        extracted_text = extract_text(temp_path)
        category, confidence = classify_text(extracted_text)

        category_folder = os.path.join(UPLOAD_ROOT, category)
        os.makedirs(category_folder, exist_ok=True)
        final_path = os.path.join(category_folder, filename)
        if os.path.exists(final_path):
            name, ext = os.path.splitext(filename)
            final_path = os.path.join(category_folder, f"{name}_{int(datetime.utcnow().timestamp())}{ext}")

        os.replace(temp_path, final_path)

        rel_path = os.path.relpath(final_path, BASE_DIR)
        text_excerpt = (extracted_text[:400] + "...") if extracted_text and len(extracted_text) > 400 else extracted_text

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO documents (file_name, original_filename, category, confidence, upload_date, file_path, text_excerpt)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                os.path.basename(final_path),
                original_filename,
                category,
                confidence,
                datetime.utcnow().isoformat(timespec="seconds"),
                rel_path,
                text_excerpt,
            ),
        )
        doc_id = cur.lastrowid
        conn.commit()
        conn.close()

        return render_template(
            "processing.html",
            doc_id=doc_id,
            category=category,
            confidence=confidence,
        )

    return render_template("upload.html")


@app.route("/result/<int:doc_id>")
def result(doc_id: int):
    conn = get_db_connection()
    doc = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
    conn.close()
    if doc is None:
        flash("Document not found.", "danger")
        return redirect(url_for("index"))
    return render_template("result.html", doc=doc)


@app.route("/category/<string:category_name>")
def category_view(category_name: str):
    conn = get_db_connection()
    docs = conn.execute(
        "SELECT * FROM documents WHERE category = ? ORDER BY datetime(upload_date) DESC", (category_name,)
    ).fetchall()
    conn.close()
    return render_template("category.html", category_name=category_name, docs=docs)


@app.route("/search")
def search():
    query = request.args.get("q", "").strip()
    docs = []
    if query:
        like = f"%{query}%"
        conn = get_db_connection()
        docs = conn.execute(
            """
            SELECT * FROM documents
            WHERE original_filename LIKE ?
               OR text_excerpt LIKE ?
            ORDER BY datetime(upload_date) DESC
            """,
            (like, like),
        ).fetchall()
        conn.close()
    return render_template("category.html", category_name=f"Search: {query}", docs=docs, search_mode=True, query=query)


@app.route("/download/<int:doc_id>")
def download(doc_id: int):
    conn = get_db_connection()
    doc = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
    conn.close()
    if doc is None:
        flash("Document not found.", "danger")
        return redirect(url_for("index"))

    abs_path = os.path.join(BASE_DIR, doc["file_path"])
    directory = os.path.dirname(abs_path)
    filename = os.path.basename(abs_path)
    return send_from_directory(directory, filename, as_attachment=True)


@app.route("/view/<int:doc_id>")
def view_file(doc_id: int):
    conn = get_db_connection()
    doc = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
    conn.close()
    if doc is None:
        flash("Document not found.", "danger")
        return redirect(url_for("index"))

    abs_path = os.path.join(BASE_DIR, doc["file_path"])
    directory = os.path.dirname(abs_path)
    filename = os.path.basename(abs_path)
    return send_from_directory(directory, filename)


@app.context_processor
def inject_categories():
    return {
        "NAV_CATEGORIES": ["Academic", "Finance", "Medical", "Personal", "Uncategorized"],
    }


if __name__ == "__main__":
    ensure_directories()
    init_db()
    app.run(debug=True)

import os
import sqlite3
from datetime import datetime
from pathlib import Path

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    send_from_directory,
    flash,
    g,
)
from werkzeug.utils import secure_filename

from PyPDF2 import PdfReader
import docx2txt
from PIL import Image

try:
    import pytesseract
except ImportError:  # Optional OCR support
    pytesseract = None


BASE_DIR = Path(__file__).resolve().parent
UPLOAD_FOLDER = BASE_DIR / "uploads"
DB_PATH = BASE_DIR / "documents.db"

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".png", ".jpg", ".jpeg"}

CATEGORIES = {
    "Academic": ["certificate", "university", "marks", "grade", "college", "semester", "degree"],
    "Finance": ["invoice", "bank", "account", "payment", "amount", "transaction", "statement"],
    "Medical": ["hospital", "doctor", "diagnosis", "medicine", "report", "prescription", "lab"],
    "Personal": ["aadhaar", "passport", "birth", "address", "license", "id card", "identity"],
}


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "change-this-in-production"
    app.config["UPLOAD_FOLDER"] = str(UPLOAD_FOLDER)

    # Ensure upload directories exist
    UPLOAD_FOLDER.mkdir(exist_ok=True)
    for category in CATEGORIES.keys():
        (UPLOAD_FOLDER / category).mkdir(parents=True, exist_ok=True)

    init_db()

    @app.route("/")
    def index():
        db = get_db()
        cur = db.execute(
            "SELECT category, COUNT(*) as count FROM documents GROUP BY category"
        )
        counts = {row["category"]: row["count"] for row in cur.fetchall()}

        total = sum(counts.values())

        recent = db.execute(
            "SELECT id, file_name, category, confidence, upload_date FROM documents "
            "ORDER BY upload_date DESC LIMIT 5"
        ).fetchall()

        # Ensure all categories appear with at least 0
        for cat in CATEGORIES.keys():
            counts.setdefault(cat, 0)

        return render_template(
            "index.html",
            total=total,
            counts=counts,
            recent=recent,
        )

    @app.route("/upload", methods=["GET", "POST"])
    def upload():
        if request.method == "POST":
            if "file" not in request.files:
                flash("No file part in the request.", "danger")
                return redirect(request.url)

            file = request.files["file"]
            if file.filename == "":
                flash("Please choose a file to upload.", "warning")
                return redirect(request.url)

            original_filename = secure_filename(file.filename)
            ext = Path(original_filename).suffix.lower()

            if ext not in ALLOWED_EXTENSIONS:
                flash("Unsupported file type. Use PDF, DOCX, JPG, or PNG.", "danger")
                return redirect(request.url)

            temp_path = UPLOAD_FOLDER / original_filename
            file.save(temp_path)

            # Extract text
            try:
                extracted_text = extract_text(str(temp_path))
            except Exception:
                extracted_text = ""

            if not extracted_text.strip():
                flash(
                    "Could not extract text from this document. "
                    "Make sure it is not a scanned image-only PDF.",
                    "warning",
                )

            category, confidence, matched_keywords = classify_document(extracted_text)

            # Move file into category subfolder
            category_folder = UPLOAD_FOLDER / category
            category_folder.mkdir(parents=True, exist_ok=True)
            final_path = category_folder / original_filename
            if temp_path != final_path:
                if final_path.exists():
                    # Avoid overwrite: add timestamp
                    name, ext2 = os.path.splitext(original_filename)
                    final_path = category_folder / f"{name}_{int(datetime.now().timestamp())}{ext2}"
                os.replace(temp_path, final_path)

            # Save record in DB
            db = get_db()
            cur = db.execute(
                """
                INSERT INTO documents
                (file_name, category, confidence, upload_date, file_path, original_name, extracted_text)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    final_path.name,
                    category,
                    confidence,
                    datetime.now().isoformat(timespec="seconds"),
                    str(final_path),
                    original_filename,
                    extracted_text,
                ),
            )
            db.commit()
            doc_id = cur.lastrowid

            return redirect(url_for("processing", doc_id=doc_id))

        return render_template("upload.html")

    @app.route("/processing/<int:doc_id>")
    def processing(doc_id):
        return render_template("processing.html", doc_id=doc_id)

    @app.route("/result/<int:doc_id>")
    def result(doc_id):
        db = get_db()
        doc = db.execute(
            "SELECT * FROM documents WHERE id = ?", (doc_id,)
        ).fetchone()

        if doc is None:
            flash("Document not found.", "danger")
            return redirect(url_for("index"))

        return render_template("result.html", doc=doc)

    @app.route("/category/<string:category>")
    def category_view(category):
        db = get_db()
        docs = db.execute(
            "SELECT id, file_name, original_name, category, confidence, upload_date "
            "FROM documents WHERE category = ? ORDER BY upload_date DESC",
            (category,),
        ).fetchall()
        return render_template("category.html", category=category, docs=docs)

    @app.route("/search")
    def search():
        query = request.args.get("q", "").strip()
        db = get_db()

        results = []
        if query:
            like = f"%{query}%"
            results = db.execute(
                """
                SELECT id, file_name, original_name, category, confidence, upload_date
                FROM documents
                WHERE original_name LIKE ? OR extracted_text LIKE ?
                ORDER BY upload_date DESC
                """,
                (like, like),
            ).fetchall()

        return render_template("category.html", category="Search results", docs=results, query=query)

    @app.route("/view/<int:doc_id>")
    def view_file(doc_id):
        db = get_db()
        doc = db.execute(
            "SELECT file_path, original_name FROM documents WHERE id = ?", (doc_id,)
        ).fetchone()

        if doc is None:
            flash("File not found.", "danger")
            return redirect(url_for("index"))

        file_path = Path(doc["file_path"])
        if not file_path.exists():
            flash("File is missing on the server.", "danger")
            return redirect(url_for("index"))

        return send_from_directory(
            directory=file_path.parent,
            path=file_path.name,
            as_attachment=False,
            download_name=doc["original_name"],
        )

    return app


def allowed_file(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


def extract_text(file_path: str) -> str:
    path = Path(file_path)
    ext = path.suffix.lower()

    if ext == ".pdf":
        reader = PdfReader(str(path))
        text_parts = []
        for page in reader.pages:
            try:
                page_text = page.extract_text() or ""
            except Exception:
                page_text = ""
            text_parts.append(page_text)
        return "\n".join(text_parts)

    if ext == ".docx":
        return docx2txt.process(str(path)) or ""

    if ext in {".png", ".jpg", ".jpeg"} and pytesseract is not None:
        image = Image.open(str(path))
        return pytesseract.image_to_string(image) or ""

    # Fallback: try reading as plain text
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def classify_document(text: str):
    text_lower = text.lower()
    scores = {}
    matched_keywords = {}

    for category, keywords in CATEGORIES.items():
        hits = [word for word in keywords if word.lower() in text_lower]
        matched_keywords[category] = hits
        scores[category] = len(hits)

    if any(scores.values()):
        best_category = max(scores, key=scores.get)
    else:
        best_category = "Personal"  # default fallback

    total_hits = sum(scores.values())
    if total_hits > 0 and scores[best_category] > 0:
        confidence = int((scores[best_category] / total_hits) * 100)
    else:
        confidence = 0

    return best_category, confidence, matched_keywords.get(best_category, [])


def get_db():
    if "db" not in g:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        g.db = conn
    return g.db


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_name TEXT NOT NULL,
            category TEXT NOT NULL,
            confidence INTEGER DEFAULT 0,
            upload_date TEXT NOT NULL,
            file_path TEXT NOT NULL,
            original_name TEXT NOT NULL,
            extracted_text TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


app = create_app()
app.teardown_appcontext(close_db)


if __name__ == "__main__":
    app.run(debug=True)

