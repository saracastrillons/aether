"""Organizations, users, roles and invitations."""
import re, secrets
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select, func
from db import Session, Org, User, Invite, Alert, add_audit, list_audit
from security import auth, need, hash_pw, check_pw, make_token, RateLimiter, client_ip

router = APIRouter(prefix="/api")
ROLES = ("admin", "analyst", "viewer")
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
USERNAME = re.compile(r"^[a-z0-9_.-]{3,30}$")

class Reg(BaseModel): org_name: str; username: str; email: str; password: str
class Login(BaseModel): username: str; password: str
class Inv(BaseModel): email: str; role: str
class Acc(BaseModel): token: str; username: str; password: str
class Role(BaseModel): role: str
class Pw(BaseModel): current: str; new: str

DEMO = {"org": None}   # id of the shared public demo organization
DEMO_ALERTS = [("Revenue drop over 10%", "mom_pct", "<", -10), ("Customer base below 3,000", "customers", "<", 3000),
               ("Record month above $290K", "last_month", ">", 290000)]

def seed():
    """Create the demo organization (demo/demo, analyst/analyst, viewer/viewer) on first run."""
    with Session.begin() as s:
        if not s.scalar(select(func.count(Org.id))):
            o = Org(name="Nimbus Retail", data_mode="demo"); s.add(o); s.flush()
            for u, r in (("demo", "admin"), ("analyst", "analyst"), ("viewer", "viewer")):
                s.add(User(username=u, email=f"{u}@nimbus.demo", pw=hash_pw(u), role=r, org_id=o.id))
            s.flush()
        u = s.scalar(select(User).where(User.username == "demo"))
        DEMO["org"] = u.org_id if u else None
        if u:   # example alert rules, so visitors see the feature without being able to edit the shared demo
            have = set(s.scalars(select(Alert.name).where(Alert.org_id == u.org_id)))
            for name, metric, op, th in DEMO_ALERTS:
                if name not in have: s.add(Alert(org_id=u.org_id, name=name, metric=metric, op=op, threshold=th))

def guard_demo(user, what="This action"):
    """The public demo is shared by every visitor, so anything that would break it for others is blocked."""
    if user["org"] == DEMO["org"]:
        raise HTTPException(403, f"{what} is disabled in the public demo. Create your own workspace to do it.")

def _session(u, o):
    return {"token": make_token(u.username, u.role, o.id, o.name), "role": u.role, "org": o.name}

def _validate(username, email, password):
    if not USERNAME.match(username): raise HTTPException(422, "Username: 3-30 chars (lowercase letters, numbers, . _ -)")
    if not EMAIL.match(email): raise HTTPException(422, "Invalid email")
    if len(password) < 8: raise HTTPException(422, "Password must have at least 8 characters")

# Throttles are keyed by IP, so one visitor can never lock other people out (e.g. of the shared demo).
LOGIN_FAILS = RateLimiter(5, 300)        # wrong passwords per (IP, username) in 5 minutes
IP_FAILS = RateLimiter(30, 900)          # wrong passwords per IP across all usernames (password spraying)
SIGNUPS = RateLimiter(10, 3600)          # new accounts (registrations + accepted invites) per IP per hour
SLOW_DOWN = "Too many failed attempts. Try again in a few minutes."

@router.post("/auth/register")
def register(b: Reg, request: Request):
    SIGNUPS.check(client_ip(request), "Too many accounts created from this network. Try again later.")
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

@router.post("/auth/login")
def login(b: Login, request: Request):
    name, ip = b.username.strip().lower(), client_ip(request)
    if LOGIN_FAILS.blocked((ip, name)) or IP_FAILS.blocked(ip): raise HTTPException(429, SLOW_DOWN)
    with Session() as s:
        u = s.scalar(select(User).where(User.username == name))
        if not u or not check_pw(b.password, u.pw):
            LOGIN_FAILS.hit((ip, name)); IP_FAILS.hit(ip)
            raise HTTPException(401, "Invalid credentials")
        LOGIN_FAILS.reset((ip, name))
        out = _session(u, s.get(Org, u.org_id)); oid = u.org_id
    add_audit(oid, b.username, "login")
    return out

# ---------- invitations ----------
@router.post("/invites")
def invite(b: Inv, user=Depends(auth)):
    need(user, "admin"); guard_demo(user, "Inviting people")
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
def accept(b: Acc, request: Request):
    SIGNUPS.check(client_ip(request), "Too many accounts created from this network. Try again later.")
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
    need(user, "admin"); guard_demo(user, "Changing roles")
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
    need(user, "admin"); guard_demo(user, "Removing members")
    if name == user["sub"]: raise HTTPException(409, "You cannot remove yourself")
    with Session.begin() as s: s.delete(_member(s, user, name))
    add_audit(user["org"], user["sub"], f"removed {name}")
    return {"ok": True}
# ---------- account ----------
@router.post("/auth/refresh")
def refresh(user=Depends(auth)):
    """Issue a fresh token for an active session (role and org are re-read, so changes apply immediately)."""
    with Session() as s:
        u = s.scalar(select(User).where(User.username == user["sub"], User.org_id == user["org"]))
        if not u: raise HTTPException(401, "Account no longer exists")
        return _session(u, s.get(Org, u.org_id))

@router.get("/account")
def account(user=Depends(auth)):
    with Session() as s:
        u = s.scalar(select(User).where(User.username == user["sub"], User.org_id == user["org"]))
        if not u: raise HTTPException(404, "Account not found")
        return {"username": u.username, "email": u.email, "role": u.role, "org": s.get(Org, u.org_id).name}

@router.post("/account/password")
def change_password(b: Pw, user=Depends(auth)):
    guard_demo(user, "Changing the password")
    if len(b.new) < 8: raise HTTPException(422, "Password must have at least 8 characters")
    with Session.begin() as s:
        u = s.scalar(select(User).where(User.username == user["sub"], User.org_id == user["org"]))
        if not u or not check_pw(b.current, u.pw): raise HTTPException(403, "Current password is incorrect")
        u.pw = hash_pw(b.new)
    add_audit(user["org"], user["sub"], "changed their password")
    return {"ok": True}
