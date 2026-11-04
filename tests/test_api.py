import analytics as an


def test_health(client):
    r = client.get("/api/health").json()
    assert r["status"] == "ok" and r["database"] == "sqlite"


def test_security_headers(client):
    h = client.get("/api/health").headers
    assert h["x-content-type-options"] == "nosniff" and h["x-frame-options"] == "DENY"


def test_auth_required(client):
    assert client.get("/api/overview").status_code == 401


def test_overview_demo(client, admin):
    o = client.get("/api/overview", headers=admin).json()
    assert len(o["months"]) == 24 and len(o["forecast"]["values"]) == 3
    assert any(a["month"] == "2025-09" for a in o["anomalies"]), "the seeded September incident must be detected"
    assert o["insights"] and set(o["by_region"]) == {"Centro", "Norte", "Online", "Sur"}


def test_forecast_lab(client, admin):
    r = client.get("/api/forecast/lab?h=6", headers=admin).json()
    assert r["best"] in r["models"] and len(r["future"]) == 6
    assert all(len(m["forecast"]) == 6 for m in r["models"].values())


def test_analyst_explains_september(client, admin):
    r = client.post("/api/ask", headers=admin, json={"question": "Why did revenue decline in September?"}).json()
    assert "declined" in r["answer"] and "Online" in r["answer"] and r["calculations"]


def test_analyst_intents(client, admin):
    for q, word in [("Which region is growing fastest?", "region"), ("forecast next quarter", "project"), ("any anomalies?", "anomal")]:
        assert word in client.post("/api/ask", headers=admin, json={"question": q}).json()["answer"].lower()


def test_whatif_bridge_adds_up(client, admin):
    r = client.post("/api/whatif", headers=admin, json={"price": 5, "marketing": 20, "churn": -10}).json()
    assert abs(sum(b["value"] for b in r["bridge"]) - r["delta"]) <= 4


def test_rbac_viewer_cannot_upload(client, viewer):
    assert client.post("/api/upload", headers=viewer, json={"content": "month,region,product,revenue\n"}).status_code == 403


def test_alert_lifecycle(client, admin):
    assert client.post("/api/alerts", headers=admin, json={"name": "Drop", "metric": "mom_pct", "op": "<", "threshold": -5}).status_code == 200
    a = client.get("/api/alerts", headers=admin).json()[-1]
    assert a["name"] == "Drop" and a["value"] is not None
    assert client.delete(f"/api/alerts/{a['id']}", headers=admin).status_code == 200


def test_register_and_upload_csv(client):
    r = client.post("/api/auth/register", json={"org_name": "Acme", "username": "acme_admin", "email": "a@acme.io", "password": "supersecret"})
    h = {"Authorization": "Bearer " + r.json()["token"]}
    assert client.get("/api/overview", headers=h).json()["months"] == []        # new orgs start empty (tenant isolation)
    csv = client.get("/api/sample-csv").text
    up = client.post("/api/upload", headers=h, json={"content": csv}).json()
    assert up["kept"] == 12 and up["score"] == 100
    assert client.post("/api/ask", headers=h, json={"question": "what happened in March?"}).status_code == 200


def test_login_throttle(client):
    codes = [client.post("/api/auth/login", json={"username": "ghost", "password": "nope"}).status_code for _ in range(6)]
    assert codes[-1] == 429


def test_backtest_prefers_structure_over_naive():
    y = [100 + 3 * i + 10 * ((i % 12) in (5, 6, 7)) for i in range(36)]
    scores, ranked, folds = an.backtest(y, 3)
    assert folds == 4 and scores["naive"]["mape"] > scores[ranked[0]]["mape"]


def test_churn_metrics():
    c = an.churn_model()
    assert 0.5 < c["auc"] <= 1 and sum(c["confusion"].values()) == c["test_size"]
