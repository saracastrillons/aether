"""Real-user flows: messy imports, churn on own customers, the AI agent loop, account and demo protection."""
import base64, io, json
from types import SimpleNamespace as NS
import pytest
import assistant, ingest


def _org(client, name):
    r = client.post("/api/auth/register", json={"org_name": name, "username": name.lower(), "email": f"a@{name.lower()}.io", "password": "supersecret"})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["token"]}


# ---------- ingestion ----------

SPANISH = "Fecha;Ciudad;Producto;Total Ventas\n" + "\n".join(
    f"15/{m:02d}/2025;Medellín;Café;{1000 + m}.250,50" for m in range(1, 9)) + "\n15/03/2025;Medellín;Café;1.003.250,50\n15/03/2025;Medellín;Café;1.003.250,50\nfoo;bar;baz;qux"

def test_spanish_semicolon_csv():
    rows, rep = ingest.ingest_sales(SPANISH)
    assert rep["delimiter"] == ";" and rep["columns"]["month"] == "Fecha" and rep["columns"]["revenue"] == "Total Ventas"
    assert rep["months"] == 8 and rep["duplicates"] == 1 and rep["invalid"] == 1
    jan = next(r for r in rows if r["month"] == "2025-01")
    assert jan["revenue"] in (1_001_250, 1_001_251) and jan["region"] == "Medellín"

@pytest.mark.parametrize("raw,expected", [("2025-03", "2025-03"), ("2025/3/14", "2025-03"), ("202503", "2025-03"), ("03/2025", "2025-03"),
                                          ("Mar 2025", "2025-03"), ("marzo de 2025", "2025-03"), ("ene-25", "2025-01")])
def test_month_formats(raw, expected):
    assert ingest.parse_month(raw) == expected

@pytest.mark.parametrize("raw,expected", [("$1,234.50", 1234.5), ("1.234,50", 1234.5), ("1.234", 1234), ("12,5", 12.5), ("(300)", -300), ("COP 2.500.000", 2500000)])
def test_number_formats(raw, expected):
    assert ingest.parse_number(raw) == expected

def test_excel_and_daily_rows_are_aggregated():
    from openpyxl import Workbook
    from datetime import date
    wb = Workbook(); ws = wb.active; ws.append(["Monthly sales report"]); ws.append(["date", "store", "sales"])
    for m in range(1, 8):
        for d in (3, 17): ws.append([date(2025, m, d), "Centro", 100])
    buf = io.BytesIO(); wb.save(buf)
    rows, rep = ingest.ingest_sales(content_b64=base64.b64encode(buf.getvalue()).decode(), filename="ventas.xlsx")
    assert rep["format"] == "Excel" and rep["months"] == 7 and rows[0]["revenue"] == 200 and rows[0]["product"] == "All"

def test_missing_columns_message():
    with pytest.raises(ingest.IngestError, match="month"):
        ingest.ingest_sales("foo,bar\n1,2\n")


# ---------- API: import, churn, account ----------

def test_dry_run_then_import(client):
    h = _org(client, "Tienda")
    pre = client.post("/api/upload", headers=h, json={"content": SPANISH, "filename": "ventas.csv", "dry_run": True}).json()
    assert pre["preview"] and client.get("/api/overview", headers=h).json()["months"] == []      # dry run saved nothing
    assert client.post("/api/upload", headers=h, json={"content": SPANISH, "filename": "ventas.csv"}).status_code == 200
    assert len(client.get("/api/overview", headers=h).json()["months"]) == 8

def test_churn_on_own_customers(client):
    h = _org(client, "Gym")
    assert client.get("/api/churn", headers=h).json()["available"] is False
    r = client.post("/api/upload/customers", headers=h, json={"content": ingest.CUSTOMER_TEMPLATE, "filename": "c.csv"})
    assert r.status_code == 200 and r.json()["labeled"] == 60
    c = client.get("/api/churn", headers=h).json()
    assert c["available"] and c["source"] == "your customers" and c["auc"] > 0.9

def test_refresh_and_password_change(client):
    h = _org(client, "Bakery")
    assert client.post("/api/auth/refresh", headers=h).status_code == 200
    assert client.post("/api/account/password", headers=h, json={"current": "wrong-pass", "new": "newpassword1"}).status_code == 403
    assert client.post("/api/account/password", headers=h, json={"current": "supersecret", "new": "newpassword1"}).status_code == 200
    assert client.post("/api/auth/login", json={"username": "bakery", "password": "newpassword1"}).status_code == 200

def test_public_demo_is_protected(client, admin):
    assert client.post("/api/account/password", headers=admin, json={"current": "demo", "new": "hijacked123"}).status_code == 403
    assert client.delete("/api/members/viewer", headers=admin).status_code == 403
    assert client.post("/api/upload", headers=admin, json={"content": ingest.SALES_TEMPLATE}).status_code == 403
    assert client.post("/api/upload", headers=admin, json={"content": ingest.SALES_TEMPLATE, "dry_run": True}).status_code == 200


# ---------- AI agent loop (Claude simulated) ----------

class FakeClaude:
    """Mimics client.beta.messages.create: first asks for two tools, then answers from their results."""
    def __init__(self): self.calls = []; self.beta = NS(messages=NS(create=self.create))
    def create(self, **kw):
        self.calls.append({**kw, "messages": list(kw["messages"])})   # snapshot: the agent keeps appending to the list
        if len(self.calls) == 1:
            return NS(stop_reason="tool_use", model="claude-opus-5-5", content=[
                NS(type="text", text="Let me check."),
                NS(type="tool_use", id="t1", name="explain_change", input={"month": "2025-09"}),
                NS(type="tool_use", id="t2", name="query_revenue", input={"group_by": "region", "start_month": "2025-01", "end_month": "2025-12"})])
        results = {b["tool_use_id"]: b for b in kw["messages"][-1]["content"]}
        change = json.loads(results["t1"]["content"])
        return NS(stop_reason="end_turn", model="claude-opus-5-5",
                  content=[NS(type="text", text=f"Los ingresos cayeron **{change['change_pct']}%** en septiembre.")])

def test_agent_runs_tools_and_grounds_answer(client, admin):
    from main import context
    ctx = context({"org": 1, "sub": "demo", "org_name": "Nimbus Retail"})
    fake = FakeClaude()
    r = assistant.answer("¿Por qué cayeron las ventas en septiembre?", ctx,
                         history=[{"role": "user", "content": "hola"}, {"role": "assistant", "content": "¡Hola!"}], extras={}, client=fake)
    assert r["engine"] == "claude-opus-5-5" and "-23.99" in r["answer"]
    assert any("explain_change" in t for t in r["calculations"]) and any("GROUP BY" in t for t in r["calculations"])
    first = fake.calls[0]
    assert first["model"] == "claude-opus-5-5" and [m["role"] for m in first["messages"]] == ["user", "assistant", "user"]
    assert {t["name"] for t in first["tools"]} >= {"query_revenue", "explain_change", "get_forecast"}
    assert r["chart"]["type"] == "bar"

def test_agent_falls_back_to_engine_on_api_error(client, admin):
    from main import context
    ctx = context({"org": 1, "sub": "demo", "org_name": "Nimbus Retail"})
    broken = NS(beta=NS(messages=NS(create=lambda **kw: (_ for _ in ()).throw(RuntimeError("network down")))))
    r = assistant.answer("Why did revenue decline in September?", ctx, client=broken)
    assert r["engine"] == "aether-engine" and "declined" in r["answer"]

def test_tool_errors_are_reported_not_raised(client, admin):
    from main import context
    ctx = context({"org": 1, "sub": "demo", "org_name": "Nimbus Retail"})
    with pytest.raises(ValueError, match="not in data"):
        assistant.run_tool("explain_change", {"month": "1999-01"}, ctx, {})

def test_engine_new_intents(client, admin):
    for q, word in [("Compare 2024 vs 2025", "2025 vs 2024"), ("What was our best month?", "best month"), ("How is Online doing?", "online"),
                    ("¿Cuántos clientes tenemos?", "customers")]:
        a = client.post("/api/ask", headers=admin, json={"question": q}).json()["answer"]
        assert word.lower() in a.lower(), (q, a)
