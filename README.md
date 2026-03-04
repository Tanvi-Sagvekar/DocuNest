## Auto Document Organizer (DocuNest)

Smart document organizer that automatically classifies uploaded files (PDF, DOCX, images) into categories like **Academic**, **Finance**, **Medical**, and **Personal** using simple NLP keyword matching. It stores metadata in a local database, organizes files into category folders, and provides a clean dashboard UI with search and category views.

### Features

- **Automatic classification** using keyword-based NLP with confidence score
- **Supported formats**: PDF, DOCX, images (with optional OCR)
- **Dashboard** with total documents and per-category counts
- **Upload page** with drag-and-drop and progress feedback
- **Processing screen** that visually shows analysis steps
- **Result page** with category, confidence, and quick actions
- **Category views** to browse documents by type
- **Search** across file names and extracted text
- **Auto-folder organization** (`uploads/Academic`, `uploads/Finance`, etc.)

### Tech Stack

- **Backend**: Python, Flask
- **Database**: SQLite (default, file-based). Schema is compatible with MySQL and a `database.sql` file is provided for MySQL setup.
- **NLP**: Simple keyword matching (easily extendable to ML models)
- **Frontend**: HTML, Bootstrap 5, custom CSS

### Setup

1. **Create a virtual environment (recommended)**

```bash
cd d:\DocuNest
python -m venv venv
venv\Scripts\activate
```

2. **Install dependencies**

```bash
pip install -r requirements.txt
```

3. **(Optional) Enable OCR for images**

- Install Tesseract OCR on your system and ensure the `tesseract` command is available in your PATH.
- Install additional Python packages (already listed in `requirements.txt`).

4. **Run the app**

```bash
python app.py
```

Then open `http://127.0.0.1:5000` in your browser.

### Database Notes

- The app uses a local SQLite database file (`documents.db`) by default and auto-creates the `documents` table on first run.
- A sample **MySQL** schema is provided in `database.sql` if you want to migrate to MySQL for production use.

### Project Structure

```text
auto_doc_organizer/ (this repo)
├── app.py
├── requirements.txt
├── README.md
├── database.sql
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── upload.html
│   ├── processing.html
│   ├── result.html
│   └── category.html
├── static/
│   ├── css/
│   │   └── styles.css
│   └── img/
├── uploads/
│   ├── Academic/
│   ├── Finance/
│   ├── Medical/
│   └── Personal/
└── documents.db (auto-created)
```

You can freely customize the categories, keywords, and UI styling to match your needs or extend this into a more advanced ML-based classifier.

