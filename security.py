"""Password hashing, JWT and role checks."""
import base64, hashlib, hmac, json, os, secrets, time
from contextvars import ContextVar
from fastapi import HTTPException, Header


SECRET_VALUE = os.getenv("AETHER_SECRET")

if not SECRET_VALUE or len(SECRET_VALUE) < 48:
    raise RuntimeError("AETHER_SECRET must be configured with at least 48 characters")

SECRET = SECRET_VALUE.encode()

TOKEN_TTL = 8 * 3600   # seconds; the client renews the token while the user is active
ORG: ContextVar[int] = ContextVar("org", default=0)   # organization of the current request
b64 = lambda b: base64.urlsafe_b64encode(b).rstrip(b"=").decode()
_sig = lambda msg: b64(hmac.new(SECRET, msg.encode(), hashlib.sha256).digest())

def hash_pw(pw, salt=None):
    salt = salt or secrets.token_hex(16)
    return salt + "$" + hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 200_000).hex()

def check_pw(pw, stored):
    return hmac.compare_digest(hash_pw(pw, stored.split("$")[0]), stored)

def make_token(sub, role, org, org_name):
    h = b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    p = b64(json.dumps({"sub": sub, "role": role, "org": org, "org_name": org_name, "exp": int(time.time()) + TOKEN_TTL}).encode())
    return f"{h}.{p}.{_sig(h + '.' + p)}"

async def auth(authorization: str = Header(None)):
    try:
        h, p, s = authorization.split(" ")[1].split(".")
        data = json.loads(base64.urlsafe_b64decode(p + "=="))
        if not hmac.compare_digest(s, _sig(f"{h}.{p}")) or data["exp"] < time.time(): raise ValueError
    except Exception:
        raise HTTPException(401, "Invalid or expired token")
    ORG.set(data["org"])
    return data

def need(u, *roles):
    if u["role"] not in roles: raise HTTPException(403, f"Role '{u['role']}' is not allowed to do this")