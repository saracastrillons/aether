"""AI analyst.

Two modes, same guarantees (every number is computed by code, never by a language model):
- Agent mode (ANTHROPIC_API_KEY set): Claude plans the analysis and calls the analytics tools below,
  then writes the answer in the user's language from the tool results. Each tool call is shown in the trace.
- Engine mode (no key, or any API failure): a deterministic intent engine answers on its own."""
import json, os, re
import analytics as an

MODEL = "claude-opus-5-5"
MAX_STEPS = 6
MONTHS = {"01": r"jan(uary)?|ene(ro)?", "02": r"feb(ruary|rero)?", "03": r"mar(ch|zo)?", "04": r"apr(il)?|abr(il)?",
          "05": r"may(o)?", "06": r"jun(e|io)?", "07": r"jul(y|io)?", "08": r"aug(ust)?|ago(sto)?",
          "09": r"sep(t|tember|tiembre)?|set(iembre)?", "10": r"oct(ober|ubre)?", "11": r"nov(ember|iembre)?", "12": r"dec(ember)?|dic(iembre)?"}
SUGGESTIONS = ["Why did revenue decline in September?", "Which region is growing fastest?", "What's the forecast for next quarter?",
               "Compare 2024 vs 2025", "What was our best month?", "Give me an executive summary"]

def _usd(v): return ("-$" if v < 0 else "$") + f"{abs(v):,.0f}"
def _has(q, *words): return any(w in q for w in words)
def _pct(a, b): return (a / b - 1) * 100 if b else 0.0

# =====================================================================
#  Shared computations (used by both the engine and the agent tools)
# =====================================================================

def aggregate(ctx, start=None, end=None, group_by="total", region=None, product=None):
    rows = [r for r in ctx["data"] if (not start or r["month"] >= start) and (not end or r["month"] <= end)
            and (not region or r["region"].lower() == region.lower()) and (not product or r["product"].lower() == product.lower())]
    key = {"month": lambda r: r["month"], "year": lambda r: r["month"][:4], "region": lambda r: r["region"],
           "product": lambda r: r["product"], "total": lambda r: "total"}[group_by]
    out = {}
    for r in rows:
        k = key(r); o = out.setdefault(k, {"revenue": 0, "customers": 0}); o["revenue"] += r["revenue"]; o["customers"] += r["customers"]
    order = sorted(out) if group_by in ("month", "year") else sorted(out, key=lambda k: -out[k]["revenue"])
    where = " AND ".join(x for x in [f"month >= '{start}'" if start else "", f"month <= '{end}'" if end else "",
                                     f"region = '{region}'" if region else "", f"product = '{product}'" if product else ""] if x)
    col = {"month": "month", "year": "SUBSTR(month, 1, 4)", "region": "region", "product": "product"}.get(group_by)
    sql = f"SELECT {col + ', ' if col else ''}SUM(revenue), SUM(customers) FROM sales{' WHERE ' + where if where else ''}{f' GROUP BY 1' if col else ''};"
    return [{"key": k, **out[k]} for k in order], len(rows), sql

def drivers(ctx, cur, prev):
    out = []
    for key, values in (("region", ctx["regions"]), ("product", ctx["products"])):
        if len(values) < 2: continue
        mk = ctx["by_" + key]
        for v in values:
            a, b = mk.get((prev, v), 0), mk.get((cur, v), 0)
            out.append({"dimension": key, "value": v, "delta": b - a, "pct": round(_pct(b, a), 1) if a else None})
    return sorted(out, key=lambda d: d["delta"])

def find_entity(q, ctx):
    for key in ("regions", "products"):
        for v in sorted(ctx[key], key=len, reverse=True):
            if len(ctx[key]) > 1 and len(v) > 2 and re.search(rf"\b{re.escape(v.lower())}\b", q): return key[:-1], v
    return None

def _find_month(q, months):
    if m := re.search(r"\b(20\d\d)-(0[1-9]|1[0-2])\b", q):
        if m.group(0) in months: return m.group(0)
    years = re.findall(r"\b(20\d\d)\b", q)
    for num, pat in MONTHS.items():
        if re.search(rf"\b({pat})\b", q):
            c = [x for x in months if x.endswith("-" + num) and (not years or x[:4] in years)]
            if c: return c[-1]
    return None

# =====================================================================
#  Engine mode: deterministic intents
# =====================================================================

def _explain_month(ctx, cur):
    months, m = ctx["months"], ctx["monthly"]; i = months.index(cur)
    if i == 0: return _summary(ctx)
    prev = months[i - 1]; d = m[cur] - m[prev]; pct = _pct(m[cur], m[prev]); dr = drivers(ctx, cur, prev)
    top = dr[:2] if d < 0 else dr[-2:][::-1]
    calc = [f"SELECT month, SUM(revenue) FROM sales WHERE month IN ('{prev}','{cur}') GROUP BY month;",
            f"-- {prev}: {_usd(m[prev])}  →  {cur}: {_usd(m[cur])}  (Δ {d:+,.0f}, {pct:+.1f}%)"]
    if dr:
        calc += [f"SELECT region, product, SUM(revenue) FROM sales WHERE month IN ('{prev}','{cur}') GROUP BY 1, 2;  -- contribution analysis",
                 *[f"-- {x['dimension']} {x['value']}: {x['delta']:+,.0f}" + (f" ({x['pct']:+.1f}%)" if x["pct"] is not None else "") for x in top]]
    parts = " and ".join(f"{x['dimension']} **{x['value']}** ({x['delta']:+,.0f}" + (f", {x['pct']:+.1f}%)" if x["pct"] is not None else ")") for x in top)
    if d < 0:
        ans = f"Revenue **declined {abs(pct):.1f}%** in {cur}, {_usd(abs(d))} below {prev}." + (
            f" The largest negative contributions were {parts}. Recommendation: investigate availability or checkout issues on the weakest channel and launch a retention campaign for the affected line." if top else "")
    else:
        ans = f"Revenue **grew {pct:.1f}%** in {cur}, {_usd(d)} above {prev}." + (f" The strongest contributors were {parts}." if top else "")
    win = months[max(0, i - 5): i + 1]
    return {"answer": ans, "calculations": calc,
            "chart": {"type": "bar", "title": f"Monthly revenue around {cur}", "labels": win, "data": [m[x] for x in win], "highlight": win.index(cur)},
            "followups": ["Which region is growing fastest?", "Were there any anomalies?"]}

def _ranking(ctx, key):
    values = ctx["regions" if key == "region" else "products"]
    if len(values) < 2:
        return {"answer": f"Your data has a single {key} (**{values[0]}**), so there is nothing to rank. Add a {key} column to compare segments.",
                "calculations": [f"SELECT COUNT(DISTINCT {key}) FROM sales;  -- = 1"], "followups": ["Give me an executive summary"]}
    months = ctx["months"]; last12, prev12 = months[-12:], months[-24:-12]; mk = ctx["by_" + key]
    tot = {v: sum(mk.get((mm, v), 0) for mm in last12) for v in values}
    yoy = {v: _pct(tot[v], s) for v in values if len(months) >= 24 and (s := sum(mk.get((mm, v), 0) for mm in prev12))}
    order = sorted(values, key=lambda v: -tot[v]); total = sum(tot.values()) or 1
    ans = f"Over the last {len(last12)} months **{order[0]}** is the largest {key} with {_usd(tot[order[0]])} ({tot[order[0]] / total * 100:.0f}% of revenue)."
    if yoy:
        fast, slow = max(yoy, key=yoy.get), min(yoy, key=yoy.get)
        ans += f" The fastest-growing {key} is **{fast}** at {yoy[fast]:+.1f}% year over year" + (f", while **{slow}** grows slowest ({yoy[slow]:+.1f}%)." if len(yoy) > 1 else ".")
    calc = [f"SELECT {key}, SUM(revenue) FROM sales WHERE month BETWEEN '{last12[0]}' AND '{last12[-1]}' GROUP BY {key} ORDER BY 2 DESC;",
            *[f"-- {v}: {_usd(tot[v])}" + (f"  (YoY {yoy[v]:+.1f}%)" if v in yoy else "") for v in order[:10]]]
    return {"answer": ans, "calculations": calc,
            "chart": {"type": "bar", "title": f"Revenue by {key}, last 12 months", "labels": order[:10], "data": [tot[v] for v in order[:10]]},
            "followups": ["Which product drives the most revenue?" if key == "region" else "Which region is growing fastest?", "What's the forecast for next quarter?"]}

def _entity(ctx, kind, name):
    months = ctx["months"]; mk = ctx["by_" + kind]; s = [mk.get((mm, name), 0) for mm in months]
    l12, p12 = sum(s[-12:]), (sum(s[-24:-12]) if len(s) >= 24 else 0); share = l12 / (sum(ctx["revenue"][-12:]) or 1) * 100
    ans = (f"**{name}** generated {_usd(l12)} over the last {min(12, len(months))} months ({share:.0f}% of total revenue)"
           + (f", {_pct(l12, p12):+.1f}% vs the previous 12 months" if p12 else "")
           + f". Last month it brought in {_usd(s[-1])}" + (f" ({_pct(s[-1], s[-2]):+.1f}% MoM)." if len(s) > 1 and s[-2] else "."))
    return {"answer": ans, "calculations": [f"SELECT month, SUM(revenue) FROM sales WHERE {kind} = '{name}' GROUP BY month;",
                                            f"-- last 12m: {_usd(l12)}" + (f" | previous 12m: {_usd(p12)}" if p12 else "")],
            "chart": {"type": "line", "title": f"{name} — monthly revenue", "labels": months[-12:], "data": s[-12:]},
            "followups": [f"Which {kind} is growing fastest?", "What's the forecast for next quarter?"]}

def _years(ctx, years):
    rows, _, sql = aggregate(ctx, group_by="year"); by = {r["key"]: r for r in rows}
    years = [y for y in years if y in by] or list(by)
    counts = {y: sum(1 for m in ctx["months"] if m.startswith(y)) for y in years}
    parts = [f"**{y}**: {_usd(by[y]['revenue'])}" + (f" ({counts[y]} months)" if counts[y] < 12 else "") for y in years]
    ans = "Revenue by year — " + "; ".join(parts) + "."
    if len(years) >= 2:
        a, b = years[-2], years[-1]; ans += f" {b} vs {a}: {_pct(by[b]['revenue'], by[a]['revenue']):+.1f}%."
        if counts[a] != counts[b]: ans += " Note the years cover a different number of months."
    return {"answer": ans, "calculations": [sql, *[f"-- {y}: {_usd(by[y]['revenue'])} across {counts[y]} months" for y in years]],
            "chart": {"type": "bar", "title": "Revenue by year", "labels": years, "data": [by[y]["revenue"] for y in years]},
            "followups": ["What was our best month?", "Which region is growing fastest?"]}

def _extreme(ctx, best):
    m = ctx["monthly"]; k = (max if best else min)(m, key=m.get); avg = sum(m.values()) / len(m)
    return {"answer": f"The {'best' if best else 'weakest'} month was **{k}** with {_usd(m[k])}, {_pct(m[k], avg):+.1f}% vs the monthly average of {_usd(avg)}.",
            "calculations": [f"SELECT month, SUM(revenue) FROM sales GROUP BY month ORDER BY 2 {'DESC' if best else 'ASC'} LIMIT 1;", f"-- {k}: {_usd(m[k])} | average {_usd(avg)}"],
            "chart": {"type": "bar", "title": "Monthly revenue", "labels": ctx["months"][-12:], "data": ctx["revenue"][-12:],
                      "highlight": ctx["months"][-12:].index(k) if k in ctx["months"][-12:] else None},
            "followups": [f"Why did revenue change in {k}?", "Were there any anomalies?"]}

def _customers(ctx):
    c, months = ctx["customers"], ctx["months"]
    ans = f"You had **{c[-1]:,} customers** in {months[-1]} ({_pct(c[-1], c[-2]):+.1f}% MoM)" + (
        f" and {_pct(c[-1], c[-13]):+.1f}% vs a year earlier." if len(c) > 12 and c[-13] else ".") + f" Revenue per customer is ${ctx['kpis']['arpu']:,.2f}."
    return {"answer": ans, "calculations": ["SELECT month, SUM(customers) FROM sales GROUP BY month;", f"-- {months[-1]}: {c[-1]:,} customers"],
            "chart": {"type": "line", "title": "Customers per month", "labels": months[-12:], "data": c[-12:], "unit": "count"},
            "followups": ["Which region is growing fastest?", "Give me an executive summary"]}

def _forecast(ctx):
    f = ctx["forecast"]; last = ctx["revenue"][-1]
    ans = (f"The **{f['model']}** model projects **{_usd(sum(f['values']))}** over the next {len(f['values'])} months "
           f"({', '.join(f'{mm}: {_usd(v)}' for mm, v in zip(f['months'], f['values']))}). Next month is {_pct(f['values'][0], last):+.1f}% vs the last actual month. "
           f"Backtested error (MAPE) is {f['mape']}%, with a 90% band of {_usd(f['lower'][0])} – {_usd(f['upper'][0])} for next month.")
    return {"answer": ans, "calculations": [f"-- model selected by rolling-origin backtest: {f['model']}",
                                            "-- 90% band = forecast ± 1.64 · σ(residuals) · √horizon", *[f"-- {mm}: {_usd(v)}" for mm, v in zip(f["months"], f["values"])]],
            "chart": {"type": "line", "title": "Last 6 months + forecast", "labels": ctx["months"][-6:] + f["months"], "data": ctx["revenue"][-6:] + f["values"], "split": min(6, len(ctx["months"]))},
            "followups": ["Were there any anomalies?", "Give me an executive summary"]}

def _anomalies(ctx):
    a = ctx["anomalies"]
    if not a:
        return {"answer": "No statistically significant anomalies: every month-over-month change is within 3.5 robust standard deviations of the median.",
                "calculations": ["z = 0.6745 · (gᵢ − median(g)) / MAD(g)   -- flag |z| > 3.5"], "followups": ["Give me an executive summary"]}
    parts = [f"**{x['month']}** ({x['change_pct']:+.1f}% MoM, z = {x['score']}" + (f", mostly {x['driver']['region']}" if x.get("driver") else "") + ")" for x in a]
    return {"answer": f"I found {len(a)} anomal{'y' if len(a) == 1 else 'ies'}: " + "; ".join(parts) + ". These months deviate strongly from the typical growth pattern and are worth a root-cause review.",
            "calculations": ["g = diff(revenue) / revenue[:-1]   -- month-over-month growth", "z = 0.6745 · (gᵢ − median(g)) / MAD(g)   -- flag |z| > 3.5",
                             *[f"-- {x['month']}: g = {x['change_pct']}%, z = {x['score']} ({x['severity']})" for x in a]],
            "followups": [f"Why did revenue change in {a[-1]['month']}?", "Which region is growing fastest?"]}

def _summary(ctx):
    k, f = ctx["kpis"], ctx["forecast"]
    ans = (f"**{ctx['org']}** generated {_usd(k['revenue_total'])} across {len(ctx['months'])} months. Last month closed at {_usd(k['last_month'])} "
           f"({k['mom_pct']:+.1f}% MoM)" + (f" and trailing-12-month growth is {k['ytd_growth_pct']:+.1f}%" if len(ctx["months"]) >= 24 else "") + ". "
           f"{len(ctx['anomalies'])} anomal{'y was' if len(ctx['anomalies']) == 1 else 'ies were'} detected, and the model expects {_usd(sum(f['values']))} over the next quarter.")
    return {"answer": ans, "calculations": ["SELECT SUM(revenue), COUNT(DISTINCT month) FROM sales;", f"-- MoM = {k['last_month']:,} / previous − 1 = {k['mom_pct']}%"],
            "followups": SUGGESTIONS[:3]}

def engine(q, ctx):
    ql = q.lower(); years = re.findall(r"\b(20\d\d)\b", ql); ent = find_entity(ql, ctx); month = _find_month(ql, ctx["months"])
    if _has(ql, "anomal", "outlier", "unusual", "atípic", "atipic", "raro"): r = _anomalies(ctx)
    elif _has(ql, "forecast", "predict", "next quarter", "next month", "future", "pronóst", "pronost", "proyecc", "próximo", "proximo", "siguiente"): r = _forecast(ctx)
    elif month: r = _explain_month(ctx, month)
    elif ent: r = _entity(ctx, *ent)
    elif _has(ql, "best month", "mejor mes", "highest month", "record"): r = _extreme(ctx, True)
    elif _has(ql, "worst month", "peor mes", "lowest month"): r = _extreme(ctx, False)
    elif years or _has(ql, "per year", "by year", "por año", "anual", "yearly", "compare", "compar"): r = _years(ctx, years)
    elif _has(ql, "customer", "client"): r = _customers(ctx)
    elif _has(ql, "region", "región", "channel", "canal", "zona", "city", "ciudad"): r = _ranking(ctx, "region")
    elif _has(ql, "product", "producto", "plan", "item"): r = _ranking(ctx, "product")
    elif _has(ql, "why", "decline", "drop", "fell", "por qué", "porque", "cayó", "cayo", "bajó", "bajo"):
        r = _explain_month(ctx, (ctx["anomalies"] or [{"month": ctx["months"][-1]}])[-1]["month"])
    else: r = _summary(ctx)
    r.setdefault("chart", None)
    r["sources"] = [f"table: sales ({ctx['rows']} rows, {len(ctx['months'])} months)"]
    r["engine"] = "aether-engine"
    return r

# =====================================================================
#  Agent mode: Claude + analytics tools
# =====================================================================

TOOLS = [
    {"name": "get_overview", "description": "Dataset scope and headline KPIs: months covered, regions, products, last-month revenue, MoM and 12-month growth, customers, forecast summary and anomaly count. Call this first when you need context.",
     "input_schema": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"name": "query_revenue", "description": "Aggregate revenue and customers from the sales table, optionally filtered by month range (inclusive, YYYY-MM), region and product, grouped by total, month, year, region or product. Use it for any totals, comparisons, rankings or trends.",
     "input_schema": {"type": "object", "properties": {
         "group_by": {"type": "string", "enum": ["total", "month", "year", "region", "product"]},
         "start_month": {"type": "string", "description": "YYYY-MM"}, "end_month": {"type": "string", "description": "YYYY-MM"},
         "region": {"type": "string"}, "product": {"type": "string"}}, "required": ["group_by"], "additionalProperties": False}},
    {"name": "explain_change", "description": "Explain why revenue changed in a month vs a comparison month (default: the previous month), decomposed into region and product contributions.",
     "input_schema": {"type": "object", "properties": {"month": {"type": "string", "description": "YYYY-MM"}, "compare_to": {"type": "string", "description": "YYYY-MM"}},
                      "required": ["month"], "additionalProperties": False}},
    {"name": "get_forecast", "description": "Revenue forecast for the next 1-12 months from the backtested model, with a 90% prediction band and the model's backtested MAPE.",
     "input_schema": {"type": "object", "properties": {"horizon": {"type": "integer", "minimum": 1, "maximum": 12}}, "required": ["horizon"], "additionalProperties": False}},
    {"name": "get_anomalies", "description": "Months whose month-over-month growth is a statistical outlier (robust z-score), with the region that drove each one.",
     "input_schema": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"name": "simulate_scenario", "description": "What-if simulation on the forecast: percentage changes in price, marketing spend and churn. Returns baseline vs scenario revenue and a bridge of each lever's effect.",
     "input_schema": {"type": "object", "properties": {"price_pct": {"type": "number"}, "marketing_pct": {"type": "number"}, "churn_pct": {"type": "number"},
                                                       "horizon": {"type": "integer", "minimum": 1, "maximum": 12}}, "additionalProperties": False}},
    {"name": "get_churn_risk", "description": "Churn model results for this organization's customers: model quality (AUC, precision, recall), what drives churn and the customers most at risk with a recommended action.",
     "input_schema": {"type": "object", "properties": {}, "additionalProperties": False}},
]

def _sql_lines(name, args, res):
    if name == "query_revenue": return [res.pop("_sql")]
    if name == "explain_change": return [f"SELECT region, product, SUM(revenue) FROM sales WHERE month IN ('{res['compare_to']}','{res['month']}') GROUP BY 1, 2;"]
    if name == "get_forecast": return [f"-- forecast({args.get('horizon', 3)}) using {res['model']} · backtested MAPE {res['backtested_mape_pct']}%"]
    if name == "get_anomalies": return ["-- robust z-score on MoM growth, flag |z| > 3.5"]
    return []

def run_tool(name, args, ctx, extras):
    """Execute one tool. Returns (result, chart or None). Raises ValueError for bad input."""
    months = ctx["months"]
    if name == "get_overview":
        return {"organization": ctx["org"], "months": [months[0], months[-1]], "month_count": len(months), "regions": ctx["regions"], "products": ctx["products"],
                "kpis": ctx["kpis"], "forecast_next_3": dict(zip(ctx["forecast"]["months"], ctx["forecast"]["values"])), "anomaly_count": len(ctx["anomalies"])}, None
    if name == "query_revenue":
        g = args.get("group_by", "total")
        for k in ("start_month", "end_month"):
            if args.get(k) and not re.fullmatch(r"\d{4}-\d{2}", args[k]): raise ValueError(f"{k} must be YYYY-MM")
        rows, n, sql = aggregate(ctx, args.get("start_month"), args.get("end_month"), g, args.get("region"), args.get("product"))
        if not n: raise ValueError(f"No rows match. Available months {months[0]}..{months[-1]}, regions {ctx['regions']}, products {ctx['products']}")
        chart = {"type": "line" if g == "month" else "bar", "title": f"Revenue by {g}", "labels": [r["key"] for r in rows][:24], "data": [r["revenue"] for r in rows][:24]} if g != "total" else None
        return {"rows": rows[:60], "matched_rows": n, "_sql": sql}, chart
    if name == "explain_change":
        cur = args["month"]
        if cur not in ctx["monthly"]: raise ValueError(f"Month {cur} not in data ({months[0]}..{months[-1]})")
        prev = args.get("compare_to") or (months[months.index(cur) - 1] if months.index(cur) else None)
        if not prev or prev not in ctx["monthly"]: raise ValueError("No comparison month available")
        m = ctx["monthly"]; win = months[max(0, months.index(cur) - 5): months.index(cur) + 1]
        return {"month": cur, "compare_to": prev, "revenue": m[cur], "previous_revenue": m[prev], "change": m[cur] - m[prev],
                "change_pct": round(_pct(m[cur], m[prev]), 2), "contributions": drivers(ctx, cur, prev)}, \
               {"type": "bar", "title": f"Monthly revenue around {cur}", "labels": win, "data": [m[x] for x in win], "highlight": win.index(cur)}
    if name == "get_forecast":
        h = max(1, min(int(args.get("horizon", 3)), 12)); key = ctx["forecast"]["model_key"]
        f, sd, _ = an.forecast(ctx["revenue"], h, key); lo, hi = an.intervals(f, sd); fm = an.next_months(months[-1], h)
        return {"model": ctx["forecast"]["model"], "backtested_mape_pct": ctx["forecast"]["mape"],
                "forecast": [{"month": a, "expected": round(b), "low_90": c, "high_90": d} for a, b, c, d in zip(fm, f, lo, hi)], "total": round(sum(f))}, \
               {"type": "line", "title": "Recent revenue + forecast", "labels": months[-6:] + fm, "data": ctx["revenue"][-6:] + [round(x) for x in f], "split": min(6, len(months))}
    if name == "get_anomalies":
        return {"anomalies": ctx["anomalies"]}, None
    if name == "simulate_scenario":
        r = extras["whatif"](args.get("price_pct", 0), args.get("marketing_pct", 0), args.get("churn_pct", 0), args.get("horizon", 6))
        return {k: r[k] for k in ("months", "base", "scenario", "delta", "delta_pct", "bridge", "assumptions")}, \
               {"type": "bar", "title": "Scenario vs baseline (total)", "labels": ["Baseline", "Scenario"], "data": [sum(r["base"]), sum(r["scenario"])]}
    if name == "get_churn_risk":
        c = extras["churn"]()
        if not c.get("available", True): return {"available": False, "reason": c.get("reason")}, None
        return {k: c[k] for k in ("source", "auc", "accuracy", "precision", "recall", "base_rate", "features", "weights")} | {"top_at_risk": c["at_risk"][:5]}, None
    raise ValueError(f"Unknown tool {name}")

SYSTEM = """You are AETHER, a senior business analyst inside a BI platform. You answer questions about the user's organization using ONLY the analytics tools provided.

Rules:
- Every number in your answer must come from a tool result in this conversation. Never estimate, invent or do mental math beyond simple differences or percentages of tool numbers.
- Call tools as needed (several in parallel if independent). If a question can't be answered from the data, say what's missing.
- Answer in the same language as the user's question. Be concise: 2-5 sentences for an executive reader, and add a short bullet list only when comparing several items.
- Wrap the 1-3 most important figures or entities in **double asterisks**. Do not use headings or tables.
- End with one concrete, data-grounded recommendation when it adds value.
- Months use the YYYY-MM format in tools. Amounts are in the dataset's currency; format them with a $ sign and thousands separators."""

def _client():
    if not os.getenv("ANTHROPIC_API_KEY"): return None
    try:
        import anthropic
        return anthropic.Anthropic(timeout=60.0, max_retries=2)
    except Exception:
        return None

def llm_enabled(): return bool(os.getenv("ANTHROPIC_API_KEY"))

def _history(history):
    """Plain-text prior turns, trimmed and forced into strict user/assistant alternation starting with user."""
    out = []
    for h in (history or [])[-10:]:
        role = "assistant" if h.get("role") in ("assistant", "ai") else "user"
        text = str(h.get("content") or "")[:2000].strip()
        if not text: continue
        if out and out[-1]["role"] == role: out[-1]["content"] += "\n" + text
        else: out.append({"role": role, "content": text})
    while out and out[0]["role"] != "user": out.pop(0)
    if out and out[-1]["role"] == "user": out.pop()
    return out

def agent(q, ctx, history, extras, client):
    messages = _history(history) + [{"role": "user", "content": q}]
    trace, chart, used = [], None, []
    for _ in range(MAX_STEPS):
        msg = client.beta.messages.create(
            model=MODEL, max_tokens=4096, system=SYSTEM, tools=TOOLS, messages=messages,
            output_config={"effort": "low"}, betas=["server-side-fallback-2026-07-01"], fallbacks="default")
        if msg.stop_reason == "refusal": return None
        messages.append({"role": "assistant", "content": msg.content})
        calls = [b for b in msg.content if b.type == "tool_use"]
        if msg.stop_reason != "tool_use" or not calls: break
        results = []
        for b in calls:
            args = b.input if isinstance(b.input, dict) else {}
            trace.append(f"→ {b.name}({', '.join(f'{k}={v!r}' for k, v in args.items())})"); used.append(b.name)
            try:
                res, ch = run_tool(b.name, args, ctx, extras); chart = ch or chart
                trace += _sql_lines(b.name, args, res)
                results.append({"type": "tool_result", "tool_use_id": b.id, "content": json.dumps(res, default=str)})
            except Exception as e:
                trace.append(f"-- error: {e}")
                results.append({"type": "tool_result", "tool_use_id": b.id, "content": f"Error: {e}", "is_error": True})
        messages.append({"role": "user", "content": results})
    text = "".join(b.text for b in msg.content if b.type == "text").strip()
    if not text: return None
    return {"answer": text, "calculations": trace or ["-- answered from the conversation context, no new computation needed"], "chart": chart,
            "sources": [f"table: sales ({ctx['rows']} rows, {len(ctx['months'])} months)", f"tools: {', '.join(dict.fromkeys(used)) or 'none'}"],
            "engine": getattr(msg, "model", MODEL), "followups": []}

def answer(q, ctx, history=None, extras=None, client=None):
    client = client or _client()
    if client:
        try:
            r = agent(q, ctx, history, extras or {}, client)
            if r:
                r["followups"] = engine(q, ctx).get("followups", [])[:2]
                return r
        except Exception:
            pass   # any API problem: fall back to the deterministic engine
    return engine(q, ctx)
