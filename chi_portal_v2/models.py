"""
CHI Insurance Portal v2 — Database Models
Flask + SQLAlchemy | Railway PostgreSQL
"""
import os, enum
from datetime import datetime
from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Date, DateTime,
    Boolean, Text, ForeignKey, Enum as SQLEnum, LargeBinary
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

Base = declarative_base()

# ── ENUMS ──────────────────────────────────────────────────────────────────────

class UserRole(enum.Enum):
    AGENT      = "agent"
    CLIENT     = "client"
    BACKOFFICE = "backoffice"

class PolicySector(enum.Enum):
    MOTOR    = "Αυτοκίνητο"
    LIFE     = "Ζωή"
    HEALTH   = "Υγεία"
    PROPERTY = "Περιουσία"
    TRAVEL   = "Ταξίδι"
    PET      = "Κατοικίδια"
    BUSINESS = "Επιχείρηση"
    OTHER    = "Άλλο"

class PolicyStatus(enum.Enum):
    ACTIVE    = "ACTIVE"
    EXPIRED   = "EXPIRED"
    CANCELLED = "CANCELLED"
    PENDING   = "PENDING"

class PaymentStatus(enum.Enum):
    PAID    = "PAID"
    PENDING = "PENDING"
    OVERDUE = "OVERDUE"

class PaymentFrequency(enum.Enum):
    ANNUAL     = "Ετήσια"
    SEMI       = "Εξαμηνιαία"
    QUARTERLY  = "Τριμηνιαία"
    MONTHLY    = "Μηνιαία"

class ClaimStatus(enum.Enum):
    OPEN       = "Ανοιχτή"
    IN_PROCESS = "Σε Εξέλιξη"
    SETTLED    = "Διακανονισμός"
    CLOSED     = "Κλειστή"
    REJECTED   = "Απορριφθείσα"

class TicketStatus(enum.Enum):
    OPEN       = "Ανοιχτό"
    IN_PROCESS = "Σε Εξέλιξη"
    RESOLVED   = "Επιλύθηκε"
    CLOSED     = "Κλειστό"

class TicketPriority(enum.Enum):
    LOW    = "Χαμηλή"
    MEDIUM = "Μεσαία"
    HIGH   = "Υψηλή"
    URGENT = "Επείγον"

class EmailStatus(enum.Enum):
    QUEUED = "QUEUED"
    SENT   = "SENT"
    FAILED = "FAILED"

# ── MODELS ─────────────────────────────────────────────────────────────────────

class User(Base):
    """Portal user (agent, backoffice staff, or client login)."""
    __tablename__ = "users"
    id           = Column(Integer, primary_key=True)
    email        = Column(String(200), unique=True, nullable=False)
    password_hash= Column(String(300), nullable=False)
    role         = Column(SQLEnum(UserRole), nullable=False, default=UserRole.CLIENT)
    name         = Column(String(200))
    active       = Column(Boolean, default=True)
    agent_code   = Column(String(20), nullable=True)   # links to Agent.code; None = admin
    client_id    = Column(Integer, ForeignKey("clients.id"), nullable=True)
    created_date = Column(DateTime, default=datetime.now)
    last_login   = Column(DateTime)
    client       = relationship("Client", back_populates="user", uselist=False)



class Agent(Base):
    """Insurance agent / broker profile."""
    __tablename__ = "agents"
    id             = Column(Integer, primary_key=True)
    code           = Column(String(20), unique=True, nullable=False)  # ca, 3p, bu, chi
    name           = Column(String(200), nullable=False)
    email          = Column(String(200))
    phone          = Column(String(50))
    mobile         = Column(String(50))
    address        = Column(String(300))
    company_name   = Column(String(200))
    tax_id         = Column(String(50))
    commission_rate= Column(Float, default=0.0)  # default % commission
    active         = Column(Boolean, default=True)
    is_admin       = Column(Boolean, default=False)  # admin = sees all
    notes          = Column(Text)
    created_date   = Column(DateTime, default=datetime.now)

class Client(Base):
    """Insurance client (insured person/company)."""
    __tablename__ = "clients"
    id            = Column(Integer, primary_key=True)
    name          = Column(String(200), nullable=False)
    email         = Column(String(200))
    phone         = Column(String(50))
    mobile        = Column(String(50))
    address       = Column(String(300))
    postal_code   = Column(String(20))
    city          = Column(String(100))
    tax_id        = Column(String(50))          # ΑΦΜ
    id_number     = Column(String(50))          # ΑΔΤ
    date_of_birth = Column(Date)
    profession    = Column(String(100))
    company_name  = Column(String(200))         # if corporate
    notes         = Column(Text)
    vip           = Column(Boolean, default=False)
    portal_access = Column(Boolean, default=False)
    created_date  = Column(DateTime, default=datetime.now)
    updated_date  = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # Relationships
    user      = relationship("User", back_populates="client", uselist=False)
    policies  = relationship("Policy",  back_populates="client", cascade="all, delete-orphan")
    tickets   = relationship("Ticket",  back_populates="client", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="client", cascade="all, delete-orphan")


class Policy(Base):
    """Insurance policy."""
    __tablename__ = "policies"
    id               = Column(Integer, primary_key=True)
    client_id        = Column(Integer, ForeignKey("clients.id"), nullable=False)
    policy_number    = Column(String(100))
    sector           = Column(SQLEnum(PolicySector), default=PolicySector.OTHER)
    policy_type      = Column(String(150))      # e.g. "Κλοπή + Πυρκαγιά"
    provider         = Column(String(100))      # Insurance company
    license_plate    = Column(String(20))       # For motor
    vehicle_make     = Column(String(100))      # For motor
    vehicle_model    = Column(String(100))
    insured_value    = Column(Float)            # Insured amount
    premium          = Column(Float)            # Annual premium
    commission_rate  = Column(Float)            # % commission
    commission_amount= Column(Float)            # Calculated commission
    payment_frequency= Column(SQLEnum(PaymentFrequency), default=PaymentFrequency.ANNUAL)
    payment_code     = Column(String(100))      # RF code for bank transfers
    start_date       = Column(Date)
    expiration_date  = Column(Date)
    status           = Column(SQLEnum(PolicyStatus), default=PolicyStatus.ACTIVE)
    agent            = Column(String(20), default="chi")  # agent code
    beneficiary      = Column(String(200))
    coverage_details = Column(Text)             # JSON or text summary
    hal_summary      = Column(Text)             # Cached HAL explanation
    created_date     = Column(DateTime, default=datetime.now)
    updated_date     = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # Relationships
    client    = relationship("Client",  back_populates="policies")
    payments  = relationship("Payment", back_populates="policy",  cascade="all, delete-orphan")
    claims    = relationship("Claim",   back_populates="policy",  cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="policy")
    tickets   = relationship("Ticket",  back_populates="policy")
    email_queue = relationship("EmailQueue", back_populates="policy", cascade="all, delete-orphan")
    lixiario  = relationship("LixiariaEntry", back_populates="policy", cascade="all, delete-orphan")


class Payment(Base):
    """Payment record for a policy."""
    __tablename__ = "payments"
    id           = Column(Integer, primary_key=True)
    policy_id    = Column(Integer, ForeignKey("policies.id"), nullable=False)
    amount       = Column(Float, nullable=False)
    due_date     = Column(Date, nullable=False)
    payment_date = Column(Date)
    status       = Column(SQLEnum(PaymentStatus), default=PaymentStatus.PENDING)
    method       = Column(String(50))           # cash, bank, card
    receipt_num  = Column(String(100))
    notes        = Column(String(500))
    created_date = Column(DateTime, default=datetime.now)

    policy       = relationship("Policy", back_populates="payments")
    email_queue  = relationship("EmailQueue", back_populates="payment", cascade="all, delete-orphan")


class Claim(Base):
    """Insurance claim."""
    __tablename__ = "claims"
    id            = Column(Integer, primary_key=True)
    policy_id     = Column(Integer, ForeignKey("policies.id"), nullable=False)
    claim_number  = Column(String(100))
    description   = Column(Text, nullable=False)
    claim_amount  = Column(Float)
    settled_amount= Column(Float)
    status        = Column(SQLEnum(ClaimStatus), default=ClaimStatus.OPEN)
    incident_date = Column(Date)
    reported_date = Column(Date, default=datetime.now)
    resolved_date = Column(Date)
    notes         = Column(Text)
    created_date  = Column(DateTime, default=datetime.now)
    updated_date  = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    policy        = relationship("Policy", back_populates="claims")


class Ticket(Base):
    """Support ticket / inquiry."""
    __tablename__ = "tickets"
    id            = Column(Integer, primary_key=True)
    client_id     = Column(Integer, ForeignKey("clients.id"), nullable=False)
    policy_id     = Column(Integer, ForeignKey("policies.id"), nullable=True)
    subject       = Column(String(300), nullable=False)
    description   = Column(Text)
    status        = Column(SQLEnum(TicketStatus), default=TicketStatus.OPEN)
    priority      = Column(SQLEnum(TicketPriority), default=TicketPriority.MEDIUM)
    created_by    = Column(String(100))         # "agent" | "client" | email
    assigned_to   = Column(String(100))
    resolution    = Column(Text)
    created_date  = Column(DateTime, default=datetime.now)
    updated_date  = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    resolved_date = Column(DateTime)

    client        = relationship("Client", back_populates="tickets")
    policy        = relationship("Policy", back_populates="tickets")


class Provider(Base):
    """Insurance provider/company."""
    __tablename__ = "providers"
    id              = Column(Integer, primary_key=True)
    name            = Column(String(200), nullable=False)
    short_name      = Column(String(50))
    sector          = Column(String(200))        # comma-separated sectors
    contact_person  = Column(String(200))
    email           = Column(String(200))
    phone           = Column(String(50))
    website         = Column(String(200))
    default_commission = Column(Float)           # % default commission
    active          = Column(Boolean, default=True)
    notes           = Column(Text)
    created_date    = Column(DateTime, default=datetime.now)

    commissions     = relationship("CommissionStatement", back_populates="provider", cascade="all, delete-orphan")
    lixiaria        = relationship("LixiariaEntry", back_populates="provider")


class CommissionStatement(Base):
    """Monthly commission statement from a provider."""
    __tablename__ = "commission_statements"
    id               = Column(Integer, primary_key=True)
    provider_id      = Column(Integer, ForeignKey("providers.id"), nullable=False)
    period_month     = Column(Integer, nullable=False)   # 1-12
    period_year      = Column(Integer, nullable=False)
    total_premium    = Column(Float)
    commission_rate  = Column(Float)
    commission_amount= Column(Float)
    paid             = Column(Boolean, default=False)
    paid_date        = Column(Date)
    notes            = Column(Text)
    ai_insights      = Column(Text)              # Cached HAL analysis
    uploaded_date    = Column(DateTime, default=datetime.now)

    provider         = relationship("Provider", back_populates="commissions")


class LixiariaEntry(Base):
    """Expiry list entry (ληξιάριο) — policies expiring by month."""
    __tablename__ = "lixiaria"
    id                  = Column(Integer, primary_key=True)
    policy_id           = Column(Integer, ForeignKey("policies.id"), nullable=False)
    provider_id         = Column(Integer, ForeignKey("providers.id"), nullable=True)
    expiry_month        = Column(Integer, nullable=False)  # 1-12
    expiry_year         = Column(Integer, nullable=False)
    renewal_sent        = Column(Boolean, default=False)
    renewal_sent_date   = Column(DateTime)
    hal_email_draft     = Column(Text)           # HAL-generated renewal email
    renewal_confirmed   = Column(Boolean, default=False)
    notes               = Column(Text)
    created_date        = Column(DateTime, default=datetime.now)

    policy              = relationship("Policy", back_populates="lixiario")
    provider            = relationship("Provider", back_populates="lixiaria")


class Document(Base):
    """Uploaded document (policy PDFs, ID cards, etc.)."""
    __tablename__ = "documents"
    id                = Column(Integer, primary_key=True)
    client_id         = Column(Integer, ForeignKey("clients.id"), nullable=True)
    policy_id         = Column(Integer, ForeignKey("policies.id"), nullable=True)
    filename          = Column(String(300), nullable=False)
    original_filename = Column(String(300))
    file_type         = Column(String(50))        # pdf, jpg, png, docx
    file_data         = Column(LargeBinary)        # stored in DB (Railway-safe)
    file_size         = Column(Integer)
    ai_summary        = Column(Text)              # HAL document analysis
    uploaded_by       = Column(String(100))       # "agent" | "client" | email
    uploaded_date     = Column(DateTime, default=datetime.now)
    is_policy_doc     = Column(Boolean, default=False)

    client            = relationship("Client", back_populates="documents")
    policy            = relationship("Policy", back_populates="documents")


class EmailQueue(Base):
    """Renewal email queue."""
    __tablename__ = "email_queue"
    id              = Column(Integer, primary_key=True)
    client_id       = Column(Integer, ForeignKey("clients.id"), nullable=False)
    policy_id       = Column(Integer, ForeignKey("policies.id"), nullable=False)
    payment_id      = Column(Integer, ForeignKey("payments.id"), nullable=True)
    recipient_email = Column(String(200), nullable=False)
    subject         = Column(String(500))
    body_html       = Column(Text)
    status          = Column(SQLEnum(EmailStatus), default=EmailStatus.QUEUED)
    sent_at         = Column(DateTime)
    error_message   = Column(String(1000))
    created_date    = Column(DateTime, default=datetime.now)

    policy          = relationship("Policy", back_populates="email_queue")
    payment         = relationship("Payment", back_populates="email_queue")


# ── DATABASE SETUP ─────────────────────────────────────────────────────────────

_engine = None

def get_database_url():
    url = os.getenv("DATABASE_URL", "")
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url or "sqlite:///chi_portal.db"

def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(
            get_database_url(),
            pool_pre_ping=True,
            pool_recycle=3600,
            echo=False
        )
    return _engine

def get_session():
    Session = sessionmaker(bind=get_engine())
    return Session()

def init_db():
    Base.metadata.create_all(get_engine())

# ── SERIALIZERS (convert SQLAlchemy objects to plain dicts) ────────────────────

def _d(val):
    """Convert date/datetime/enum to JSON-safe value."""
    if val is None: return None
    if hasattr(val, 'strftime'): return val.strftime("%Y-%m-%d")
    if hasattr(val, 'value'):    return val.value
    return val

def ser_client(c) -> dict:
    if not c: return {}
    return {
        "id": c.id, "name": c.name or "", "email": c.email or "",
        "phone": c.phone or "", "mobile": c.mobile or "",
        "address": c.address or "", "city": c.city or "",
        "postal_code": c.postal_code or "", "tax_id": c.tax_id or "",
        "id_number": c.id_number or "", "date_of_birth": _d(c.date_of_birth),
        "profession": c.profession or "", "company_name": c.company_name or "",
        "notes": c.notes or "", "vip": bool(c.vip),
        "portal_access": bool(c.portal_access),
        "created_date": _d(c.created_date),
    }

def ser_policy(p) -> dict:
    if not p: return {}
    return {
        "id": p.id, "client_id": p.client_id,
        "policy_number": p.policy_number or "",
        "sector": _d(p.sector), "sector_name": p.sector.name if p.sector else "OTHER",
        "policy_type": p.policy_type or "",
        "provider": p.provider or "",
        "license_plate": p.license_plate or "",
        "vehicle_make": p.vehicle_make or "", "vehicle_model": p.vehicle_model or "",
        "premium": float(p.premium or 0),
        "commission_rate": float(p.commission_rate or 0),
        "commission_amount": float(p.commission_amount or 0),
        "commission": float(p.commission_amount or 0) or float(p.premium or 0) * float(p.commission_rate or 0) / 100,
        "payment_frequency": _d(p.payment_frequency),
        "payment_code": p.payment_code or "",
        "start_date": _d(p.start_date), "expiration_date": _d(p.expiration_date),
        "status": _d(p.status), "status_name": p.status.name if p.status else "ACTIVE",
        "agent": p.agent or "", "beneficiary": p.beneficiary or "",
        "coverage_details": p.coverage_details or "",
        "hal_summary": p.hal_summary or "",
        "insured_value": float(p.insured_value or 0),
    }

def ser_payment(pay) -> dict:
    if not pay: return {}
    return {
        "id": pay.id, "policy_id": pay.policy_id,
        "amount": float(pay.amount or 0),
        "due_date": _d(pay.due_date), "payment_date": _d(pay.payment_date),
        "status": _d(pay.status), "status_name": pay.status.name if pay.status else "PENDING",
        "method": pay.method or "", "receipt_num": pay.receipt_num or "",
        "notes": pay.notes or "",
    }

def ser_claim(c) -> dict:
    if not c: return {}
    return {
        "id": c.id, "policy_id": c.policy_id,
        "claim_number": c.claim_number or "",
        "description": c.description or "",
        "claim_amount": float(c.claim_amount or 0),
        "settled_amount": float(c.settled_amount or 0),
        "status": _d(c.status), "status_name": c.status.name if c.status else "OPEN",
        "incident_date": _d(c.incident_date),
        "reported_date": _d(c.reported_date),
        "resolved_date": _d(c.resolved_date),
        "notes": c.notes or "",
    }

def ser_ticket(t) -> dict:
    if not t: return {}
    return {
        "id": t.id, "client_id": t.client_id, "policy_id": t.policy_id,
        "subject": t.subject or "", "description": t.description or "",
        "status": _d(t.status), "status_name": t.status.name if t.status else "OPEN",
        "priority": _d(t.priority), "priority_name": t.priority.name if t.priority else "MEDIUM",
        "created_by": t.created_by or "", "assigned_to": t.assigned_to or "",
        "resolution": t.resolution or "",
        "created_date": _d(t.created_date), "updated_date": _d(t.updated_date),
        "resolved_date": _d(t.resolved_date),
    }

def ser_document(doc) -> dict:
    if not doc: return {}
    return {
        "id": doc.id, "client_id": doc.client_id, "policy_id": doc.policy_id,
        "filename": doc.filename or "", "original_filename": doc.original_filename or "",
        "file_type": doc.file_type or "", "file_size": doc.file_size or 0,
        "ai_summary": doc.ai_summary or "",
        "uploaded_by": doc.uploaded_by or "",
        "uploaded_date": _d(doc.uploaded_date),
        "is_policy_doc": bool(doc.is_policy_doc),
    }

def ser_provider(p) -> dict:
    if not p: return {}
    return {
        "id": p.id, "name": p.name or "", "short_name": p.short_name or "",
        "sector": p.sector or "", "contact_person": p.contact_person or "",
        "email": p.email or "", "phone": p.phone or "", "website": p.website or "",
        "default_commission": float(p.default_commission or 0),
        "active": bool(p.active), "notes": p.notes or "",
    }

def ser_commission(s) -> dict:
    if not s: return {}
    return {
        "id": s.id, "provider_id": s.provider_id,
        "period_month": s.period_month, "period_year": s.period_year,
        "total_premium": float(s.total_premium or 0),
        "commission_rate": float(s.commission_rate or 0),
        "commission_amount": float(s.commission_amount or 0),
        "paid": bool(s.paid), "paid_date": _d(s.paid_date),
        "notes": s.notes or "", "ai_insights": s.ai_insights or "",
        "uploaded_date": _d(s.uploaded_date),
    }

def ser_lixiaria(li) -> dict:
    if not li: return {}
    return {
        "id": li.id, "policy_id": li.policy_id, "provider_id": li.provider_id,
        "expiry_month": li.expiry_month, "expiry_year": li.expiry_year,
        "renewal_sent": bool(li.renewal_sent),
        "renewal_sent_date": _d(li.renewal_sent_date),
        "hal_email_draft": li.hal_email_draft or "",
        "renewal_confirmed": bool(li.renewal_confirmed),
        "notes": li.notes or "",
    }

def ser_email_queue(e) -> dict:
    if not e: return {}
    return {
        "id": e.id, "client_id": e.client_id, "policy_id": e.policy_id,
        "payment_id": e.payment_id, "recipient_email": e.recipient_email or "",
        "subject": e.subject or "", "body_html": e.body_html or "",
        "status": _d(e.status), "status_name": e.status.name if e.status else "QUEUED",
        "sent_at": _d(e.sent_at), "error_message": e.error_message or "",
        "created_date": _d(e.created_date),
    }

def ser_agent(a) -> dict:
    if not a: return {}
    return {
        "id": a.id, "code": a.code, "name": a.name or "",
        "email": a.email or "", "phone": a.phone or "", "mobile": a.mobile or "",
        "address": a.address or "", "company_name": a.company_name or "",
        "tax_id": a.tax_id or "", "commission_rate": float(a.commission_rate or 0),
        "active": bool(a.active), "is_admin": bool(a.is_admin),
        "notes": a.notes or "", "created_date": _d(a.created_date),
    }
