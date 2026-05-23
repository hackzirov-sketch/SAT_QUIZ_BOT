# Teacher Saydullayev Site

Standalone Flask website for teacher and student result PDFs.

## Run Locally

```powershell
cd teacher_site
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open:

```text
http://127.0.0.1:5000
```

## Add PDFs

Put PDF files into:

```text
static/pdfs/
```

Refresh the site. Files with names containing `teacher`, `sat`, `milliy`, `natija`, or `diplom` are shown in the main results section; other PDFs are shown as student certificates.

## cPanel

Use Python App / Passenger:

- Application root: `teacher_site`
- Startup file: `passenger_wsgi.py`
- Entry point: `application`
- Install dependencies from `requirements.txt`
