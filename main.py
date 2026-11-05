"""AETHER API - explainable business intelligence."""
import random, re, time
from datetime import date
import numpy as np
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel, Field
from db import (engine as db_engine, init_db, load_sales, replace_sales, add_audit, load_alerts, save_alert,
                delete_alert, get_data_mode, set_data_mode, load_customers, replace_customers)
from security import auth, need, ORG, RateLimiter
from orgs import guard_demo
import analytics as an, assistant, ingest, orgs

VERSION = "1.1.0"
STARTED = time.time()
init_db(); orgs.seed()
app = FastAPI(title="AETHER API", version=VERSION, description="Explainable AI business intelligence platform: "
              "multi-tenant analytics, forecasting with backtesting, anomaly detection, churn ML and an explainable AI analyst.")
app.include_router(orgs.router)

@app.middleware("http")
async def security_headers(request: Request, call_next):
    r = await call_next(request)
    r.headers.update({"X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY", "Referrer-Policy": "strict-origin-when-cross-origin",
                      "Permissions-Policy": "camera=(), microphone=(), geolocation=()"})
    return r

# ---------- Demo data: fictional company "Nimbus Retail" ----------
def build():
    rnd = random.Random(7); rows = []
    for i in range(24):
        y, m = 2024 + i // 12, i % 12 + 1
        season = 1 + 0.12 * np.sin((m - 3) / 12 * 2 * np.pi)
        for r in ["Norte", "Sur", "Centro", "Online"]:
            for p in ["Pro", "Plus", "Basic"]:
                base = {"Norte": 9, "Sur": 7, "Centro": 11, "Online": 8}[r] * {"Pro": 3, "Plus": 2, "Basic": 1}[p]
                v = base * 1000 * (1 + 0.025 * i) * season * rnd.uniform(0.95, 1.05)
                if (y, m) == (2025, 9) and r == "Online": v *= 0.45   # incident: checkout outage
                if (y, m) == (2025, 9) and p == "Pro": v *= 0.82       # churn on premium plan
                rows.append({"month": f"{y}-{m:02d}", "region": r, "product": p, "revenue": round(v), "customers": int(v / 85)})
    return rows

_C, _CTX = {}, {}   # per-organization caches: raw sales rows and computed analytics context

def rows(org=None):
    org = org or ORG.get()
    if org not in _C:
        d = load_sales(org)
        if not d and get_data_mode(org) == "demo":
            replace_sales(org, build()); d = load_sales(org)
        _C[org] = d
    return _C[org]

def invalidate(org): _C.pop(org, None); _CTX.pop(org, None); _CHURN.pop(org, None)

def context(user):
    """Everything the dashboards need, computed once per organization and cached until the data changes."""
    org = user["org"]
    if org in _CTX: return _CTX[org]
    data = rows(org)
    if not data: return None
    m, by_r, by_p, cust = {}, {}, {}, {}
    for r in data:
        m[r["month"]] = m.get(r["month"], 0) + r["revenue"]
        by_r[(r["month"], r["region"])] = by_r.get((r["month"], r["region"]), 0) + r["revenue"]
        by_p[(r["month"], r["product"])] = by_p.get((r["month"], r["product"]), 0) + r["revenue"]
        cust[r["month"]] = cust.get(r["month"], 0) + r["customers"]
    months = sorted(m); vals = [m[k] for k in months]
    regions = sorted({r["region"] for r in data}); products = sorted({r["product"] for r in data})
    region_series = {g: [by_r.get((mm, g), 0) for mm in months] for g in regions}
    product_series = {p: [by_p.get((mm, p), 0) for mm in months] for p in products}

    # model selection: keep the interpretable OLS model unless another one backtests clearly (>15%) better
    scores, ranked, _ = an.backtest(vals, 3) if len(vals) >= 12 else ({}, [], 0)
    best = "ols_seasonal"
    if ranked and scores["ols_seasonal"]["mape"] is not None and scores[ranked[0]]["mape"] * 1.15 < scores["ols_seasonal"]["mape"]:
        best = ranked[0]
    f, sd, in_mape = an.forecast(vals, 3, best); lo, hi = an.intervals(f, sd)
    anoms = an.anomalies(months, vals, region_series)
    mom = round((vals[-1] / vals[-2] - 1) * 100, 1) if len(vals) > 1 else 0
    ttm = round((sum(vals[-12:]) / sum(vals[-24:-12]) - 1) * 100, 1) if len(vals) >= 24 else None   # undefined without two full years
    kpis = {"revenue_total": sum(vals), "last_month": vals[-1], "mom_pct": mom, "customers": cust[months[-1]],
            "ytd_growth_pct": ttm, "arpu": round(vals[-1] / max(1, cust[months[-1]]), 2), "next_month": round(f[0])}
    fc = {"months": an.next_months(months[-1], 3), "values": [round(x) for x in f], "lower": lo, "upper": hi,
          "mape": scores.get(best, {}).get("mape") or round(in_mape, 2), "model": an.MODELS[best][0], "model_key": best}
    last12 = months[-12:]
    ctx = {"org": user.get("org_name", "Your organization"), "rows": len(data), "data": data, "months": months, "revenue": vals, "monthly": m,
           "customers": [cust[k] for k in months], "regions": regions, "products": products,
           "by_region": by_r, "by_product": by_p, "region_series": region_series, "product_series": product_series,
           "forecast": fc, "kpis": kpis, "anomalies": anoms,
           "heatmap": {"months": last12, "rows": [{"label": g, "values": [by_r.get((mm, g), 0) for mm in last12]} for g in regions]},
           "insights": an.insights(months, vals, region_series, product_series, anoms, f)}
    _CTX[org] = ctx
    return ctx

class Turn(BaseModel): role: str; content: str = Field(max_length=4000)
class Ask(BaseModel): question: str = Field(min_length=1, max_length=500); history: list[Turn] = Field(default_factory=list, max_length=20)

ASK_LIMIT = 40   # questions per user per hour; protects the AI budget
ASKS = RateLimiter(ASK_LIMIT, 3600)

EMPTY_FC = {"months": [], "values": [], "lower": [], "upper": [], "mape": None, "model": "Insufficient data"}

@app.get("/api/overview")
def overview(user=Depends(auth)):
    ctx = context(user); mode = get_data_mode(user["org"])
    if not ctx:
        return {"data_mode": mode, "user": user, "months": [], "revenue": [], "customers": [], "forecast": EMPTY_FC,
                "kpis": {"revenue_total": 0, "last_month": 0, "mom_pct": 0, "customers": 0, "ytd_growth_pct": 0, "arpu": 0, "next_month": 0},
                "by_region": {}, "by_product": {}, "heatmap": {"months": [], "rows": []}, "anomalies": [], "insights": [],
                "quality": {"rows": 0, "duplicates": 0, "missing": 0, "score": 0}}
    return {"data_mode": mode, "user": user, "months": ctx["months"], "revenue": ctx["revenue"], "customers": ctx["customers"],
            "forecast": ctx["forecast"], "kpis": ctx["kpis"], "by_region": ctx["region_series"], "by_product": ctx["product_series"],
            "heatmap": ctx["heatmap"], "anomalies": ctx["anomalies"], "insights": ctx["insights"],
            "quality": {"rows": ctx["rows"], "duplicates": 0, "missing": 0, "score": 100}}

@app.get("/api/forecast/lab")
def forecast_lab(h: int = 6, user=Depends(auth)):
    """Model comparison with rolling-origin backtesting, plus each model's forward forecast."""
    ctx = context(user)
    if not ctx or len(ctx["revenue"]) < 12: raise HTTPException(422, "Need at least 12 months of data for the forecast lab")
    h = max(1, min(h, 12)); vals = ctx["revenue"]
    scores, ranked, folds = an.backtest(vals, 3)
    paths, hold = an.holdout_paths(vals, 6); models = {}
    for k, (label, _) in an.MODELS.items():
        f, sd, _ = an.forecast(vals, h, k); lo, hi = an.intervals(f, sd)
        models[k] = {**scores[k], "forecast": [round(x) for x in f], "lower": lo, "upper": hi, "holdout": paths[k]}
    return {"months": ctx["months"], "revenue": vals, "future": an.next_months(ctx["months"][-1], h), "holdout_size": hold,
            "folds": folds, "horizon": h, "ranking": ranked, "best": ranked[0], "models": models,
            "method": f"Rolling-origin cross-validation: {folds} folds, expanding window, 3-month horizon per fold."}

@app.post("/api/ask")
def ask(b: Ask, user=Depends(auth)):
    ctx = context(user)
    if not ctx:
        return {"answer": "No business data is available yet. Import a CSV or Excel file in the Data section to start analyzing your company.",
                "sources": [], "calculations": [], "chart": None, "followups": [], "engine": "aether-engine"}
    ASKS.check((user["org"], user["sub"]), f"You've reached {ASK_LIMIT} questions this hour. Please try again later.")
    clip = lambda v, lo, hi: max(lo, min(hi, float(v or 0)))
    extras = {"whatif": lambda p, m, c, h: whatif(WI(price=clip(p, -50, 50), marketing=clip(m, -100, 200), churn=clip(c, -50, 50),
                                                       horizon=int(clip(h, 1, 12))), user),
              "churn": lambda: churn(user)}
    return assistant.answer(b.question, ctx, [t.model_dump() for t in b.history], extras)

@app.get("/api/assistant/info")
def assistant_info(user=Depends(auth)):
    return {"llm": assistant.llm_enabled(), "model": assistant.MODEL if assistant.llm_enabled() else "aether-engine", "suggestions": assistant.SUGGESTIONS}

@app.get("/api/report")
def report(user=Depends(auth)):
    o = overview(user); ctx = context(user)
    summary = assistant.engine("executive summary", ctx)["answer"] if ctx else "No data yet."
    lead = ctx["anomalies"][-1]["month"] if ctx and ctx["anomalies"] else None
    insight = assistant.engine(f"why did revenue change in {lead}", ctx)["answer"] if lead else summary
    return {"title": f"Executive Report — {user.get('org_name', 'Organization')}", "generated": str(date.today()), "author": user["sub"],
            "kpis": o["kpis"], "forecast": o["forecast"], "anomalies": o["anomalies"], "insights": o["insights"],
            "summary": summary, "insight": insight, "months": o["months"][-12:], "revenue": o["revenue"][-12:],
            "regions": {r: s[-12:] for r, s in o["by_region"].items()}}

@app.get("/api/health")
def health():
    return {"status": "ok", "version": VERSION, "uptime_s": round(time.time() - STARTED), "database": db_engine.dialect.name,
            "ai_narration": assistant.llm_enabled()}

def log(u, a): add_audit(u["org"], u["sub"], a)

TEMPLATES = {"sales": ingest.SALES_TEMPLATE, "customers": ingest.CUSTOMER_TEMPLATE}

@app.get("/api/templates/{kind}", response_class=PlainTextResponse)
def template(kind: str):
    if kind not in TEMPLATES: raise HTTPException(404, "Unknown template")
    return TEMPLATES[kind]

@app.get("/api/sample-csv", response_class=PlainTextResponse)
def sample_csv(): return ingest.SALES_TEMPLATE

class Up(BaseModel):
    content: str | None = Field(None, max_length=8_000_000); content_b64: str | None = Field(None, max_length=11_000_000)
    filename: str = Field("", max_length=200); dry_run: bool = False

def _read(b, fn):
    try: return fn(b.content, b.content_b64, b.filename)
    except ingest.IngestError as e: raise HTTPException(422, str(e))

@app.post("/api/upload")
def upload(b: Up, user=Depends(auth)):
    """Import sales. With dry_run=true nothing is saved: the response shows how the file was understood."""
    need(user, "admin", "analyst")
    clean, rep = _read(b, ingest.ingest_sales)
    if rep["months"] < 6: raise HTTPException(422, f"Need at least 6 distinct months of data (found {rep['months']}).")
    if b.dry_run: return {**rep, "preview": clean[:8]}
    guard_demo(user, "Importing data")
    replace_sales(user["org"], clean); set_data_mode(user["org"], "real"); invalidate(user["org"])
    log(user, f"imported sales file '{b.filename or 'CSV'}' ({rep['rows']} rows)")
    return rep

@app.post("/api/upload/customers")
def upload_customers(b: Up, user=Depends(auth)):
    """Import customer-level data so the churn model trains on this organization's own customers."""
    need(user, "admin", "analyst")
    rows, rep = _read(b, ingest.ingest_customers)
    if not rows: raise HTTPException(422, "No valid customer rows found")
    X = np.array([[r["tenure"], r["orders"], r["tickets"], r["idle"]] for r in rows])
    y = np.array([np.nan if r["churned"] is None else r["churned"] for r in rows])
    try: an.churn_model(X, y, [r["ext_id"] for r in rows])
    except ValueError as e: raise HTTPException(422, str(e))
    if b.dry_run: return {**rep, "preview": rows[:8]}
    guard_demo(user, "Importing data")
    replace_customers(user["org"], rows); _CHURN.pop(user["org"], None)
    log(user, f"imported customer file '{b.filename or 'CSV'}' ({len(rows)} customers)")
    return rep

@app.get("/api/dataset")
def dataset(user=Depends(auth)):
    ctx = context(user)
    return {"data_mode": get_data_mode(user["org"]), "demo_org": user["org"] == orgs.DEMO["org"], "customers": len(load_customers(user["org"])),
            "sales": {"rows": ctx["rows"], "months": len(ctx["months"]), "range": [ctx["months"][0], ctx["months"][-1]],
                      "regions": ctx["regions"], "products": ctx["products"]} if ctx else None}

@app.post("/api/reset")
def reset(user=Depends(auth)):
    need(user, "admin"); replace_sales(user["org"], build()); set_data_mode(user["org"], "demo"); invalidate(user["org"])
    log(user, "loaded demo data")
    return {"ok": True, "rows": len(rows())}

@app.get("/api/export")
def export(user=Depends(auth)):
    log(user, "exported data")
    return {"content": "month,region,product,revenue,customers\n" + "\n".join(
        f"{r['month']},{r['region']},{r['product']},{r['revenue']},{r['customers']}" for r in rows())}

class WI(BaseModel):
    price: float = Field(0, ge=-50, le=50); marketing: float = Field(0, ge=-100, le=200); churn: float = Field(0, ge=-50, le=50)
    elasticity: float = Field(-1.2, ge=-3, le=0); horizon: int = Field(6, ge=1, le=12)

@app.post("/api/whatif")
def whatif(b: WI, user=Depends(auth)):
    ctx = context(user)
    if not ctx:
        return {"base": [], "scenario": [], "months": [], "delta": 0, "bridge": [],
                "assumptions": "Insufficient data. Import your sales data to simulate business scenarios."}
    base = an.forecast(ctx["revenue"], b.horizon, ctx["forecast"]["model_key"])[0]
    vol_price, vol_mkt, vol_churn = b.elasticity * b.price / 100, 0.25 * b.marketing / 100, -0.6 * b.churn / 100
    f = (1 + b.price / 100) * (1 + vol_price + vol_mkt + vol_churn); sc = [round(x * f) for x in base]; tb = sum(base)
    bridge = [{"label": "Price (margin)", "value": round(tb * b.price / 100)},
              {"label": "Price (volume)", "value": round(tb * (1 + b.price / 100) * vol_price)},
              {"label": "Marketing", "value": round(tb * (1 + b.price / 100) * vol_mkt)},
              {"label": "Churn", "value": round(tb * (1 + b.price / 100) * vol_churn)}]
    return {"months": an.next_months(ctx["months"][-1], b.horizon), "base": [round(x) for x in base], "scenario": sc,
            "delta": sum(sc) - round(tb), "delta_pct": round((f - 1) * 100, 2), "bridge": bridge,
            "assumptions": f"Price elasticity {b.elasticity}, marketing lift +0.25, churn impact −0.6 (adjustable assumptions)."}

_CHURN = {}   # per-organization trained churn model
@app.get("/api/churn")
def churn(user=Depends(auth)):
    """Train on the organization's own customers; the demo dataset uses a synthetic customer base."""
    org = user["org"]
    if org not in _CHURN:
        cust = load_customers(org)
        if cust:
            X = np.array([[c["tenure"], c["orders"], c["tickets"], c["idle"]] for c in cust])
            y = np.array([np.nan if c["churned"] is None else c["churned"] for c in cust])
            try: _CHURN[org] = {"available": True, "source": "your customers", **an.churn_model(X, y, [c["ext_id"] for c in cust], score_active_only=True)}
            except ValueError as e: return {"available": False, "reason": str(e)}
        elif get_data_mode(org) == "demo":
            _CHURN[org] = {"available": True, "source": "demo customer base", **an.churn_model()}
        else:
            return {"available": False, "reason": "Import customer-level data (tenure, orders per month, support tickets, days since last order, churned) to train the churn model on your own customers."}
    return _CHURN[org]

class Al(BaseModel): name: str = Field(min_length=1, max_length=120); metric: str; op: str; threshold: float
METRICS = ("mom_pct", "last_month", "customers", "ytd_growth_pct")

@app.get("/api/alerts")
def alerts(user=Depends(auth)):
    ctx = context(user); cur = {k: ctx["kpis"][k] for k in METRICS} if ctx else {}; out = []
    for a in load_alerts(user["org"]):
        v = cur.get(a["metric"])
        out.append({**a, "value": v, "firing": v is not None and (v < a["threshold"] if a["op"] == "<" else v > a["threshold"])})
    return out

@app.post("/api/alerts")
def add_alert(b: Al, user=Depends(auth)):
    need(user, "admin", "analyst"); guard_demo(user, "Creating alerts")
    if b.metric not in METRICS: raise HTTPException(422, "Invalid metric")
    if b.op not in ("<", ">"): raise HTTPException(422, "Invalid operator")
    save_alert(user["org"], b.name, b.metric, b.op, b.threshold); log(user, f"created alert '{b.name}'")
    return {"ok": True}

@app.delete("/api/alerts/{aid}")
def remove_alert(aid: int, user=Depends(auth)):
    need(user, "admin", "analyst"); guard_demo(user, "Deleting alerts")
    if not delete_alert(user["org"], aid): raise HTTPException(404, "Alert not found")
    log(user, "deleted an alert")
    return {"ok": True}

app.mount("/static", StaticFiles(directory="static"), name="static")
@app.get("/")
def index(): return FileResponse("static/index.html")
