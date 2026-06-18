https://docs.google.com/document/d/1bVfq0SfeZDyTaxM2Z2XTkYSoSw5k_CeM4I4lomGcYHs/edit?usp=sharing

---

# Hackathon — FastAPI Website

A starter FastAPI scaffold with server-rendered pages (Jinja2) and a JSON API.

## Project layout

```
hackathon/
├── app/
│   ├── main.py            # App factory, mounts static + routers
│   ├── config.py          # Settings (env / .env)
│   ├── schemas.py         # Pydantic request/response models
│   ├── routers/
│   │   ├── pages.py       # HTML page routes
│   │   └── api.py         # JSON API routes (/api/*)
│   ├── templates/         # Jinja2 templates
│   │   ├── base.html
│   │   ├── index.html
│   │   └── about.html
│   └── static/
│       └── css/style.css
├── requirements.txt
└── README.md
```

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux

pip install -r requirements.txt
cp .env.example .env
```

## Run

```bash
uvicorn app.main:app --reload
```

- Site:      http://127.0.0.1:8000/
- API docs:  http://127.0.0.1:8000/docs
- Health:    http://127.0.0.1:8000/health
