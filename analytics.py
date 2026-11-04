"""Analytics engine: forecasting models, backtesting, anomaly detection, churn model and automatic insights.

Pure functions over plain Python lists / dicts, so they are easy to test and reuse."""
import numpy as np

# ---------- forecasting models ----------

def _design(t):
    t = np.asarray(t, float)
    return np.c_[t, np.ones_like(t), np.sin(2 * np.pi * t / 12), np.cos(2 * np.pi * t / 12)]

def ols_seasonal(y, h):
    """Linear trend + annual Fourier seasonality, fitted by least squares."""
    y = np.asarray(y, float); A = _design(np.arange(len(y)))
    w, *_ = np.linalg.lstsq(A, y, rcond=None)
    return _design(np.arange(len(y), len(y) + h)) @ w, y - A @ w

def naive(y, h):
    y = np.asarray(y, float)
    return np.repeat(y[-1], h), np.diff(y)

def seasonal_naive(y, h):
    y = np.asarray(y, float)
    if len(y) < 12: return naive(y, h)
    return np.array([y[len(y) - 12 + i % 12] for i in range(h)]), y[12:] - y[:-12]

def holt(y, h):
    """Holt's linear exponential smoothing; (alpha, beta) chosen by one-step-ahead SSE grid search."""
    y = np.asarray(y, float); best = None
    for a in (0.2, 0.4, 0.6, 0.8):
        for b in (0.05, 0.1, 0.2, 0.3):
            lv, tr, res = y[0], y[1] - y[0], []
            for v in y[1:]:
                p = lv + tr; res.append(v - p)
                nl = a * v + (1 - a) * (lv + tr); tr = b * (nl - lv) + (1 - b) * tr; lv = nl
            sse = float(np.sum(np.square(res)))
            if best is None or sse < best[0]: best = (sse, lv, tr, np.array(res))
    _, lv, tr, res = best
    return lv + tr * np.arange(1, h + 1), res

MODELS = {
    "ols_seasonal": ("Trend + seasonality (OLS)", ols_seasonal),
    "holt": ("Holt exponential smoothing", holt),
    "seasonal_naive": ("Seasonal naive", seasonal_naive),
    "naive": ("Naive (last value)", naive),
}

def forecast(series, h=3, model="ols_seasonal"):
    """Point forecast, residual std and in-sample MAPE (kept for backwards compatibility)."""
    y = np.asarray(series, float); f, res = MODELS[model][1](y, h)
    mape = float(np.mean(np.abs(res / y[-len(res):])) * 100) if len(res) else 0.0
    return f.tolist(), float(np.std(res)) if len(res) else 0.0, mape

def _metrics(actual, pred):
    a, p = np.asarray(actual, float), np.asarray(pred, float)
    return {"mape": round(float(np.mean(np.abs((a - p) / a)) * 100), 2),
            "rmse": round(float(np.sqrt(np.mean((a - p) ** 2)))),
            "bias": round(float(np.mean(p - a)))}

def backtest(series, h=3, folds=4):
    """Rolling-origin cross-validation: refit every model on an expanding window and score the next h months."""
    y = np.asarray(series, float); n = len(y); out = {}
    origins = [o for o in range(n - h - folds + 1, n - h + 1) if o >= 8]
    for key, (label, fn) in MODELS.items():
        errs = [_metrics(y[o:o + h], fn(y[:o], h)[0]) for o in origins]
        out[key] = {"label": label,
                    "mape": round(float(np.mean([e["mape"] for e in errs])), 2) if errs else None,
                    "rmse": round(float(np.mean([e["rmse"] for e in errs]))) if errs else None,
                    "bias": round(float(np.mean([e["bias"] for e in errs]))) if errs else None}
    ranked = sorted((k for k in out if out[k]["mape"] is not None), key=lambda k: out[k]["mape"])
    return out, ranked, len(origins)

def holdout_paths(series, hold=6):
    """Each model trained without the last `hold` months, predicting them (for the backtest chart)."""
    y = np.asarray(series, float); hold = min(hold, max(1, len(y) - 8))
    return {k: [round(float(v)) for v in fn(y[:-hold], hold)[0]] for k, (_, fn) in MODELS.items()}, hold

def intervals(values, sd, z=1.64):
    """Prediction band that widens with the horizon (sd * sqrt(step))."""
    return ([round(v - z * sd * np.sqrt(i + 1)) for i, v in enumerate(values)],
            [round(v + z * sd * np.sqrt(i + 1)) for i, v in enumerate(values)])

def next_months(last, h):
    y, m = map(int, last.split("-")); out = []
    for _ in range(h):
        m += 1
        if m > 12: y, m = y + 1, 1
        out.append(f"{y}-{m:02d}")
    return out

# ---------- anomaly detection ----------

def anomalies(months, vals, by_region=None, threshold=3.5):
    """Robust z-score (median / MAD) on month-over-month growth, with the region that explains most of it."""
    if len(vals) < 4: return []
    g = np.diff(vals) / np.asarray(vals[:-1], float); med = np.median(g)
    mad = np.median(np.abs(g - med)) or 1e-9; out = []
    for i, gi in enumerate(g):
        z = 0.6745 * (gi - med) / mad
        if abs(z) <= threshold: continue
        cur, prev = months[i + 1], months[i]; driver = None
        if by_region:
            deltas = {r: s[i + 1] - s[i] for r, s in by_region.items()}
            r = min(deltas, key=deltas.get) if gi < 0 else max(deltas, key=deltas.get)
            driver = {"region": r, "delta": round(deltas[r]), "share": round(abs(deltas[r]) / (abs(vals[i + 1] - vals[i]) or 1) * 100)}
        out.append({"month": cur, "prev": prev, "score": round(float(z), 1), "change_pct": round(float(gi * 100), 1),
                    "severity": "critical" if abs(z) > 7 else "high" if abs(z) > 5 else "medium", "driver": driver})
    return out

# ---------- churn model ----------

def _auc(y, p):
    order = np.argsort(p); ranks = np.empty(len(p)); ranks[order] = np.arange(1, len(p) + 1)
    pos = y == 1; n1, n0 = pos.sum(), (~pos).sum()
    return float((ranks[pos].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)) if n1 and n0 else 0.5

def churn_model(n=600, seed=3):
    """Logistic regression trained by batch gradient descent on a synthetic customer base, evaluated on a 30% holdout."""
    rg = np.random.default_rng(seed)
    X = np.c_[rg.integers(1, 48, n), rg.poisson(4, n), rg.integers(0, 6, n), rg.integers(0, 90, n)].astype(float)
    names = ["tenure", "orders/month", "support tickets", "days since last order"]
    true = np.array([-.9, -.8, .9, 1.1])
    mu, sd = X.mean(0), X.std(0); Z = (X - mu) / sd
    y = (rg.random(n) < 1 / (1 + np.exp(-(Z @ true - .6)))).astype(float)
    idx = rg.permutation(n); cut = int(n * .7); tr, te = idx[:cut], idx[cut:]
    w, c, curve = np.zeros(4), 0.0, []
    for epoch in range(600):
        p = 1 / (1 + np.exp(-(Z[tr] @ w + c)))
        w -= .1 * Z[tr].T @ (p - y[tr]) / len(tr); c -= .1 * (p - y[tr]).mean()
        if epoch % 30 == 0:
            curve.append(round(float(-np.mean(y[tr] * np.log(p + 1e-9) + (1 - y[tr]) * np.log(1 - p + 1e-9))), 4))
    prob = 1 / (1 + np.exp(-(Z @ w + c))); pt, yt = prob[te], y[te]; pred = pt > .5
    tp, fp = int((pred & (yt == 1)).sum()), int((pred & (yt == 0)).sum())
    fn, tn = int((~pred & (yt == 1)).sum()), int((~pred & (yt == 0)).sum())
    prec = tp / (tp + fp) if tp + fp else 0; rec = tp / (tp + fn) if tp + fn else 0
    roc = []
    for th in np.linspace(1, 0, 21):
        pr = pt >= th
        roc.append([round(float((pr & (yt == 0)).sum() / max(1, (yt == 0).sum())), 3),
                    round(float((pr & (yt == 1)).sum() / max(1, (yt == 1).sum())), 3)])
    actions = {"tenure": "Onboarding call + loyalty perk", "orders/month": "Re-engagement offer on favourite category",
               "support tickets": "Escalate to senior support, close open tickets", "days since last order": "Win-back email with time-limited discount"}
    top = np.argsort(-prob)[:12]; at_risk = []
    for i in top:
        contrib = w * Z[i]; reason = names[int(np.argmax(contrib))]
        at_risk.append({"id": f"CUST-{1000 + int(i)}", "prob": round(float(prob[i]) * 100, 1), "tenure": int(X[i, 0]),
                        "orders": int(X[i, 1]), "tickets": int(X[i, 2]), "idle_days": int(X[i, 3]),
                        "reason": reason, "action": actions[reason],
                        "contrib": [round(float(v), 2) for v in contrib]})
    base = float(y.mean())
    return {"accuracy": round(float((pred == yt).mean() * 100), 1), "precision": round(prec * 100, 1), "recall": round(rec * 100, 1),
            "f1": round(2 * prec * rec / (prec + rec) * 100, 1) if prec + rec else 0, "auc": round(_auc(yt, pt), 3),
            "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn}, "roc": roc, "loss_curve": curve,
            "train_size": len(tr), "test_size": len(te), "base_rate": round(base * 100, 1),
            "features": names, "weights": [round(float(x), 2) for x in w], "bias": round(float(c), 2),
            "at_risk": at_risk, "segments": _segments(prob)}

def _segments(prob):
    b = [(0, 30, "Low"), (30, 60, "Medium"), (60, 80, "High"), (80, 101, "Critical")]
    return [{"label": l, "count": int(((prob * 100 >= lo) & (prob * 100 < hi)).sum())} for lo, hi, l in b]

# ---------- automatic insights ----------

def insights(months, vals, by_region, by_product, anoms, fc_values):
    """Short, ranked, human-readable findings computed from the data (no LLM involved)."""
    out = []
    if len(vals) >= 24:
        yoy = (sum(vals[-12:]) / sum(vals[-24:-12]) - 1) * 100
        out.append({"tone": "up" if yoy >= 0 else "down", "icon": "trend", "title": f"Revenue {'up' if yoy >= 0 else 'down'} {abs(yoy):.1f}% year over year",
                    "detail": f"Last 12 months: ${sum(vals[-12:]):,.0f} vs ${sum(vals[-24:-12]):,.0f} the year before."})
    if by_region and len(months) >= 24:
        g = {r: (sum(s[-12:]) / sum(s[-24:-12]) - 1) * 100 for r, s in by_region.items() if sum(s[-24:-12])}
        if g:
            best = max(g, key=g.get); worst = min(g, key=g.get)
            out.append({"tone": "up", "icon": "region", "title": f"{best} is the fastest-growing region",
                        "detail": f"{g[best]:+.1f}% over the last 12 months vs the year before. {worst} trails at {g[worst]:+.1f}%."})
    if by_product:
        tot = {p: sum(s[-3:]) for p, s in by_product.items()}; all_ = sum(tot.values()) or 1
        top = max(tot, key=tot.get)
        out.append({"tone": "neutral", "icon": "product", "title": f"{top} drives {tot[top] / all_ * 100:.0f}% of recent revenue",
                    "detail": "Share of the last 3 months. Concentration risk: " + ("high" if tot[top] / all_ > .5 else "moderate") + "."})
    if anoms:
        a = anoms[-1]; d = a.get("driver")
        out.append({"tone": "down" if a["change_pct"] < 0 else "up", "icon": "alert", "title": f"Anomaly in {a['month']}: {a['change_pct']:+.1f}% MoM",
                    "detail": f"Robust z-score {a['score']}." + (f" {d['region']} explains ~{d['share']}% of the move." if d else "")})
    if fc_values and vals:
        nxt = (fc_values[0] / vals[-1] - 1) * 100
        out.append({"tone": "up" if nxt >= 0 else "down", "icon": "forecast", "title": f"Next month forecast: ${fc_values[0]:,.0f}",
                    "detail": f"{nxt:+.1f}% vs last month, driven by trend and annual seasonality."})
    return out
