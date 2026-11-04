"""Organizations, users, roles and invitations."""
import re, secrets, time
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from db import Session, Org, User, Invite, add_audit, list_audit
from security import auth, need, hash_pw, check_pw, make_token

router = APIRouter(prefix="/api")
ROLES = ("admin", "analyst", "viewer")
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
USERNAME = re.compile(r"^[a-z0-9_.-]{3,30}$")

class Reg(BaseModel): org_name: str; username: str; email: str; password: str
class Login(BaseModel): username: str; password: str
class Inv(BaseModel): email: str; role: str
class Acc(BaseModel): token: str; username: str; password: str
class Role(BaseModel): role: str

def seed():
    """Create the demo organization (demo/demo, analyst/analyst, viewer/viewer) on first run."""
    with Session.begin() as s:
        if s.scalar(select(func.count(Org.id))): return
        o = Org(name="Nimbus Retail", data_mode="demo"); s.add(o); s.flush()
        for u, r in (("demo", "admin"), ("analyst", "analyst"), ("viewer", "viewer")):
            s.add(User(username=u, email=f"{u}@nimbus.demo", pw=hash_pw(u), role=r, org_id=o.id))

def _session(u, o):
    return {"token": make_token(u.username, u.role, o.id, o.name), "role": u.role, "org": o.name}

def _validate(username, email, password):
    if not USERNAME.match(username): raise HTTPException(422, "Username: 3-30 chars (lowercase letters, numbers, . _ -)")
    if not EMAIL.match(email): raise HTTPException(422, "Invalid email")
    if len(password) < 8: raise HTTPException(422, "Password must have at least 8 characters")

@router.post("/auth/register")
def register(b: Reg):
    name = b.username.strip().lower(); _validate(name, b.email, b.password)
    if len(b.org_name.strip()) < 2: raise HTTPException(422, "Organization name is required")
    with Session.begin() as s:
        if s.scalar(select(User).where(User.username == name)): raise HTTPException(409, "Username already taken")
        
        o = Org(name=b.org_name.strip(), data_mode="empty")
        s.add(o)
        s.flush()

        u = User(username=name, email=b.email, pw=hash_pw(b.password), role="admin", org_id=o.id)

        s.add(u); s.flush(); out = _session(u, o); oid = o.id
    add_audit(oid, name, "created the organization")
    return out

_FAILS = {}   # username -> recent failed login timestamps (simple brute-force throttle)

@router.post("/auth/login")
def login(b: Login):
    name, now = b.username.strip().lower(), time.time()
    recent = [t for t in _FAILS.get(name, []) if now - t < 300]
    if len(recent) >= 5: raise HTTPException(429, "Too many failed attempts. Try again in a few minutes.")
    with Session() as s:
        u = s.scalar(select(User).where(User.username == name))
        if not u or not check_pw(b.password, u.pw):
            _FAILS[name] = recent + [now]
            raise HTTPException(401, "Invalid credentials")
        _FAILS.pop(name, None)
        out = _session(u, s.get(Org, u.org_id)); oid = u.org_id
    add_audit(oid, b.username, "login")
    return out

# ---------- invitations ----------
@router.post("/invites")
def invite(b: Inv, user=Depends(auth)):
    need(user, "admin")
    if b.role not in ROLES or not EMAIL.match(b.email): raise HTTPException(422, "A valid email and role are required")
    tok = secrets.token_urlsafe(24)
    with Session.begin() as s:
        s.add(Invite(token=tok, email=b.email, role=b.role, org_id=user["org"], expires=datetime.utcnow() + timedelta(days=7)))
    add_audit(user["org"], user["sub"], f"invited {b.email} as {b.role}")
    return {"token": tok, "link": f"/?invite={tok}"}

@router.get("/invites")
def invites(user=Depends(auth)):
    need(user, "admin")
    with Session() as s:
        q = select(Invite).where(Invite.org_id == user["org"], Invite.accepted.is_(False), Invite.expires > datetime.utcnow())
        return [{"id": i.id, "email": i.email, "role": i.role, "token": i.token, "expires": i.expires.strftime("%Y-%m-%d")} for i in s.scalars(q)]

@router.delete("/invites/{iid}")
def revoke(iid: int, user=Depends(auth)):
    need(user, "admin")
    with Session.begin() as s:
        i = s.get(Invite, iid)
        if not i or i.org_id != user["org"]: raise HTTPException(404, "Invite not found")
        s.delete(i)
    add_audit(user["org"], user["sub"], "revoked an invite")
    return {"ok": True}

def _open_invite(s, token):
    i = s.scalar(select(Invite).where(Invite.token == token))
    if not i or i.accepted or i.expires < datetime.utcnow(): raise HTTPException(410, "Invite is invalid or expired")
    return i

@router.get("/invites/{token}")
def invite_info(token: str):
    with Session() as s:
        i = _open_invite(s, token)
        return {"org": s.get(Org, i.org_id).name, "role": i.role, "email": i.email}

@router.post("/invites/accept")
def accept(b: Acc):
    name = b.username.strip().lower()
    with Session.begin() as s:
        i = _open_invite(s, b.token); _validate(name, i.email, b.password)
        if s.scalar(select(User).where(User.username == name)): raise HTTPException(409, "Username already taken")
        o = s.get(Org, i.org_id)
        u = User(username=name, email=i.email, pw=hash_pw(b.password), role=i.role, org_id=o.id)
        s.add(u); i.accepted = True; s.flush(); out = _session(u, o); oid = o.id
    add_audit(oid, name, f"joined as {out['role']} via invite")
    return out

# ---------- members ----------
@router.get("/team")
def team(user=Depends(auth)):
    need(user, "admin")
    with Session() as s:
        q = select(User).where(User.org_id == user["org"]).order_by(User.id)
        members = [{"username": u.username, "email": u.email, "role": u.role} for u in s.scalars(q)]
    return {"members": members, "audit": list_audit(user["org"], 30)}

def _member(s, user, name):
    u = s.scalar(select(User).where(User.username == name, User.org_id == user["org"]))
    if not u: raise HTTPException(404, "Member not found")
    return u

@router.patch("/members/{name}")
def set_role(name: str, b: Role, user=Depends(auth)):
    need(user, "admin")
    if b.role not in ROLES: raise HTTPException(422, "Invalid role")
    with Session.begin() as s:
        u = _member(s, user, name)
        admins = s.scalar(select(func.count(User.id)).where(User.org_id == user["org"], User.role == "admin"))
        if u.role == "admin" and b.role != "admin" and admins < 2:
            raise HTTPException(409, "An organization needs at least one admin")
        u.role = b.role
    add_audit(user["org"], user["sub"], f"changed {name} to {b.role}")
    return {"ok": True}

@router.delete("/members/{name}")
def remove(name: str, user=Depends(auth)):
    need(user, "admin")
    if name == user["sub"]: raise HTTPException(409, "You cannot remove yourself")
    with Session.begin() as s: s.delete(_member(s, user, name))
    add_audit(user["org"], user["sub"], f"removed {name}")
    return {"ok": True}