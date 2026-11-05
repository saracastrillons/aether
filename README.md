# AETHER — Explainable AI Business Intelligence

> Business decisions you can *explain*.

AETHER turns raw sales data into forecasts, anomalies and churn risk, plus an AI analyst that shows every query, formula and assumption behind its answers. It is a multi-tenant SaaS-style platform: FastAPI on the back end, a NumPy analytics engine, and a dependency-free single-page front end.

**Live demo:** open the app and click **Launch live demo** (company *Nimbus Retail*, 24 months of data). You can also sign in as `demo` / `analyst` / `viewer` (the password is the same as the username) to see role-based access in action.

## Features

| Area | What it does |
| --- | --- |
| **Overview** | KPI cards with sparklines, revenue with a 90% forecast band and anomaly markers, auto-generated insights, regional heatmap, product mix |
| **AI Analyst** | With an Anthropic API key, Claude works as an **agent with analytics tools** (aggregate revenue, explain a change, forecast, simulate a scenario, churn risk): it plans the analysis, the engine computes every number, and each tool call appears in the reasoning trace. It answers in the user's language and remembers the conversation. Without a key, a deterministic intent engine answers (drivers, rankings, years, best month, segments, forecast, anomalies). Rate-limited per user |
| **Forecast Lab** | Four models (OLS trend + Fourier seasonality, Holt smoothing, seasonal naive, naive) compared with **rolling-origin cross-validation**: MAPE, RMSE, bias and holdout backtest charts. The overview uses the backtested winner |
| **Scenarios** | What-if simulator (price, marketing, churn, elasticity, horizon) with a **revenue bridge** (waterfall) and presets |
| **Churn Risk** | Logistic regression trained by gradient descent **on each organization's own customers** and evaluated on a stratified 30% holdout: ROC/AUC, confusion matrix, precision/recall/F1, coefficients, risk segments, and per-customer driver and next best action for active customers |
| **Data** | Import CSV or Excel with English or Spanish headers (`Fecha`, `Ciudad`, `Ventas`…), any delimiter, dates like `14/03/2025` or `mar-25`, amounts like `1.234,50` or `$1,234.50`. Daily rows are summed into months, and a **preview** shows how the file was understood before anything is saved |
| **Alerts** | KPI threshold rules with templates, evaluated on every refresh and shown in the notification center |
| **Team & Audit** | Organizations, admin / analyst / viewer roles **enforced by the API**, expiring invite links, audit log, account settings with password change, renewable sessions. The shared public demo is protected against destructive actions |
| **Executive Report** | A one-page, print-ready brief (Print → Save as PDF) |
| **UX** | Animated landing page, ⌘K / Ctrl+K command palette, light/dark themes, deep links (`#/forecast`), responsive layout down to phone width |

## Architecture

```
static/            Single-page app (vanilla JS + Chart.js, no build step)
  index.html       Landing, auth, app shell
  css/aether.css   Design system (tokens, light/dark themes, components)
  js/app.js        Router, views, charts, analyst chat, command palette
main.py            FastAPI app: analytics endpoints, per-organization context cache
ingest.py          Tolerant CSV/Excel ingestion (header synonyms, dates, number formats)
analytics.py       Pure NumPy engine: forecasting models, backtesting, anomalies, churn model, insights
assistant.py       AI analyst: Claude tool-use agent + deterministic intent engine fallback
orgs.py            Registration, login (with brute-force throttling), invites, members
security.py        PBKDF2 password hashing, HS256 JWT, role checks
db.py              SQLAlchemy 2.0 models (SQLite by default, PostgreSQL via DATABASE_URL)
tests/             Pytest suite (API, RBAC, tenant isolation, analytics)
```

**Design decisions**

- **Explainability first:** the analyst never generates numbers with an LLM. A deterministic engine computes the figures, and Claude (when enabled) only rewrites them, so the reasoning trace always matches the answer.
- **Model selection by backtest, not in-sample fit:** each model is refit without the months it predicts. The interpretable OLS model is kept unless another model is more than 15% better.
- **Multi-tenancy:** the organization comes from the signed JWT, and every query is scoped to it. The analytics context is cached per organization and invalidated when the data changes.
- **Security:** PBKDF2-SHA256 (200k iterations), constant-time comparisons, expiring tokens, server-side RBAC, login throttling, security headers, HTML escaping of all user content on the client.

## Run locally

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
```

Set a secret of at least 48 characters, then start the API:

```powershell
# PowerShell
$env:AETHER_SECRET = python -c "import secrets; print(secrets.token_urlsafe(48))"
uvicorn main:app --reload
```

```bash
# bash
export AETHER_SECRET=$(python -c "import secrets; print(secrets.token_urlsafe(48))")
uvicorn main:app --reload
```

Open http://localhost:8000. The interactive API docs (OpenAPI / Swagger) are at http://localhost:8000/docs.

**AI agent (optional):** create an API key at https://console.anthropic.com and set it before starting the server (`$env:ANTHROPIC_API_KEY = "sk-ant-..."` in PowerShell). The analyst then uses Claude (`claude-opus-5-5`) with tools. Without a key, or if the API fails, the deterministic engine answers, so the app always works.

## Docker (API + PostgreSQL)

```bash
export AETHER_SECRET=...   # 48+ characters
docker compose up --build
```

## Tests

```bash
pytest -q
```

The tests cover authentication, RBAC, tenant isolation, CSV import, alerts, the analyst's intents, the what-if bridge, backtesting and the churn metrics. CI runs them on every push (`.github/workflows/ci.yml`).

## CSV format

```csv
month,region,product,revenue,customers
2025-01,North,Pro,27400,322
```

`customers` is optional. At least 6 distinct months are required, and 12 or more unlock the Forecast Lab.
