"""Persistence layer (SQLAlchemy). SQLite by default; PostgreSQL via DATABASE_URL."""
import os, time
from datetime import datetime
from sqlalchemy import create_engine, Integer, String, Boolean, DateTime, ForeignKey, select, delete
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

URL = os.getenv("DATABASE_URL", "sqlite:///aether.db")
engine = create_engine(URL, pool_pre_ping=True)
Session = sessionmaker(engine)

class Base(DeclarativeBase): pass


class Org(Base):
    __tablename__ = "orgs"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    data_mode: Mapped[str] = mapped_column(String(10), default="empty")


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(160))
    pw: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(20))
    org_id: Mapped[int] = mapped_column(ForeignKey("orgs.id"), index=True)

class Invite(Base):
    __tablename__ = "invites"
    id: Mapped[int] = mapped_column(primary_key=True)
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(160))
    role: Mapped[str] = mapped_column(String(20))
    org_id: Mapped[int] = mapped_column(ForeignKey("orgs.id"), index=True)
    expires: Mapped[datetime] = mapped_column(DateTime)
    accepted: Mapped[bool] = mapped_column(Boolean, default=False)

class Sale(Base):
    __tablename__ = "sales"
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(Integer, index=True)
    month: Mapped[str] = mapped_column(String(7), index=True)
    region: Mapped[str] = mapped_column(String(80))
    product: Mapped[str] = mapped_column(String(80))
    revenue: Mapped[int] = mapped_column(Integer)
    customers: Mapped[int] = mapped_column(Integer)

class Audit(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(Integer, index=True)
    ts: Mapped[str] = mapped_column(String(32))
    user: Mapped[str] = mapped_column(String(80))
    action: Mapped[str] = mapped_column(String(255))


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("orgs.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    metric: Mapped[str] = mapped_column(String(40))
    op: Mapped[str] = mapped_column(String(5))
    threshold: Mapped[float] = mapped_column()
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


def init_db(): Base.metadata.create_all(engine)

def load_sales(org):
    with Session() as s:
        q = select(Sale).where(Sale.org_id == org).order_by(Sale.id)
        return [dict(month=r.month, region=r.region, product=r.product, revenue=r.revenue, customers=r.customers)
                for r in s.scalars(q)]

def replace_sales(org, rows):
    with Session.begin() as s:
        s.execute(delete(Sale).where(Sale.org_id == org))
        s.add_all(Sale(org_id=org, **r) for r in rows)

def add_audit(org, user, action):
    with Session.begin() as s:
        s.add(Audit(org_id=org, ts=time.strftime("%Y-%m-%d %H:%M:%S"), user=user, action=action))

def list_audit(org, n=30):
    with Session() as s:
        q = select(Audit).where(Audit.org_id == org).order_by(Audit.id.desc()).limit(n)
        return [{"t": a.ts, "user": a.user, "action": a.action} for a in s.scalars(q)]


def load_alerts(org):
    with Session() as s:
        q = select(Alert).where(Alert.org_id == org, Alert.enabled == True).order_by(Alert.id)
        return [
            {
                "id": a.id,
                "name": a.name,
                "metric": a.metric,
                "op": a.op,
                "threshold": a.threshold
            }
            for a in s.scalars(q)
        ]


def save_alert(org, name, metric, op, threshold):
    with Session.begin() as s:
        s.add(Alert(
            org_id=org,
            name=name,
            metric=metric,
            op=op,
            threshold=threshold
        ))


def get_data_mode(org_id):
    with Session() as session:
        org = session.get(Org, org_id)

        if org is None:
            raise ValueError("Organization not found")

        return org.data_mode


def set_data_mode(org_id, mode):
    if mode not in ("empty", "demo", "real"):
        raise ValueError("Invalid data mode")

    with Session.begin() as session:
        org = session.get(Org, org_id)

        if org is None:
            raise ValueError("Organization not found")

        org.data_mode = mode


def delete_alert(org, aid):
    with Session.begin() as s:
        a = s.get(Alert, aid)
        if not a or a.org_id != org: return False
        s.delete(a)
        return True


class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(Integer, index=True)
    ext_id: Mapped[str] = mapped_column(String(60))
    tenure: Mapped[float] = mapped_column()
    orders: Mapped[float] = mapped_column()
    tickets: Mapped[float] = mapped_column()
    idle: Mapped[float] = mapped_column()
    churned: Mapped[int | None] = mapped_column(Integer, nullable=True)


def load_customers(org):
    with Session() as s:
        q = select(Customer).where(Customer.org_id == org).order_by(Customer.id)
        return [dict(ext_id=c.ext_id, tenure=c.tenure, orders=c.orders, tickets=c.tickets, idle=c.idle, churned=c.churned) for c in s.scalars(q)]


def replace_customers(org, rows):
    with Session.begin() as s:
        s.execute(delete(Customer).where(Customer.org_id == org))
        s.add_all(Customer(org_id=org, **r) for r in rows)
