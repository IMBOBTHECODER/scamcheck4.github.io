https://docs.google.com/document/d/1bVfq0SfeZDyTaxM2Z2XTkYSoSw5k_CeM4I4lomGcYHs/edit?usp=sharing

---

# ScamCheck

A FastAPI web app that checks whether a pasted message, email, or link is a scam.
It sends the text to **Google Gemini** (`gemini-2.5-flash`), gets back a structured
verdict (Safe / Warning / Danger) with the warning signs it found and concrete
next steps, and renders it server-side. It is built to be readable by **elderly
and non-technical users**: plain-language output, large text, icon badges, and a
Vietnamese / English toggle.

Live: <https://scamchecker.top>

## What it does

- **Scam check** — paste text, get a Safe / Warning / Danger verdict with the
  flagged snippets highlighted in the original text, plain-language reasons, and
  at least three suggested actions.
- **Quick-test presets** — one-click example scams (fake bank, fake government,
  fake prize) so first-time users can try it without typing.
- **Per-device history** — the last 10 checks are saved against an anonymous
  device id (a signed cookie — no accounts), each linking to its own result page.
  Clearing history is undoable for 10 minutes.
- **Per-device settings** — theme (dark / light / auto) and language (vi / en),
  stored in the cookie, not the database.
- **Graceful degradation** — if the database or Gemini is unavailable the site
  still boots and the affected pages show a clean notice instead of a 500.

## Project layout

The app runs **from inside `fastapi/app/`** (see the import note below).

```
hackathon/
├── index.html              # Separate static GitHub Pages demo (talks to Gemini in-browser; unrelated to the backend)
├── deploy.ps1              # rsync → server, pip install, restart uvicorn, health-check
├── .deployignore           # rsync excludes (app/venv/, .env, __pycache__)
└── fastapi/
    ├── start_uv.sh         # server-side: pkill uvicorn + relaunch main:app
    └── app/                # ← CWD when the app runs
        ├── main.py         # App factory: lifespan init_db, security middleware, sessions, /health
        ├── config.py       # Settings (.env), Gemini key pool, scam-check prompt + i18n directives
        ├── core/
        │   ├── db.py       # SQLAlchemy engine/session; resilient init_db()
        │   ├── device.py   # Anonymous per-device id (session cookie)
        │   ├── prefs.py    # Theme/language prefs (session cookie, validated)
        │   └── i18n.py     # vi/en UI string tables
        ├── models/
        │   ├── base.py     # Declarative Base + utcnow()
        │   └── scan.py     # Scan ORM model (history rows)
        ├── routers/
        │   └── pages.py    # All HTML routes (/, /result/{id}, /history, /settings)
        ├── services/
        │   └── scam_check.py   # Gemini call: prompt → JSON verdict (with key-pool failover)
        ├── templates/      # Jinja2: base, index, result, history, settings, _badge, footer
        ├── static/css/     # style.css (CSS-variable theming)
        └── requirements.txt
```

> There is **no** `schemas.py`, `routers/api.py`, or `about.html` — the scam-check
> logic lives in `services/scam_check.py` and the only API surface is `/health`.

## Important: run from `app/`, module is `main:app`

Imports inside the app are **bare** (`from config import settings`,
`from routers import pages`) and `Jinja2Templates(directory="templates")` /
`StaticFiles(directory="static")` are **relative to the current directory**. So
the app must be started with `app/` as the working directory and the module path
is `main:app` — **not** `app.main:app`.

## Run locally

```powershell
cd fastapi/app
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# Create app/.env (see Configuration) — at minimum DATABASE_URL + a Gemini key
uvicorn main:app --reload      # run from app/, module is main:app
```

- Site: <http://127.0.0.1:8000/> · Health: <http://127.0.0.1:8000/health>

A reachable **MySQL/MariaDB** is required for history; the home page and a scam
check (inline-result fallback) still work if the DB is down.

## Configuration (`app/.env`)

`.env` is gitignored and deployignored — **never commit keys** (`config.py` is in
git). `Settings` (pydantic-settings) reads these:

| Variable | Required | Purpose |
|---|---|---|
| `DATABASE_URL` | **yes** | e.g. `mysql+pymysql://user:pass@127.0.0.1:3306/scamcheck` |
| `GEMINI_API_KEYS` | yes* | Comma-separated **pool** of Gemini keys; round-robined with failover |
| `GEMINI_API_KEY` | yes* | Single Gemini key (folded into the same pool) |
| `SESSION_SECRET` | prod | Signs the device/prefs cookie — set a real value in production |
| `SESSION_HTTPS_ONLY` | prod | `true` on the HTTPS server; `false` for local http |
| `MAX_REQUEST_BYTES` | no | Request-body cap (default 64 KB) |
| `DEBUG` | no | FastAPI debug (default `true`) |

\* At least one of `GEMINI_API_KEYS` / `GEMINI_API_KEY` must be set, or checks
return a clean "not configured" message. Each key should be a **separate Google
project** to actually add quota — the free tier for `gemini-2.5-flash` is ~20
requests/day per key.

## Deploy

```powershell
./deploy.ps1      # from repo root
```

rsyncs `fastapi/` → `scamchecker:/home/scamchecker.top/fastapi/` (excludes from
`.deployignore` — notably the server-only `app/venv/`), pip-installs on the
server, runs `start_uv.sh` (relaunches `main:app`), then health-checks the public
URL **from the server** (the dev machine's wifi blocks `scamchecker.top`).

Server notes (see the `scamchecker-deploy` memory for detail): SSH alias
`scamchecker`; **Python 3.9** on the server, so avoid PEP 604 `X | None` unions —
use `typing.Optional`; reverse proxy is OpenLiteSpeed/CyberPanel (vhost changes
applied by the operator); no sudo on the server.

## Notes

- **Security:** security headers + CSP and a request-body cap (`main.py`),
  signed `same_site=lax` session cookie, all DB access via the SQLAlchemy ORM
  (parameterized), and highlighted snippets are HTML-escaped (only the inserted
  `<mark>` tags are live) — so model output can't inject HTML.
- The repo also contains a **standalone `index.html`** at the root: an unrelated
  single-file GitHub Pages demo that calls Gemini directly from the browser. It
  is not wired to this backend.
- There is no test suite or linter config yet.
