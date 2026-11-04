"""AI analyst: a deterministic intent engine that computes every number and shows its work,
optionally narrated by Claude (set ANTHROPIC_API_KEY or AETHER_LLM=1). Claude never invents numbers:
it only rewrites the facts the engine already computed."""
import json, os, re

MODEL = "claude-opus-5-5"
MONTHS = {"01": r"jan(uary)?|ene(ro)?", "02": r"feb(ruary|rero)?", "03": r"mar(ch|zo)?", "04": r"apr(il)?|abr(il)?",
          "05": r"may(o)?", "06": r"jun(e|io)?", "07": r"jul(y|io)?", "08": r"aug(ust)?|ago(sto)?",
          "09": r"sep(t|tember|tiembre)?|set(iembre)?", "10": r"oct(ober|ubre)?", "11": r"nov(ember|iembre)?", "12": r"dec(ember)?|dic(iembre)?"}
SUGGESTIONS = ["Why did revenue decline in September?", "Which region is growing fastest?", "What's the forecast for next quarter?",
               "Were there any anomalies?", "Which product drives the most revenue?", "Give me an executive summary"]

def _usd(v): return f"${v:,.0f}"

def _find_month(q, months):
    if m := re.search(r"\b(20\d\d)-(0[1-9]|1[0-2])\b", q):
        if m.group(0) in months: return m.group(0)
    for num, pat in MONTHS.items():
        if re.search(rf"\b({pat})\b", q):
            c = [x for x in months if x.endswith("-" + num)]
            if c: return c[-1]
    return None

def _has(q, *words): return any(w in q for w in words)

# ---------- intents ----------

def _explain_month(ctx, cur):
    months, m = ctx["months"], ctx["monthly"]; i = months.index(cur)
    if i == 0: return _summary(ctx)
    prev = months[i - 1]; d = m[cur] - m[prev]; pct = d / m[prev] * 100; drivers = []
    for key, values in (("region", ctx["regions"]), ("product", ctx["products"])):
        mk = ctx["by_" + key]
        for v in values:
            a, b = mk.get((prev, v), 0), mk.get((cur, v), 0)
            if a: drivers.append((b - a, key, v, (b - a) / a * 100))
    drivers.sort(); worst, best = drivers[:2], drivers[-2:][::-1]
    calc = [f"SELECT month, SUM(revenue) FROM sales WHERE month IN ('{prev}','{cur}') GROUP BY month;",
            f"-- {prev}: {_usd(m[prev])}  →  {cur}: {_usd(m[cur])}  (Δ {d:+,.0f}, {pct:+.1f}%)",
            f"SELECT region, product, SUM(revenue) FROM sales WHERE month IN ('{prev}','{cur}') GROUP BY 1, 2;  -- contribution analysis",
            *[f"-- {k} {v}: {dv:+,.0f} ({dp:+.1f}%)" for dv, k, v, dp in (worst if d < 0 else best)]]
    if d < 0:
        ans = (f"Revenue **declined {abs(pct):.1f}%** in {cur}, {_usd(abs(d))} below {prev}. The largest negative contributions were "
               + " and ".join(f"{k} **{v}** ({dv:+,.0f} USD, {dp:+.1f}%)" for dv, k, v, dp in worst)
               + ". Recommendation: investigate availability or checkout incidents on the weakest channel and launch a retention campaign for the affected plan.")
    else:
        ans = (f"Revenue **grew {pct:.1f}%** in {cur}, {_usd(d)} above {prev}. The strongest contributors were "
               + " and ".join(f"{k} **{v}** ({dv:+,.0f} USD, {dp:+.1f}%)" for dv, k, v, dp in best) + ".")
    win = months[max(0, i - 5): i + 1]
    return {"answer": ans, "calculations": calc,
            "chart": {"type": "bar", "title": f"Monthly revenue around {cur}", "labels": win, "data": [m[x] for x in win], "highlight": win.index(cur)},
            "followups": [f"Which region is growing fastest?", "Were there any anomalies?"]}

def _ranking(ctx, key):
    months = ctx["months"]; last12, prev12 = months[-12:], months[-24:-12]; mk = ctx["by_" + key]
    values = ctx["regions" if key == "region" else "products"]
    tot = {v: sum(mk.get((mm, v), 0) for mm in last12) for v in values}
    yoy = {v: (tot[v] / s - 1) * 100 for v in values if (s := sum(mk.get((mm, v), 0) for mm in prev12))}
    order = sorted(values, key=lambda v: -tot[v]); total = sum(tot.values()) or 1
    fast = max(yoy, key=yoy.get) if yoy else order[0]
    ans = (f"Over the last 12 months **{order[0]}** is the largest {key} with {_usd(tot[order[0]])} ({tot[order[0]] / total * 100:.0f}% of revenue). "
           + (f"The fastest-growing {key} is **{fast}** at {yoy[fast]:+.1f}% year over year" if yoy else "")
           + (f", while **{min(yoy, key=yoy.get)}** grows slowest ({yoy[min(yoy, key=yoy.get)]:+.1f}%)." if len(yoy) > 1 else "."))
    calc = [f"SELECT {key}, SUM(revenue) FROM sales WHERE month BETWEEN '{last12[0]}' AND '{last12[-1]}' GROUP BY {key} ORDER BY 2 DESC;",
            *[f"-- {v}: {_usd(tot[v])}" + (f"  (YoY {yoy[v]:+.1f}%)" if v in yoy else "") for v in order]]
    return {"answer": ans, "calculations": calc,
            "chart": {"type": "bar", "title": f"Revenue by {key}, last 12 months", "labels": order, "data": [tot[v] for v in order]},
            "followups": ["Which product drives the most revenue?" if key == "region" else "Which region is growing fastest?", "What's the forecast for next quarter?"]}

def _forecast(ctx):
    f = ctx["forecast"]; last = ctx["revenue"][-1]; tot = sum(f["values"])
    ans = (f"The **{f['model']}** model projects **{_usd(tot)}** over the next {len(f['values'])} months "
           f"({', '.join(f'{mm}: {_usd(v)}' for mm, v in zip(f['months'], f['values']))}). "
           f"Next month is {(f['values'][0] / last - 1) * 100:+.1f}% vs the last actual month. "
           f"Backtested error (MAPE) is {f['mape']}%, with a 90% prediction band of {_usd(f['lower'][0])} – {_usd(f['upper'][0])} for next month.")
    calc = ["y(t) = β₀ + β₁·t + β₂·sin(2πt/12) + β₃·cos(2πt/12) + ε   -- fitted by least squares",
            f"-- residual σ used for a 90% band (z = 1.64, widening with √horizon)", *[f"-- {mm}: {_usd(v)}" for mm, v in zip(f["months"], f["values"])]]
    return {"answer": ans, "calculations": calc,
            "chart": {"type": "line", "title": "Last 6 months + forecast", "labels": ctx["months"][-6:] + f["months"],
                      "data": ctx["revenue"][-6:] + f["values"], "split": 6},
            "followups": ["Were there any anomalies?", "Give me an executive summary"]}

def _anomalies(ctx):
    a = ctx["anomalies"]
    if not a:
        return {"answer": "No statistically significant anomalies: every month-over-month change is within 3.5 robust standard deviations of the median.",
                "calculations": ["z = 0.6745 · (gᵢ − median(g)) / MAD(g)   -- flag |z| > 3.5"], "followups": ["Give me an executive summary"]}
    parts = [f"**{x['month']}** ({x['change_pct']:+.1f}% MoM, z = {x['score']}" + (f", mostly {x['driver']['region']}" if x.get("driver") else "") + ")" for x in a]
    return {"answer": f"I found {len(a)} anomal{'y' if len(a) == 1 else 'ies'}: " + "; ".join(parts) + ". These months deviate strongly from the typical growth pattern and are worth a root-cause review.",
            "calculations": ["g = diff(revenue) / revenue[:-1]   -- month-over-month growth",
                             "z = 0.6745 · (gᵢ − median(g)) / MAD(g)   -- robust z-score, flag |z| > 3.5",
                             *[f"-- {x['month']}: g = {x['change_pct']}%, z = {x['score']} ({x['severity']})" for x in a]],
            "followups": [f"Why did revenue change in {a[-1]['month']}?", "Which region is growing fastest?"]}

def _summary(ctx):
    k, f = ctx["kpis"], ctx["forecast"]
    ans = (f"**{ctx['org']}** generated {_usd(k['revenue_total'])} across {len(ctx['months'])} months. Last month closed at {_usd(k['last_month'])} "
           f"({k['mom_pct']:+.1f}% MoM) and trailing-12-month growth is {k['ytd_growth_pct']:+.1f}%. "
           f"{len(ctx['anomalies'])} anomal{'y was' if len(ctx['anomalies']) == 1 else 'ies were'} detected, and the model expects {_usd(sum(f['values']))} over the next quarter.")
    return {"answer": ans, "calculations": ["SELECT SUM(revenue), COUNT(DISTINCT month) FROM sales;",
                                            f"-- MoM = {k['last_month']:,} / previous − 1 = {k['mom_pct']}%",
                                            f"-- TTM growth = Σ last 12 / Σ previous 12 − 1 = {k['ytd_growth_pct']}%"],
            "followups": SUGGESTIONS[:3]}

def engine(q, ctx):
    ql = q.lower()
    if _has(ql, "anomal", "outlier", "unusual", "atípic", "atipic"): r = _anomalies(ctx)
    elif _has(ql, "forecast", "predict", "next quarter", "next month", "future", "pronóst", "pronost", "proyecc"): r = _forecast(ctx)
    elif (cur := _find_month(ql, ctx["months"])): r = _explain_month(ctx, cur)
    elif _has(ql, "region", "región", "channel", "canal"): r = _ranking(ctx, "region")
    elif _has(ql, "product", "producto", "plan"): r = _ranking(ctx, "product")
    elif _has(ql, "why", "decline", "drop", "fell", "por qué", "porque", "cayó", "cayo"): r = _explain_month(ctx, (ctx["anomalies"] or [{"month": ctx["months"][-1]}])[-1]["month"])
    else: r = _summary(ctx)
    r.setdefault("chart", None)
    r["sources"] = [f"table: sales ({ctx['rows']} rows, {len(ctx['months'])} months)", "engine: aether-analytics (deterministic)"]
    r["engine"] = "aether-engine"
    return r

# ---------- optional Claude narration ----------

SYSTEM = ("You are AETHER, a senior business analyst embedded in a BI platform. You receive a user question and FACTS computed by a "
          "deterministic analytics engine. Answer in the user's language, in 2-4 sentences, executive tone. Use ONLY numbers present in FACTS - "
          "never invent or recompute figures. Wrap the 1-3 most important entities or figures in **double asterisks**. End with one concrete recommendation when relevant.")

def _client():
    if not (os.getenv("ANTHROPIC_API_KEY") or os.getenv("AETHER_LLM") == "1"): return None
    try:
        import anthropic
        return anthropic.Anthropic(timeout=30.0, max_retries=1)
    except Exception:
        return None

def llm_enabled(): return bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("AETHER_LLM") == "1")

def answer(q, ctx):
    r = engine(q, ctx); client = _client()
    if not client: return r
    facts = {"org": ctx["org"], "kpis": ctx["kpis"], "engine_answer": r["answer"], "calculations": r["calculations"], "chart": r["chart"]}
    try:
        msg = client.beta.messages.create(
            model=MODEL, max_tokens=1024, system=SYSTEM,
            output_config={"effort": "low"},
            betas=["server-side-fallback-2026-07-01"], fallbacks="default",
            messages=[{"role": "user", "content": f"QUESTION: {q}\n\nFACTS:\n{json.dumps(facts, default=str)}"}])
        if msg.stop_reason == "refusal": return r
        text = "".join(b.text for b in msg.content if b.type == "text").strip()
        if text:
            r["answer"] = text; r["engine"] = MODEL
            r["sources"].append(f"narration: {msg.model} (grounded on the engine's facts)")
    except Exception:
        pass   # the deterministic answer is always a valid fallback
    return r
