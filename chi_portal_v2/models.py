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
    client_id    = Column(Integer, ForeignKey("clients.id"), nullable=True)
    created_date = Column(DateTime, default=datetime.now)
    last_login   = Column(DateTime)
    client       = relationship("Client", back_populates="user", uselist=False)


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
