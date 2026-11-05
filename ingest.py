"""Tolerant file ingestion: CSV (any common delimiter) or Excel, English or Spanish headers,
messy dates and numbers. Produces clean monthly rows plus a report of what was understood."""
import base64, csv, io, re, unicodedata
from datetime import date, datetime

MAX_BYTES = 8_000_000

SALES_FIELDS = {
    "month": ["month", "mes", "date", "fecha", "period", "periodo", "dia", "day", "order_date", "fecha_venta", "invoice_date"],
    "region": ["region", "zona", "zone", "city", "ciudad", "store", "tienda", "channel", "canal", "sucursal", "branch", "country", "pais", "location", "sede"],
    "product": ["product", "producto", "item", "sku", "category", "categoria", "plan", "line", "linea", "service", "servicio", "articulo"],
    "revenue": ["revenue", "ingresos", "ingreso", "ventas", "venta", "sales", "amount", "monto", "total", "valor", "importe", "facturacion", "income"],
    "customers": ["customers", "clientes", "customer_count", "buyers", "compradores", "n_clientes", "num_clientes", "orders", "pedidos"],
}
CUSTOMER_FIELDS = {
    "customer_id": ["customer_id", "id", "cliente", "id_cliente", "customer", "client_id", "codigo", "email"],
    "tenure": ["tenure", "tenure_months", "antiguedad", "antiguedad_meses", "months_active", "meses", "meses_cliente"],
    "orders": ["orders_per_month", "orders", "pedidos_mes", "compras_mes", "pedidos", "compras", "frequency", "frecuencia"],
    "tickets": ["support_tickets", "tickets", "quejas", "reclamos", "complaints", "incidencias", "soporte"],
    "idle": ["days_since_last_order", "idle_days", "recency", "dias_sin_comprar", "dias_inactivo", "dias_ultima_compra", "inactividad"],
    "churned": ["churned", "churn", "abandono", "se_fue", "cancelo", "baja", "perdido", "left"],
}
MONTHS = {"jan": 1, "ene": 1, "feb": 2, "mar": 3, "apr": 4, "abr": 4, "may": 5, "jun": 6, "jul": 7, "aug": 8, "ago": 8,
          "sep": 9, "set": 9, "oct": 10, "nov": 11, "dec": 12, "dic": 12}

class IngestError(ValueError): pass

def norm(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower().strip()
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")

# ---------- reading ----------

def read_table(content=None, content_b64=None, filename=""):
    """Return (header, rows, info) from CSV text or base64 Excel."""
    if content_b64 or filename.lower().endswith((".xlsx", ".xlsm")):
        raw = base64.b64decode(content_b64 or "")
        if len(raw) > MAX_BYTES: raise IngestError("File is larger than 8 MB")
        try:
            from openpyxl import load_workbook
            ws = load_workbook(io.BytesIO(raw), read_only=True, data_only=True).worksheets[0]
            rows = [list(r) for r in ws.iter_rows(values_only=True) if any(c not in (None, "") for c in r)]
        except Exception:
            raise IngestError("Could not read the Excel file. Save it as .xlsx (or CSV) and try again.")
        info = {"format": "Excel", "delimiter": None}
    else:
        text = (content or "").lstrip("﻿")
        if len(text.encode()) > MAX_BYTES: raise IngestError("File is larger than 8 MB")
        sample = "\n".join(text.splitlines()[:20])
        counts = {d: sample.count(d) for d in [",", ";", "\t", "|"]}
        delim = max(counts, key=counts.get) if any(counts.values()) else ","
        rows = [r for r in csv.reader(io.StringIO(text), delimiter=delim) if any(c.strip() for c in r)]
        info = {"format": "CSV", "delimiter": {"\t": "tab"}.get(delim, delim)}
    if len(rows) < 2: raise IngestError("The file has no data rows")
    # skip title rows above the real header (first row with >= 2 non-empty text cells)
    start = next((i for i, r in enumerate(rows[:10]) if sum(isinstance(c, str) and c.strip() != "" for c in r) >= 2), 0)
    return [str(c or "").strip() for c in rows[start]], rows[start + 1:], info

def map_columns(header, fields, required):
    keys = [norm(h) for h in header]; mapping = {}
    for field, syns in fields.items():
        for s in syns:                       # exact synonym first, then "contains" (e.g. "total_ventas_cop")
            hit = next((i for i, k in enumerate(keys) if k == s and i not in mapping.values()), None)
            if hit is None: hit = next((i for i, k in enumerate(keys) if s in k.split("_") and i not in mapping.values()), None)
            if hit is not None: mapping[field] = hit; break
    missing = [f for f in required if f not in mapping]
    if missing:
        raise IngestError(f"Couldn't find a column for: {', '.join(missing)}. Columns found: {', '.join(header)}. "
                          f"Rename them (e.g. {', '.join(fields[m][0] for m in missing)}) or download the template.")
    return mapping

# ---------- value parsing ----------

def parse_number(v):
    if v is None or v == "": raise ValueError
    if isinstance(v, (int, float)): return float(v)
    s = re.sub(r"[^\d,.\-()]", "", str(v))
    neg = s.startswith("(") and s.endswith(")") or s.startswith("-"); s = s.strip("()-")
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    elif "," in s:
        s = s.replace(",", "") if re.fullmatch(r"\d{1,3}(,\d{3})+", s) else s.replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", s):
        s = s.replace(".", "")
    if not s: raise ValueError
    return -float(s) if neg else float(s)

def date_order(values):
    """Decide day-first vs month-first for d/m/y style dates by looking at the whole column."""
    a = b = 0
    for v in values:
        m = re.match(r"^\s*(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})", str(v or ""))
        if m:
            a += int(m.group(1)) > 12; b += int(m.group(2)) > 12
    return "mdy" if b > a else "dmy"

def parse_month(v, order="dmy"):
    if isinstance(v, (datetime, date)): return f"{v.year}-{v.month:02d}"
    if isinstance(v, (int, float)) and 190001 <= v <= 210012: v = str(int(v))
    s = str(v or "").strip().lower()
    if m := re.match(r"^(\d{4})[-/.](\d{1,2})(?:[-/.]\d{1,2})?", s): y, mo = int(m.group(1)), int(m.group(2))
    elif m := re.match(r"^(\d{4})(\d{2})$", s): y, mo = int(m.group(1)), int(m.group(2))
    elif m := re.match(r"^(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})", s):
        d1, d2, y = int(m.group(1)), int(m.group(2)), int(m.group(3)); mo = d2 if order == "dmy" else d1
        y += 2000 if y < 100 else 0
    elif m := re.match(r"^(\d{1,2})[/\-.](\d{4})$", s): mo, y = int(m.group(1)), int(m.group(2))
    elif m := re.match(r"^([a-z]{3})[a-z]*[\s\-/.,]*(?:de\s+)?(\d{2,4})$", s) or re.match(r"^(\d{2,4})[\s\-/.]*([a-z]{3})", s):
        a, b = m.groups(); name, yr = (a, b) if a.isalpha() else (b, a)
        if name not in MONTHS: raise ValueError
        mo, y = MONTHS[name], int(yr) + (2000 if len(yr) == 2 else 0)
    else: raise ValueError
    if not (1 <= mo <= 12 and 1990 <= y <= 2100): raise ValueError
    return f"{y}-{mo:02d}"

# ---------- datasets ----------

def ingest_sales(content=None, content_b64=None, filename=""):
    header, rows, info = read_table(content, content_b64, filename)
    mp = map_columns(header, SALES_FIELDS, ["month", "revenue"])
    order = date_order(r[mp["month"]] for r in rows if len(r) > mp["month"])
    agg, invalid, dup, seen, samples = {}, 0, 0, set(), []
    for r in rows:
        r = list(r) + [None] * (len(header) - len(r))
        key = tuple(str(c) for c in r)
        if key in seen: dup += 1; continue
        seen.add(key)
        try:
            month = parse_month(r[mp["month"]], order); rev = parse_number(r[mp["revenue"]])
            region = str(r[mp["region"]]).strip()[:80] if "region" in mp and r[mp["region"]] not in (None, "") else "All"
            product = str(r[mp["product"]]).strip()[:80] if "product" in mp and r[mp["product"]] not in (None, "") else "All"
            cust = parse_number(r[mp["customers"]]) if "customers" in mp and r[mp["customers"]] not in (None, "") else None
        except (ValueError, IndexError):
            invalid += 1
            if len(samples) < 3: samples.append([str(c) for c in r[:6]])
            continue
        k = (month, region, product); a = agg.setdefault(k, [0.0, 0.0, cust is not None])
        a[0] += rev; a[1] += cust or 0; a[2] = a[2] and cust is not None
    clean = [{"month": m, "region": g, "product": p, "revenue": round(v[0]), "customers": int(v[1]) if v[2] else int(max(v[0], 0) / 85)}
             for (m, g, p), v in sorted(agg.items())]
    months = sorted({r["month"] for r in clean}); total = len(rows)
    return clean, {**info, "columns": {f: header[i] for f, i in mp.items()}, "date_order": order, "rows": total,
                   "kept": total - dup - invalid, "duplicates": dup, "invalid": invalid, "invalid_samples": samples,
                   "aggregated_to": len(clean), "months": len(months), "range": [months[0], months[-1]] if months else None,
                   "regions": sorted({r["region"] for r in clean})[:20], "products": sorted({r["product"] for r in clean})[:20],
                   "estimated_customers": "customers" not in mp,
                   "score": max(0, round(100 - (dup + invalid) / max(1, total) * 100))}

def _bool(v):
    s = norm(v)
    if s in ("1", "true", "yes", "si", "s", "y", "churned", "cancelado", "perdido", "baja"): return 1
    if s in ("0", "false", "no", "n", "active", "activo", "retenido", ""): return 0
    return int(parse_number(v) > 0)

def ingest_customers(content=None, content_b64=None, filename=""):
    header, rows, info = read_table(content, content_b64, filename)
    mp = map_columns(header, CUSTOMER_FIELDS, ["tenure", "orders", "tickets", "idle"])
    out, invalid = [], 0
    for i, r in enumerate(rows):
        r = list(r) + [None] * (len(header) - len(r))
        try:
            out.append({"ext_id": str(r[mp["customer_id"]])[:60] if "customer_id" in mp and r[mp["customer_id"]] not in (None, "") else f"C-{i + 1:05d}",
                        "tenure": parse_number(r[mp["tenure"]]), "orders": parse_number(r[mp["orders"]]),
                        "tickets": parse_number(r[mp["tickets"]]), "idle": parse_number(r[mp["idle"]]),
                        "churned": _bool(r[mp["churned"]]) if "churned" in mp and r[mp["churned"]] not in (None, "") else None})
        except (ValueError, IndexError):
            invalid += 1
    labeled = [c for c in out if c["churned"] is not None]
    return out, {**info, "columns": {f: header[i] for f, i in mp.items()}, "rows": len(rows), "kept": len(out), "invalid": invalid,
                 "labeled": len(labeled), "churn_rate": round(sum(c["churned"] for c in labeled) / len(labeled) * 100, 1) if labeled else None,
                 "score": max(0, round(100 - invalid / max(1, len(rows)) * 100))}

SALES_TEMPLATE = "month,region,product,revenue,customers\n" + "\n".join(
    f"2025-{m:02d},{r},{p},{v},{v // 85}" for m in range(1, 13) for r, p, v in
    (("North", "Pro", 27000 + m * 400), ("North", "Basic", 8200 + m * 120), ("South", "Pro", 21000 + m * 350), ("South", "Basic", 7100 + m * 90)))
CUSTOMER_TEMPLATE = "customer_id,tenure_months,orders_per_month,support_tickets,days_since_last_order,churned\n" + "\n".join(
    f"C-{i:04d},{t},{o},{k},{d},{c}" for i, (t, o, k, d, c) in enumerate(
        [(24, 6, 0, 5, 0), (3, 1, 4, 70, 1), (12, 3, 1, 20, 0), (2, 0, 5, 85, 1), (36, 8, 0, 2, 0), (8, 2, 3, 45, 1)] * 10, 1))
