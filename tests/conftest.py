import os, sys, tempfile, pathlib

# Isolated database and secret for the test run (set before the app is imported).
_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ.setdefault("AETHER_SECRET", "test-secret-" + "x" * 48)
os.environ.pop("ANTHROPIC_API_KEY", None); os.environ.pop("AETHER_LLM", None)
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); os.chdir(ROOT)

import pytest
from fastapi.testclient import TestClient
from main import app

@pytest.fixture(scope="session")
def client(): return TestClient(app)

def _login(client, u, p):
    r = client.post("/api/auth/login", json={"username": u, "password": p}); assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["token"]}

@pytest.fixture(scope="session")
def admin(client): return _login(client, "demo", "demo")

@pytest.fixture(scope="session")
def viewer(client): return _login(client, "viewer", "viewer")
