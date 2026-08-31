"""
CHI Insurance Portal v2 — Main Application
Flask + SQLAlchemy | Railway PostgreSQL | HAL AI Brain
Three Portals: Agent · Client · Back Office
"""
import os, io, json, base64, base64
from datetime import datetime, timedelta, date
from functools import wraps
from flask import (Flask, render_template, request, redirect, url_for,
                   flash, session, jsonify, send_file, abort)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

import models as m
import hal_engine as hal

# ── APP SETUP ──────────────────────────────────────────────────────────────────

app = Flask(__name__, template_folder="templates")
app.secret_key = os.getenv("SECRET_KEY", "chi-insurance-v2-secret-2026")
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024   # 16MB uploads
app.config["SESSION_PERMANENT"] = False          # expire session on browser close
app.config["SESSION_COOKIE_SECURE"] = False      # set True if HTTPS only
app.config["SESSION_COOKIE_HTTPONLY"] = True     # no JS access to cookie
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

# CHI Contact info (available in all templates)
CHI_CONTACT = {
    "name": "CHI Insurance Brokers",
    "phone": "+306975900189",
    "email": "xiatropoulos@gmail.com",
    "company": "CHI Insurance Brokers",
}

@app.context_processor
def _inject_chi():
    return {"CHI_CONTACT": CHI_CONTACT}

# context_processor defined above

def _run_migrations():
    """Auto-migrate: create missing tables/columns on startup."""
    from sqlalchemy import text as _text
    try:
        m.init_db()
    except Exception:
        pass
    try:
        engine = m.get_engine()
        with engine.connect() as conn:
            for sql in [
                "ALTER TABLE users ADD COLUMN agent_code VARCHAR(20)",
                "ALTER TABLE users ADD COLUMN must_change_password BOOLEAN DEFAULT TRUE",
            ]:
                try:
                    conn.execute(_text(sql)); conn.commit()
                except Exception: pass
    except Exception:
        pass

_run_migrations()

# ── INSTALLMENT HELPER ─────────────────────────────────────────────────────────

def _add_months(d, months):
    """Add months to a date using stdlib only — no dateutil needed."""
    import calendar
    month = d.month - 1 + months
    year  = d.year + month // 12
    month = month % 12 + 1
    day   = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _create_installments(db, policy, annual_premium):
    """Create Payment installment records based on policy.payment_frequency.

    Maps frequency → number of installments per year:
      ANNUAL    → 1  installment  (full year, one payment)
      SEMI      → 2  installments (every 6 months)
      QUARTERLY → 4  installments (every 3 months)
      MONTHLY   → 12 installments (every month)

    Amount per installment = annual_premium / n_installments.
    Due dates step forward from policy.start_date by the month interval.
    """
    freq = policy.payment_frequency
    freq_map = {
        m.PaymentFrequency.ANNUAL:    (1,  12),
        m.PaymentFrequency.SEMI:      (2,   6),
        m.PaymentFrequency.QUARTERLY: (4,   3),
        m.PaymentFrequency.MONTHLY:   (12,  1),
    }
    n_installments, month_step = freq_map.get(freq, (1, 12))
    installment_amount = round(annual_premium / n_installments, 2)

    base_date = policy.start_date or policy.expiration_date or date.today()

    for i in range(n_installments):
        due = _add_months(base_date, month_step * i)
        pay = m.Payment(
            policy_id=policy.id,
            amount=installment_amount,
            due_date=due,
            status=m.PaymentStatus.PENDING,
        )
        db.add(pay)

    return n_installments, installment_amount


ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png", "docx", "xlsx", "doc"}

@app.template_filter("chi_date")
def chi_date_filter(s):
    """Format YYYY-MM-DD string to DD/MM/YYYY for display."""
    if not s: return "—"
    try:
        p = str(s).split("-")
        if len(p) == 3 and len(p[0]) == 4:
            return f"{p[2]}/{p[1]}/{p[0]}"
    except Exception:
        pass
    return str(s)

@app.template_filter("chi_datetime")
def chi_datetime_filter(s):
    """Format YYYY-MM-DD string to DD/MM/YYYY."""
    return chi_date_filter(s)

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

# ── AUTH HELPERS ───────────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

def agent_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        if session.get("role") not in ("agent", "backoffice"):
            flash("Δεν έχετε πρόσβαση σε αυτή τη σελίδα.", "danger")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

def backoffice_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        if session.get("role") not in ("backoffice", "agent"):
            flash("Δεν έχετε πρόσβαση.", "danger")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

def client_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

def current_user():
    if "user_id" not in session:
        return None
    db = m.get_session()
    u = db.query(m.User).get(session["user_id"])
    db.close()
    return u

# ── AUTH ROUTES ────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    if "user_id" not in session:
        return redirect(url_for("login"))
    role = session.get("role")
    if role == "agent":
        return redirect(url_for("agent_dashboard"))
    if role == "backoffice":
        return redirect(url_for("backoffice_dashboard"))
    return redirect(url_for("client_dashboard"))

@app.route("/agent")
def agent_index():
    return redirect(url_for("agent_dashboard"))

@app.route("/backoffice")
def backoffice_index():
    return redirect(url_for("backoffice_dashboard"))

@app.route("/client")
def client_index():
    return redirect(url_for("client_dashboard"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("index"))
    if request.method == "POST":
        email    = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        db = m.get_session()
        user = db.query(m.User).filter_by(email=email, active=True).first()
        if user and check_password_hash(user.password_hash, password):
            # Read ALL values before closing session — handle missing columns gracefully
            role  = user.role.value
            uid   = user.id
            name  = user.name or email
            try: cid = user.client_id
            except Exception: cid = None
            try: agent_scope = user.agent_code
            except Exception: agent_scope = None
            try: must_change = bool(user.must_change_password) if user.must_change_password is not None else False
            except Exception: must_change = False
            try:
                user.last_login = datetime.now()
                db.commit()
            except Exception:
                try: db.rollback()
                except Exception: pass
            db.close()
            session["user_id"]     = uid
            session["role"]        = role
            session["user_name"]   = name
            session["client_id"]   = cid
            session["agent_scope"] = agent_scope
            if must_change:
                return redirect(url_for("change_password_forced"))
            if role == "agent":
                return redirect(url_for("agent_dashboard"))
            if role == "backoffice":
                return redirect(url_for("backoffice_dashboard"))
            return redirect(url_for("client_dashboard"))
        db.close()
        flash("Λάθος email ή κωδικός.", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ── SETUP ROUTE (first time DB init + admin user) ──────────────────────────────

@app.route("/setup", methods=["GET", "POST"])
def setup():
    import traceback
    setup_key = os.getenv("SETUP_KEY", "chi-setup-2026")
    style = "font-family:sans-serif;max-width:500px;margin:60px auto;padding:20px"
    if request.method == "POST":
        if request.form.get("key") != setup_key:
            return f"<div style='{style}'><h3 style='color:red'>❌ Invalid setup key</h3><a href='/setup'>Back</a></div>", 403
        try:
            m.init_db()
            db = m.get_session()
            created = []
            agent_pw = os.getenv("AGENT_PASSWORD", "YouM@tt3r!")
            backoffice_pw = os.getenv("BACKOFFICE_PASSWORD", "YouM@tt3r!")
            # Create default admin agent (chi = head office)
            if not db.query(m.Agent).filter_by(code="chi").first():
                db.add(m.Agent(code="chi", name="Chris Iatropoulos — CHI Insurance Brokers",
                               email="info@chiinsurancebrokers.com", is_admin=True, active=True,
                               company_name="CHI Insurance Brokers"))
                created.append("Admin Agent: chi")
            db.flush()
            # Admin user
            existing_admin = db.query(m.User).filter_by(email="info@chiinsurancebrokers.com").first()
            if not existing_admin:
                db.add(m.User(email="info@chiinsurancebrokers.com",
                              password_hash=generate_password_hash(agent_pw),
                              role=m.UserRole.AGENT, name="Chris Iatropoulos",
                              agent_code=None))
                created.append("Admin user")
            else:
                existing_admin.name = "CHI Insurance Brokers"
                existing_admin.agent_code = None
            # Backoffice user
            if not db.query(m.User).filter_by(email="backoffice@chiinsurancebrokers.com").first():
                db.add(m.User(email="backoffice@chiinsurancebrokers.com",
                              password_hash=generate_password_hash(backoffice_pw),
                              role=m.UserRole.BACKOFFICE, name="Back Office CHI",
                              agent_code=None))
                created.append("Backoffice user")
            # kiraainurse — client portal user
            kira_email = "kiraainurse@chiinsurancebrokers.com"
            if not db.query(m.User).filter_by(email=kira_email).first():
                # Find client by email or name
                kira_client = (
                    db.query(m.Client).filter(m.Client.email.ilike("%kira%")).first() or
                    db.query(m.Client).filter(m.Client.name.ilike("%ΚΥΡΑ%")).first()
                )
                kira_user = m.User(
                    email=kira_email,
                    password_hash=generate_password_hash(DEFAULT_PASSWORD),
                    role=m.UserRole.CLIENT,
                    name="Kira Nurse",
                    client_id=kira_client.id if kira_client else None,
                    must_change_password=True,
                    active=True,
                )
                db.add(kira_user)
                if kira_client:
                    kira_client.portal_access = True
                created.append("kiraainurse portal user")
            db.commit()
            db.close()
            # Also update current session name
            if session.get("agent_scope") is None and session.get("role") == "agent":
                session["user_name"] = "CHI Insurance Brokers"
            return f"""<div style='{style}'>
            <h2 style='color:green'>✅ Setup complete!</h2>
            <p>Created: {', '.join(created) if created else 'Users already existed'}</p>
            <p><strong>Agent login:</strong> info@chiinsurancebrokers.com / {agent_pw}</p>
            <p><strong>DB URL:</strong> {os.getenv('DATABASE_URL','NOT SET')[:40]}...</p>
            <a href='/login' style='background:#1B2B5E;color:white;padding:10px 20px;text-decoration:none;border-radius:6px'>→ Login</a>
            </div>"""
        except Exception as e:
            tb = traceback.format_exc()
            return f"""<div style='{style}'>
            <h2 style='color:red'>❌ Setup failed</h2>
            <pre style='background:#f5f5f5;padding:12px;border-radius:6px;font-size:12px;overflow-x:auto'>{tb}</pre>
            <p><strong>DATABASE_URL set:</strong> {bool(os.getenv('DATABASE_URL'))}</p>
            </div>""", 500
    # GET
    db_url = os.getenv("DATABASE_URL", "NOT SET")
    db_status = "✅ Set" if os.getenv("DATABASE_URL") else "❌ NOT SET — add PostgreSQL plugin in Railway"
    return f"""<!DOCTYPE html><html><body style='{style}'>
    <h2>CHI Insurance Portal v2 — Setup</h2>
    <p>DB: {db_status}</p>
    <p>ANTHROPIC_API_KEY: {"✅ Set" if os.getenv("ANTHROPIC_API_KEY") else "⚠️ Not set (HAL won't work)"}</p>
    <hr>
    <form method=POST>
      <p>Setup Key: <input name=key type=password style='padding:8px;width:100%;margin-top:4px'></p>
      <button type=submit style='padding:10px 24px;background:#1B2B5E;color:white;border:none;border-radius:6px;cursor:pointer;font-size:15px'>
        Initialize Database & Create Users
      </button>
    </form>
    </body></html>"""

# ══════════════════════════════════════════════════════════════════════════════
# PORTAL 1 — AGENT
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/agent/dashboard")
@agent_required
def agent_dashboard():
    db = m.get_session()
    today = date.today()
    thirty = today + timedelta(days=30)
    seven  = today + timedelta(days=7)
    try:
        scope = get_agent_scope()
        def scoped_pol(q):
            return q.filter(m.Policy.agent == scope) if scope else q
        if scope:
            # For scoped agents: count only their clients
            client_ids = [r[0] for r in db.query(m.Policy.client_id).filter(m.Policy.agent==scope).distinct().all()]
            total_clients = len(client_ids)
        else:
            total_clients    = db.query(m.Client).count()
        active_policies  = scoped_pol(db.query(m.Policy).filter_by(status=m.PolicyStatus.ACTIVE)).count()
        pending_payments = db.query(m.Payment).filter_by(status=m.PaymentStatus.PENDING).count()
        overdue_payments = db.query(m.Payment).filter_by(status=m.PaymentStatus.OVERDUE).count()
        expiring_30 = scoped_pol(db.query(m.Policy).filter(
            m.Policy.expiration_date.between(today, thirty),
            m.Policy.status == m.PolicyStatus.ACTIVE)).count()
        expiring_7 = scoped_pol(db.query(m.Policy).filter(
            m.Policy.expiration_date.between(today, seven),
            m.Policy.status == m.PolicyStatus.ACTIVE)).count()
        open_tickets = db.query(m.Ticket).filter(
            m.Ticket.status.in_([m.TicketStatus.OPEN, m.TicketStatus.IN_PROCESS])
        ).count()
        # Total active premium
        total_premium = scoped_pol(db.query(m.Policy).filter_by(status=m.PolicyStatus.ACTIVE)).all()
        total_premium_val = sum((p.premium or 0) for p in total_premium)
        # Commission (30% avg estimated)
        total_commission = sum(((p.commission_amount or 0) if p.commission_amount else (p.premium or 0) * (p.commission_rate or 0) / 100) for p in total_premium)
        # Urgent renewals
        urgent = scoped_pol(db.query(m.Policy).filter(
            m.Policy.expiration_date.between(today, seven),
            m.Policy.status == m.PolicyStatus.ACTIVE
        )).order_by(m.Policy.expiration_date).limit(8).all()
        urgent_data = []
        for p in urgent:
            c = db.query(m.Client).get(p.client_id)
            urgent_data.append({
                "client": c.name if c else "—", "client_id": c.id if c else None,
                "policy_type": p.policy_type or "—", "provider": p.provider or "—",
                "expires": p.expiration_date.strftime("%d/%m/%Y") if p.expiration_date else "—",
                "days_left": (p.expiration_date - today).days if p.expiration_date else 0,
                "premium": p.premium or 0, "policy_id": p.id
            })
        # Recent clients — scoped by agent
        if scope:
            _scoped_cids = [r[0] for r in db.query(m.Policy.client_id).filter(
                m.Policy.agent == scope).distinct().all()]
            _rq = db.query(m.Client).filter(m.Client.id.in_(_scoped_cids))
        else:
            _rq = db.query(m.Client)
        recent_raw = _rq.order_by(m.Client.created_date.desc()).limit(5).all()
        recent_clients = [m.ser_client(c) for c in recent_raw]
        stats = {
            "total_clients": total_clients, "active_policies": active_policies,
            "pending_payments": pending_payments, "overdue_payments": overdue_payments,
            "expiring_30": expiring_30, "expiring_7": expiring_7,
            "open_tickets": open_tickets, "total_premium": total_premium_val,
            "total_commission": total_commission
        }
        return render_template("agent/dashboard.html", stats=stats,
                               urgent=urgent_data, recent_clients=recent_clients,
                               today=today.strftime("%Y-%m-%d"))
    finally:
        db.close()

@app.route("/agent/clients")
@agent_required
def agent_clients():
    db = m.get_session()
    search     = request.args.get("q", "").strip()
    sector_f   = request.args.get("sector", "")
    provider_f = request.args.get("provider", "")
    agent_f    = request.args.get("agent", "")
    month_f    = request.args.get("month", "", )
    year_f     = request.args.get("year", "")
    try:
        all_providers = [r[0] for r in db.query(m.Policy.provider).filter(m.Policy.provider != None).distinct().order_by(m.Policy.provider).all()]
        all_agents    = [r[0] for r in db.query(m.Policy.agent).filter(m.Policy.agent != None).distinct().order_by(m.Policy.agent).all()]
        scope = get_agent_scope()
        q = db.query(m.Client)
        if search:
            q = q.filter(
                (m.Client.name.ilike(f"%{search}%")) |
                (m.Client.email.ilike(f"%{search}%")) |
                (m.Client.phone.ilike(f"%{search}%")) |
                (m.Client.tax_id.ilike(f"%{search}%"))
            )
        # Always scope by agent if not admin
        if scope and not agent_f:
            agent_f = scope
        if sector_f or provider_f or agent_f or month_f or year_f:
            policy_q = db.query(m.Policy.client_id)
            if sector_f:
                try: policy_q = policy_q.filter(m.Policy.sector == m.PolicySector[sector_f])
                except KeyError: pass
            if provider_f:
                policy_q = policy_q.filter(m.Policy.provider == provider_f)
            if agent_f:
                policy_q = policy_q.filter(m.Policy.agent == agent_f)
            if month_f:
                policy_q = policy_q.filter(m.db_func_extract_month(m.Policy.expiration_date) == int(month_f)) if hasattr(m, 'db_func_extract_month') else policy_q
            client_ids = [r[0] for r in policy_q.distinct().all()]
            q = q.filter(m.Client.id.in_(client_ids))
        clients = q.order_by(m.Client.name).all()
        data = []
        today = date.today()
        for c in clients:
            policies = db.query(m.Policy).filter_by(client_id=c.id).all()
            active_p = [p for p in policies if p.status == m.PolicyStatus.ACTIVE]
            if sector_f:
                try: active_p = [p for p in active_p if p.sector == m.PolicySector[sector_f]]
                except KeyError: pass
            if provider_f:
                active_p = [p for p in active_p if p.provider == provider_f]
            if agent_f:
                active_p = [p for p in active_p if p.agent == agent_f]
            if month_f and year_f:
                active_p = [p for p in active_p if p.expiration_date and p.expiration_date.month == int(month_f) and p.expiration_date.year == int(year_f)]
            elif month_f:
                active_p = [p for p in active_p if p.expiration_date and p.expiration_date.month == int(month_f)]
            elif year_f:
                active_p = [p for p in active_p if p.expiration_date and p.expiration_date.year == int(year_f)]
            total_premium = sum((p.premium or 0) for p in active_p)
            commission = sum(((p.commission_amount or 0) or (p.premium or 0) * (p.commission_rate or 0)/100) for p in active_p)
            sectors = list(set(p.sector.value for p in active_p if p.sector))
            providers = list(set(p.provider for p in active_p if p.provider))
            next_exp = min((p.expiration_date for p in active_p if p.expiration_date), default=None)
            pending = db.query(m.Payment).join(m.Policy).filter(
                m.Policy.client_id == c.id,
                m.Payment.status == m.PaymentStatus.PENDING
            ).count()
            if not active_p and (sector_f or provider_f or agent_f or month_f or year_f):
                continue
            data.append({
                "id": c.id, "name": c.name, "email": c.email, "phone": c.phone,
                "city": c.city, "vip": c.vip, "portal_access": c.portal_access,
                "total_policies": len(policies), "active_policies": len(active_p),
                "total_premium": total_premium, "commission": commission,
                "sectors": sectors, "providers": providers,
                "next_expiry": next_exp, "pending_payments": pending
            })
        month_names = ["","Ιαν","Φεβ","Μαρ","Απρ","Μαι","Ιουν","Ιουλ","Αυγ","Σεπ","Οκτ","Νοε","Δεκ"]
        years = list(range(date.today().year - 1, date.today().year + 3))
        return render_template("agent/clients.html", clients=data, search=search,
                               sector_f=sector_f, provider_f=provider_f, agent_f=agent_f,
                               month_f=month_f, year_f=year_f,
                               sectors=m.PolicySector, all_providers=all_providers,
                               all_agents=all_agents, month_names=month_names,
                               months=range(1,13), years=years, today=today)
    finally:
        db.close()

@app.route("/agent/clients/duplicates")
@agent_required
def agent_duplicate_clients():
    """Find clients sharing the same ΑΦΜ (tax_id) — candidates for merging."""
    from sqlalchemy import func
    db = m.get_session()
    try:
        # Group by normalized (trimmed) tax_id, ignore blanks, find groups with >1 client
        dup_tax_ids = [
            r[0] for r in db.query(func.trim(m.Client.tax_id))
            .filter(m.Client.tax_id != None, func.trim(m.Client.tax_id) != "")
            .group_by(func.trim(m.Client.tax_id))
            .having(func.count(m.Client.id) > 1)
            .all()
        ]
        groups = []
        for tax_id in dup_tax_ids:
            clients = db.query(m.Client).filter(
                func.trim(m.Client.tax_id) == tax_id
            ).order_by(m.Client.id).all()
            rows = []
            for c in clients:
                rows.append({
                    "id": c.id, "name": c.name, "email": c.email, "phone": c.phone,
                    "mobile": c.mobile, "city": c.city, "tax_id": c.tax_id,
                    "created_date": c.created_date.strftime("%d/%m/%Y") if c.created_date else "—",
                    "policies": db.query(m.Policy).filter_by(client_id=c.id).count(),
                    "tickets": db.query(m.Ticket).filter_by(client_id=c.id).count(),
                    "documents": db.query(m.Document).filter_by(client_id=c.id).count(),
                    "has_portal": db.query(m.User).filter_by(client_id=c.id).count() > 0,
                })
            groups.append({"tax_id": tax_id, "clients": rows})
        return render_template("agent/duplicate_clients.html", groups=groups)
    finally:
        db.close()


@app.route("/agent/clients/merge", methods=["POST"])
@agent_required
def agent_merge_clients():
    """Merge one or more duplicate client records into a single 'keeper' record.

    Moves all policies, tickets, documents, email-queue entries and portal
    user accounts from the duplicate(s) onto the keeper, then deletes the
    duplicate client rows. Fields blank on the keeper are filled in from the
    duplicates where available, so no information is lost.
    """
    keep_id = request.form.get("keep_id", type=int)
    dup_ids = [int(x) for x in request.form.getlist("dup_ids") if x and x.isdigit()]
    dup_ids = [d for d in dup_ids if d != keep_id]

    if not keep_id or not dup_ids:
        flash("Επιλέξτε ποια εγγραφή θα διατηρηθεί και ποιες θα ενωθούν σε αυτή.", "danger")
        return redirect(url_for("agent_duplicate_clients"))

    db = m.get_session()
    try:
        keeper = db.query(m.Client).get(keep_id)
        if not keeper:
            flash("Δεν βρέθηκε η εγγραφή προορισμού.", "danger")
            return redirect(url_for("agent_duplicate_clients"))

        moved_policies = moved_tickets = moved_documents = moved_emails = moved_users = 0
        merged_names = []

        for dup_id in dup_ids:
            dup = db.query(m.Client).get(dup_id)
            if not dup:
                continue
            merged_names.append(dup.name)

            # Fill in any blank fields on the keeper from the duplicate
            for field in ("email", "phone", "mobile", "address", "postal_code",
                          "city", "tax_id", "id_number", "date_of_birth",
                          "profession", "company_name"):
                if not getattr(keeper, field) and getattr(dup, field):
                    setattr(keeper, field, getattr(dup, field))
            if dup.vip:
                keeper.vip = True
            if dup.notes:
                keeper.notes = (keeper.notes + "\n" if keeper.notes else "") + f"[Από συγχώνευση #{dup.id}] {dup.notes}"

            # Re-point every related record at the keeper
            moved_policies  += db.query(m.Policy).filter_by(client_id=dup.id) \
                .update({m.Policy.client_id: keeper.id}, synchronize_session=False)
            moved_tickets   += db.query(m.Ticket).filter_by(client_id=dup.id) \
                .update({m.Ticket.client_id: keeper.id}, synchronize_session=False)
            moved_documents += db.query(m.Document).filter_by(client_id=dup.id) \
                .update({m.Document.client_id: keeper.id}, synchronize_session=False)
            moved_emails    += db.query(m.EmailQueue).filter_by(client_id=dup.id) \
                .update({m.EmailQueue.client_id: keeper.id}, synchronize_session=False)

            # Portal login accounts: only one user can own client_id at a time —
            # if the keeper has no portal account yet, hand the duplicate's over.
            dup_users = db.query(m.User).filter_by(client_id=dup.id).all()
            for u in dup_users:
                keeper_has_user = db.query(m.User).filter_by(client_id=keeper.id).first()
                if not keeper_has_user:
                    u.client_id = keeper.id
                    keeper.portal_access = True
                    moved_users += 1
                else:
                    # Keeper already has portal access — deactivate the orphaned login
                    u.client_id = None
                    u.active = False

            db.delete(dup)

        keeper.updated_date = datetime.now()
        db.commit()
        flash(
            f"✅ Συγχωνεύθηκαν {len(merged_names)} διπλοεγγραφές ({', '.join(merged_names)}) στον πελάτη «{keeper.name}». "
            f"Μεταφέρθηκαν: {moved_policies} συμβόλαια, {moved_tickets} tickets, "
            f"{moved_documents} έγγραφα, {moved_emails} emails"
            + (f", {moved_users} portal login" if moved_users else "") + ".",
            "success"
        )
        return redirect(url_for("agent_client_detail", client_id=keeper.id))
    except Exception as e:
        db.rollback()
        flash(f"❌ Σφάλμα κατά τη συγχώνευση: {e}", "danger")
        return redirect(url_for("agent_duplicate_clients"))
    finally:
        db.close()


@app.route("/agent/client/add", methods=["GET", "POST"])
@agent_required
def agent_add_client():
    if request.method == "POST":
        db = m.get_session()
        try:
            tax_id = (request.form.get("tax_id") or "").strip()
            # Warn (don't silently duplicate) if this ΑΦΜ already belongs to another client
            if tax_id and not request.form.get("force_duplicate"):
                existing = db.query(m.Client).filter(m.Client.tax_id == tax_id).first()
                if existing:
                    flash(
                        f"⚠️ Υπάρχει ήδη πελάτης με ΑΦΜ {tax_id}: «{existing.name}» (#{existing.id}). "
                        f"Πατήστε «Καταχώρηση ούτως ή άλλως» αν θέλετε να τον προσθέσετε σαν νέα εγγραφή.",
                        "danger"
                    )
                    form_data = {k: request.form.get(k) for k in request.form}
                    return render_template("agent/client_form.html", client=form_data,
                                           action="add", duplicate_warning=existing)
            dob_str = request.form.get("date_of_birth")
            dob = datetime.strptime(dob_str, "%Y-%m-%d").date() if dob_str else None
            client = m.Client(
                name=request.form.get("name"), email=request.form.get("email"),
                phone=request.form.get("phone"), mobile=request.form.get("mobile"),
                address=request.form.get("address"), postal_code=request.form.get("postal_code"),
                city=request.form.get("city"), tax_id=tax_id or None,
                id_number=request.form.get("id_number"), date_of_birth=dob,
                profession=request.form.get("profession"), company_name=request.form.get("company_name"),
                notes=request.form.get("notes"), vip=bool(request.form.get("vip"))
            )
            db.add(client)
            db.commit()
            # Create portal access if email provided
            if client.email and request.form.get("create_portal"):
                pw = request.form.get("portal_password", "chi2026!")
                user = m.User(email=client.email, password_hash=generate_password_hash(pw),
                              role=m.UserRole.CLIENT, name=client.name, client_id=client.id)
                db.add(user)
                client.portal_access = True
                db.commit()
            flash(f"✅ Ο πελάτης {client.name} προστέθηκε.", "success")
            return redirect(url_for("agent_client_detail", client_id=client.id))
        except Exception as e:
            db.rollback()
            flash(f"Σφάλμα: {e}", "danger")
        finally:
            db.close()
    return render_template("agent/client_form.html", client={}, action="add")

@app.route("/agent/client/<int:client_id>")
@agent_required
def agent_client_detail(client_id):
    db = m.get_session()
    try:
        client = db.query(m.Client).get(client_id)
        if not client:
            abort(404)
        policies = db.query(m.Policy).filter_by(client_id=client_id).order_by(m.Policy.expiration_date).all()
        today = date.today()
        # Enrich policies
        pol_data = []
        for p in policies:
            payments = db.query(m.Payment).filter_by(policy_id=p.id).order_by(m.Payment.due_date).all()
            next_payment = next((pay for pay in payments if pay.status == m.PaymentStatus.PENDING), None)
            overdue = [pay for pay in payments if pay.status == m.PaymentStatus.OVERDUE]
            days_left = (p.expiration_date - today).days if p.expiration_date else None
            pol_data.append({
                "policy": p, "payments": payments, "next_payment": next_payment,
                "overdue": overdue, "days_left": days_left,
                "commission": p.commission_amount or (p.premium or 0) * (p.commission_rate or 0) / 100
            })
        tickets = db.query(m.Ticket).filter_by(client_id=client_id).order_by(m.Ticket.created_date.desc()).all()
        documents = db.query(m.Document).filter_by(client_id=client_id).order_by(m.Document.uploaded_date.desc()).all()
        claims = db.query(m.Claim).join(m.Policy).filter(m.Policy.client_id==client_id).order_by(m.Claim.reported_date.desc()).all()
        # Totals
        active_pols = [p["policy"] for p in pol_data if p["policy"].status == m.PolicyStatus.ACTIVE]
        total_premium  = sum((p.premium or 0) for p in active_pols)
        total_commission = sum((p.commission_amount or (p.premium or 0)*(p.commission_rate or 0)/100) for p in active_pols)
        # Serialize all objects to plain dicts
        client_d = m.ser_client(client)
        pol_data_d = []
        for pd in pol_data:
            p = pd["policy"]
            pol_data_d.append({
                "policy":       m.ser_policy(p),
                "payments":     [m.ser_payment(pay) for pay in pd["payments"]],
                "next_payment": m.ser_payment(pd["next_payment"]) if pd["next_payment"] else None,
                "overdue":      [m.ser_payment(pay) for pay in pd["overdue"]],
                "days_left":    pd["days_left"],
                "commission":   pd["commission"],
            })
        sectors_d = [{"name": s.name, "value": s.value} for s in m.PolicySector]

        # ── Related AFM (family) ──
        related_links = db.query(m.RelatedAFM).filter(
            (m.RelatedAFM.client_id == client_id) | (m.RelatedAFM.related_client_id == client_id)
        ).all()
        related_clients_data = []
        family_policies = []
        seen_ids = set()
        for link in related_links:
            other_id = link.related_client_id if link.client_id == client_id else link.client_id
            if other_id in seen_ids:
                continue
            seen_ids.add(other_id)
            other_client = db.query(m.Client).get(other_id)
            if not other_client:
                continue
            label = link.relationship_label or ""
            link_id = link.id
            related_clients_data.append({
                "link_id": link_id,
                "client": m.ser_client(other_client),
                "relationship_label": label,
            })
            other_policies = db.query(m.Policy).filter_by(client_id=other_id).order_by(m.Policy.expiration_date).all()
            for op in other_policies:
                family_policies.append({
                    "policy": m.ser_policy(op),
                    "client_name": other_client.name,
                    "client_id": other_client.id,
                    "client_tax_id": other_client.tax_id or "",
                })
        family_total_premium = sum(
            fp["policy"]["premium"] for fp in family_policies
            if fp["policy"]["status_name"] == "ACTIVE"
        )

        return render_template("agent/client_detail.html",
            client=client_d, pol_data=pol_data_d,
            tickets=[m.ser_ticket(t) for t in tickets],
            documents=[m.ser_document(d) for d in documents],
            claims=[m.ser_claim(c) for c in claims],
            today=today.strftime("%Y-%m-%d"),
            total_premium=total_premium, total_commission=total_commission,
            sectors=sectors_d,
            related_clients=related_clients_data,
            family_policies=family_policies,
            family_total_premium=family_total_premium)
    finally:
        db.close()

# ── RELATED AFM (Family linking) ──────────────────────────────────────────

@app.route("/agent/client/<int:client_id>/related-afm/search")
@agent_required
def agent_search_clients_for_afm(client_id):
    """Search clients by name or AFM to link as family."""
    q = request.args.get("q", "").strip()
    if len(q) < 2:
        return jsonify([])
    db = m.get_session()
    try:
        needle = _strip_greek_accents(q)
        candidates = db.query(m.Client).filter(m.Client.id != client_id).all()
        results = [
            c for c in candidates
            if needle in _strip_greek_accents(c.name or "")
            or needle in _strip_greek_accents(c.tax_id or "")
        ][:10]
        existing = db.query(m.RelatedAFM).filter(
            (m.RelatedAFM.client_id == client_id) | (m.RelatedAFM.related_client_id == client_id)
        ).all()
        linked_ids = set()
        for link in existing:
            linked_ids.add(link.client_id)
            linked_ids.add(link.related_client_id)
        return jsonify([
            {"id": c.id, "name": c.name, "tax_id": c.tax_id or "", "phone": c.mobile or c.phone or ""}
            for c in results if c.id not in linked_ids
        ])
    finally:
        db.close()

@app.route("/agent/client/<int:client_id>/related-afm/add", methods=["POST"])
@agent_required
def agent_add_related_afm(client_id):
    """Link another client as family member."""
    db = m.get_session()
    try:
        related_id = int(request.form.get("related_client_id", 0))
        label = request.form.get("relationship_label", "").strip()
        if not related_id or related_id == client_id:
            flash("Μη έγκυρος πελάτης.", "error")
            return redirect(url_for("agent_client_detail", client_id=client_id))
        existing = db.query(m.RelatedAFM).filter(
            ((m.RelatedAFM.client_id == client_id) & (m.RelatedAFM.related_client_id == related_id)) |
            ((m.RelatedAFM.client_id == related_id) & (m.RelatedAFM.related_client_id == client_id))
        ).first()
        if existing:
            flash("Αυτός ο πελάτης είναι ήδη συσχετισμένος.", "warning")
            return redirect(url_for("agent_client_detail", client_id=client_id))
        link = m.RelatedAFM(client_id=client_id, related_client_id=related_id, relationship_label=label)
        db.add(link)
        db.commit()
        flash("✅ Συσχέτιση ΑΦΜ προστέθηκε!", "success")
    except Exception as e:
        db.rollback()
        flash(f"Σφάλμα: {e}", "error")
    finally:
        db.close()
    return redirect(url_for("agent_client_detail", client_id=client_id))

@app.route("/agent/related-afm/<int:link_id>/remove", methods=["POST"])
@agent_required
def agent_remove_related_afm(link_id):
    """Remove a family link."""
    db = m.get_session()
    try:
        link = db.query(m.RelatedAFM).get(link_id)
        if not link:
            abort(404)
        client_id = int(request.form.get("client_id", link.client_id))
        db.delete(link)
        db.commit()
        flash("Η συσχέτιση αφαιρέθηκε.", "success")
        return redirect(url_for("agent_client_detail", client_id=client_id))
    except Exception as e:
        db.rollback()
        flash(f"Σφάλμα: {e}", "error")
        return redirect(url_for("agent_clients"))
    finally:
        db.close()

@app.route("/agent/client/<int:client_id>/edit", methods=["GET", "POST"])
@agent_required
def agent_edit_client(client_id):
    db = m.get_session()
    client = db.query(m.Client).get(client_id)
    if not client:
        abort(404)
    if request.method == "POST":
        try:
            tax_id = (request.form.get("tax_id") or "").strip()
            # Warn if this ΑΦΜ is being changed to one already used by a *different* client
            if tax_id and not request.form.get("force_duplicate"):
                existing = db.query(m.Client).filter(
                    m.Client.tax_id == tax_id, m.Client.id != client_id
                ).first()
                if existing:
                    flash(
                        f"⚠️ Το ΑΦΜ {tax_id} χρησιμοποιείται ήδη από τον πελάτη «{existing.name}» (#{existing.id}). "
                        f"Μήπως πρόκειται για διπλοεγγραφή; Δείτε τη σελίδα διπλοεγγραφών για συγχώνευση, "
                        f"ή πατήστε «Αποθήκευση ούτως ή άλλως» αν είναι σωστό.",
                        "danger"
                    )
                    client_d = m.ser_client(client)
                    client_d.update({k: request.form.get(k) for k in request.form if k != "tax_id"})
                    client_d["tax_id"] = tax_id
                    db.close()
                    return render_template("agent/client_form.html", client=client_d,
                                           action="edit", duplicate_warning=existing)
            dob_str = request.form.get("date_of_birth")
            client.name        = request.form.get("name")
            client.email       = request.form.get("email")
            client.phone       = request.form.get("phone")
            client.mobile      = request.form.get("mobile")
            client.address     = request.form.get("address")
            client.postal_code = request.form.get("postal_code")
            client.city        = request.form.get("city")
            client.tax_id      = tax_id or None
            client.id_number   = request.form.get("id_number")
            client.date_of_birth = datetime.strptime(dob_str, "%Y-%m-%d").date() if dob_str else None
            client.profession  = request.form.get("profession")
            client.company_name= request.form.get("company_name")
            client.notes       = request.form.get("notes")
            client.vip         = bool(request.form.get("vip"))
            client.updated_date = datetime.now()
            db.commit()
            flash("✅ Στοιχεία πελάτη ενημερώθηκαν.", "success")
            return redirect(url_for("agent_client_detail", client_id=client_id))
        except Exception as e:
            db.rollback(); flash(f"Σφάλμα: {e}", "danger")
        finally:
            db.close()
    db2 = m.get_session(); c2 = db2.query(m.Client).get(client_id); r2 = m.ser_client(c2); db2.close()
    return render_template("agent/client_form.html", client=r2, action="edit")

@app.route("/agent/client/<int:client_id>/policy/add", methods=["GET","POST"])
@agent_required
def agent_add_policy(client_id):
    db = m.get_session()
    client = db.query(m.Client).get(client_id)
    if not client:
        abort(404)
    providers = db.query(m.Provider).filter_by(active=True).order_by(m.Provider.name).all()
    if request.method == "POST":
        try:
            sd = request.form.get("start_date")
            ed = request.form.get("expiration_date")
            sector_val = request.form.get("sector")
            sector = m.PolicySector[sector_val] if sector_val else m.PolicySector.OTHER
            prem = float(request.form.get("premium") or 0)
            comm_rate = float(request.form.get("commission_rate") or 0)
            policy = m.Policy(
                client_id=client_id,
                policy_number=request.form.get("policy_number"),
                sector=sector,
                policy_type=request.form.get("policy_type"),
                provider=request.form.get("provider"),
                premium=prem,
                commission_rate=comm_rate,
                commission_amount=round(prem * comm_rate / 100, 2),
                payment_frequency=m.PaymentFrequency[request.form.get("payment_frequency","ANNUAL")],
                payment_code=request.form.get("payment_code"),
                license_plate=request.form.get("license_plate"),
                vehicle_make=request.form.get("vehicle_make"),
                vehicle_model=request.form.get("vehicle_model"),
                insured_value=float(request.form.get("insured_value") or 0) or None,
                beneficiary=request.form.get("beneficiary"),
                coverage_details=request.form.get("coverage_details"),
                start_date=datetime.strptime(sd,"%Y-%m-%d").date() if sd else None,
                expiration_date=datetime.strptime(ed,"%Y-%m-%d").date() if ed else None,
                status=m.PolicyStatus.ACTIVE,
                agent=request.form.get("agent","chi")
            )
            db.add(policy)
            db.flush()
            # Auto-create lixiario entry
            if policy.expiration_date:
                li = m.LixiariaEntry(
                    policy_id=policy.id,
                    expiry_month=policy.expiration_date.month,
                    expiry_year=policy.expiration_date.year
                )
                db.add(li)
            # Auto-create installments based on payment_frequency
            if prem > 0:
                n, amt = _create_installments(db, policy, prem)
            db.commit()
            freq_label = policy.payment_frequency.value if policy.payment_frequency else "Ετήσια"
            installment_note = f" ({n}x €{amt:.2f}, {freq_label})" if prem > 0 else ""
            flash(f"✅ Συμβόλαιο {policy.policy_number or policy.policy_type} προστέθηκε{installment_note}.", "success")
            return redirect(url_for("agent_client_detail", client_id=client_id))
        except Exception as e:
            db.rollback(); flash(f"Σφάλμα: {e}", "danger")
        finally:
            db.close()
    provs = [m.ser_provider(p) for p in providers]
    db.close()
    return render_template("agent/policy_form.html", client=m.ser_client(client), policy=None,
                           sectors=[{"name":s.name,"value":s.value} for s in m.PolicySector],
                           providers=provs,
                           freq=[{"name":f.name,"value":f.value} for f in m.PaymentFrequency],
                           action="add")

@app.route("/agent/policy/<int:policy_id>/edit", methods=["GET","POST"])
@agent_required
def agent_edit_policy(policy_id):
    db = m.get_session()
    policy = db.query(m.Policy).get(policy_id)
    if not policy:
        abort(404)
    client = db.query(m.Client).get(policy.client_id)
    providers = db.query(m.Provider).filter_by(active=True).order_by(m.Provider.name).all()
    if request.method == "POST":
        try:
            sd = request.form.get("start_date")
            ed = request.form.get("expiration_date")
            sector_val = request.form.get("sector")
            prem = float(request.form.get("premium") or 0)
            comm_rate = float(request.form.get("commission_rate") or 0)
            policy.policy_number  = request.form.get("policy_number")
            policy.sector         = m.PolicySector[sector_val] if sector_val else m.PolicySector.OTHER
            policy.policy_type    = request.form.get("policy_type")
            policy.provider       = request.form.get("provider")
            policy.premium        = prem
            policy.commission_rate = comm_rate
            policy.commission_amount = round(prem * comm_rate / 100, 2)
            policy.license_plate  = request.form.get("license_plate")
            policy.vehicle_make   = request.form.get("vehicle_make")
            policy.vehicle_model  = request.form.get("vehicle_model")
            policy.insured_value  = float(request.form.get("insured_value") or 0) or None
            policy.beneficiary    = request.form.get("beneficiary")
            policy.coverage_details = request.form.get("coverage_details")
            policy.payment_code   = request.form.get("payment_code")
            policy.start_date     = datetime.strptime(sd,"%Y-%m-%d").date() if sd else None
            policy.expiration_date= datetime.strptime(ed,"%Y-%m-%d").date() if ed else None
            policy.status         = m.PolicyStatus[request.form.get("status","ACTIVE")]
            policy.agent          = request.form.get("agent", "").strip() or None
            policy.payment_frequency = m.PaymentFrequency[request.form.get("payment_frequency","ANNUAL")] if request.form.get("payment_frequency") else m.PaymentFrequency.ANNUAL
            policy.hal_summary    = None   # clear cache
            policy.updated_date   = datetime.now()

            # Rebuild pending installments when premium or frequency changes
            unpaid = db.query(m.Payment).filter(
                m.Payment.policy_id == policy.id,
                m.Payment.status.in_([m.PaymentStatus.PENDING, m.PaymentStatus.OVERDUE])
            ).all()
            if prem > 0 and unpaid:
                # Check if we need to rebuild (premium or frequency changed)
                expected_n, expected_amt = {
                    m.PaymentFrequency.ANNUAL:    (1,  prem),
                    m.PaymentFrequency.SEMI:      (2,  round(prem/2, 2)),
                    m.PaymentFrequency.QUARTERLY: (4,  round(prem/4, 2)),
                    m.PaymentFrequency.MONTHLY:   (12, round(prem/12, 2)),
                }.get(policy.payment_frequency, (1, prem))
                actual_n = len(unpaid)
                amounts_match = all(abs((p.amount or 0) - expected_amt) < 0.02 for p in unpaid)
                if actual_n != expected_n or not amounts_match:
                    # Frequency or premium changed — delete pending and recreate
                    for p in unpaid:
                        db.delete(p)
                    db.flush()
                    n, amt = _create_installments(db, policy, prem)
                    freq_label = policy.payment_frequency.value if policy.payment_frequency else ""
                    db.commit()
                    flash(f"✅ Συμβόλαιο ενημερώθηκε. Αναδημιουργήθηκαν {n} δόσεις (€{amt:.2f} {freq_label}).", "success")
                else:
                    # Same count & amounts — just update due dates if start_date changed
                    new_base = policy.start_date or policy.expiration_date
                    freq_steps = {
                        m.PaymentFrequency.ANNUAL: 12, m.PaymentFrequency.SEMI: 6,
                        m.PaymentFrequency.QUARTERLY: 3, m.PaymentFrequency.MONTHLY: 1,
                    }
                    step = freq_steps.get(policy.payment_frequency, 12)
                    for i, pay in enumerate(sorted(unpaid, key=lambda p: p.due_date or date.today())):
                        if new_base:
                            pay.due_date = _add_months(new_base, step * i)
                        pay.amount = expected_amt
                    db.commit()
                    flash(f"✅ Συμβόλαιο ενημερώθηκε ({actual_n} δόσεις ενημερώθηκαν).", "success")
            elif prem > 0 and not unpaid:
                # No pending payments yet — create from scratch
                n, amt = _create_installments(db, policy, prem)
                db.commit()
                flash(f"✅ Συμβόλαιο ενημερώθηκε. Δημιουργήθηκαν {n} δόσεις (€{amt:.2f}).", "success")
            else:
                db.commit()
                flash("✅ Συμβόλαιο ενημερώθηκε.", "success")
            return redirect(url_for("agent_client_detail", client_id=client.id))
        except Exception as e:
            db.rollback(); flash(f"Σφάλμα: {e}", "danger")
        finally:
            db.close()
    provs = [m.ser_provider(p) for p in providers]
    pc = m.ser_client(client)
    pp = m.ser_policy(policy)
    db.close()
    return render_template("agent/policy_form.html", client=pc, policy=pp,
                           sectors=[{"name":s.name,"value":s.value} for s in m.PolicySector],
                           providers=provs,
                           freq=[{"name":f.name,"value":f.value} for f in m.PaymentFrequency],
                           action="edit")

@app.route("/agent/policy/<int:policy_id>/delete", methods=["POST"])
@agent_required
def agent_delete_policy(policy_id):
    db = m.get_session()
    policy = db.query(m.Policy).get(policy_id)
    if policy:
        client_id = policy.client_id
        db.delete(policy); db.commit()
        flash("🗑 Συμβόλαιο διαγράφηκε.", "info")
        return redirect(url_for("agent_client_detail", client_id=client_id))
    db.close(); abort(404)

# HAL — Agent: explain policy
@app.route("/agent/policy/<int:policy_id>/hal", methods=["GET","POST"])
@agent_required
def agent_hal_policy(policy_id):
    db = m.get_session()
    policy = db.query(m.Policy).get(policy_id)
    if not policy:
        abort(404)
    client = db.query(m.Client).get(policy.client_id)
    explanation = policy.hal_summary
    if request.method == "POST" or not explanation:
        pol_data = {
            "policy_number": policy.policy_number, "type": policy.policy_type,
            "sector": policy.sector.value if policy.sector else "",
            "provider": policy.provider, "premium": policy.premium,
            "start": str(policy.start_date), "expiry": str(policy.expiration_date),
            "commission_rate": policy.commission_rate,
            "coverage": policy.coverage_details, "beneficiary": policy.beneficiary,
            "payment_frequency": policy.payment_frequency.value if policy.payment_frequency else ""
        }
        explanation = hal.explain_policy(pol_data, client.name if client else "")
        policy.hal_summary = explanation
        db.commit()
    db.close()
    return jsonify({"explanation": explanation})

# HAL — Agent: upsell analysis
@app.route("/agent/client/<int:client_id>/hal/upsell")
@agent_required
def agent_hal_upsell(client_id):
    db = m.get_session()
    client = db.query(m.Client).get(client_id)
    policies = db.query(m.Policy).filter_by(client_id=client_id, status=m.PolicyStatus.ACTIVE).all()
    client_data = {"name": client.name, "profession": client.profession,
                   "city": client.city, "company": client.company_name}
    pol_list = [{"type": p.policy_type, "sector": p.sector.value if p.sector else "",
                  "premium": p.premium, "provider": p.provider} for p in policies]
    result = hal.upsell_opportunities(client_data, pol_list)
    db.close()
    return jsonify({"analysis": result})

# HAL — Agent: chat
@app.route("/agent/hal/chat", methods=["POST"])
@agent_required
def agent_hal_chat():
    data = request.json or {}
    messages = data.get("messages", [])
    context = data.get("context", "")
    response = hal.chat(messages, context)
    return jsonify({"response": response})

# Agent: Renewals (Ληξιάριο)
@app.route("/agent/renewals")
@agent_required
def agent_renewals():
    db = m.get_session()
    today = date.today()
    days       = request.args.get("days", 30, type=int)
    sector_f   = request.args.get("sector", "")
    provider_f = request.args.get("provider", "")
    month_f    = request.args.get("month", "", )
    year_f     = request.args.get("year", "")
    agent_f    = request.args.get("agent", "")
    try:
        scope = get_agent_scope()
        if scope and not agent_f:
            agent_f = scope
        all_providers = [r[0] for r in db.query(m.Policy.provider).filter(m.Policy.provider != None).distinct().order_by(m.Policy.provider).all()]
        all_agents    = [r[0] for r in db.query(m.Policy.agent).filter(m.Policy.agent != None).distinct().order_by(m.Policy.agent).all()]
        # Build date range
        if month_f and year_f:
            from calendar import monthrange
            _, last_day = monthrange(int(year_f), int(month_f))
            start_dt = date(int(year_f), int(month_f), 1)
            end_dt   = date(int(year_f), int(month_f), last_day)
        else:
            start_dt = today
            end_dt   = today + timedelta(days=days)
        q = db.query(m.Policy).filter(
            m.Policy.expiration_date.between(start_dt, end_dt),
            m.Policy.status == m.PolicyStatus.ACTIVE
        )
        if sector_f:
            try: q = q.filter(m.Policy.sector == m.PolicySector[sector_f])
            except KeyError: pass
        if provider_f:
            q = q.filter(m.Policy.provider == provider_f)
        if agent_f:
            q = q.filter(m.Policy.agent == agent_f)
        policies = q.order_by(m.Policy.expiration_date).all()
        renewals = []
        for p in policies:
            c = db.query(m.Client).get(p.client_id)
            pending_pay = db.query(m.Payment).filter_by(policy_id=p.id, status=m.PaymentStatus.PENDING).first()
            queued = db.query(m.EmailQueue).filter_by(policy_id=p.id, status=m.EmailStatus.QUEUED).first()
            sent   = db.query(m.EmailQueue).filter_by(policy_id=p.id, status=m.EmailStatus.SENT).first()
            renewals.append({
                "policy": m.ser_policy(p),
                "client": m.ser_client(c),
                "days_left": (p.expiration_date - today).days,
                "pending_pay": m.ser_payment(pending_pay) if pending_pay else None,
                "queued": bool(queued), "sent": bool(sent)
            })
        month_names = ["","Ιαν","Φεβ","Μαρ","Απρ","Μαι","Ιουν","Ιουλ","Αυγ","Σεπ","Οκτ","Νοε","Δεκ"]
        years = list(range(today.year - 1, today.year + 3))
        total_premium = sum((r["policy"]["premium"] or 0) for r in renewals)
        return render_template("agent/renewals.html", renewals=renewals, days=days, today=today,
                               sector_f=sector_f, provider_f=provider_f, agent_f=agent_f,
                               month_f=month_f, year_f=year_f, sectors=m.PolicySector,
                               all_providers=all_providers, all_agents=all_agents,
                               month_names=month_names, months=range(1,13), years=years,
                               total_premium=total_premium)
    finally:
        db.close()

@app.route("/agent/renewals/hal-draft/<int:policy_id>", methods=["POST"])
@agent_required
def agent_hal_renewal_draft(policy_id):
    db = m.get_session()
    policy = db.query(m.Policy).get(policy_id)
    if not policy:
        db.close(); return jsonify({"error": "Not found"}), 404
    client = db.query(m.Client).get(policy.client_id)
    today  = date.today()
    days_left = (policy.expiration_date - today).days if policy.expiration_date else 30
    client_data = {"name": client.name, "email": client.email}
    policy_data = {
        "policy_type": policy.policy_type, "provider": policy.provider,
        "policy_number": policy.policy_number, "premium": policy.premium,
        "expiration_date": str(policy.expiration_date)
    }
    draft = hal.draft_renewal_email(client_data, policy_data, days_left)
    # Queue it
    pending_pay = db.query(m.Payment).filter_by(policy_id=policy.id, status=m.PaymentStatus.PENDING).first()
    if client.email and pending_pay:
        eq = m.EmailQueue(
            client_id=client.id, policy_id=policy.id,
            payment_id=pending_pay.id, recipient_email=client.email,
            subject=draft.get("subject","Ανανέωση Συμβολαίου"),
            body_html=draft.get("body_html",""), status=m.EmailStatus.QUEUED
        )
        db.add(eq); db.commit()
    db.close()
    return jsonify(draft)

@app.route("/agent/email-queue")
@agent_required
def agent_email_queue():
    db = m.get_session()
    scope = get_agent_scope()
    q = db.query(m.EmailQueue).order_by(m.EmailQueue.created_date.desc())
    if scope is not None:
        # Scoped agent: only emails for policies that belong to them
        q = q.join(m.Policy, m.EmailQueue.policy_id == m.Policy.id)\
              .filter(m.Policy.agent == scope)
    emails_raw = q.limit(100).all()
    data = []
    for e in emails_raw:
        c = db.query(m.Client).get(e.client_id)
        p = db.query(m.Policy).get(e.policy_id)
        data.append({"eq": m.ser_email_queue(e),
                     "client_name": c.name if c else "—",
                     "policy_type": p.policy_type if p else "—"})
    db.close()
    return render_template("agent/email_queue.html", emails=data)

@app.route("/agent/email/<int:eq_id>/send", methods=["POST"])
@agent_required
def agent_send_email(eq_id):
    db = m.get_session()
    eq = db.query(m.EmailQueue).get(eq_id)
    if not eq:
        db.close(); abort(404)
    brevo_key = os.getenv("BREVO_API_KEY","")
    if not brevo_key:
        flash("⚠️ BREVO_API_KEY δεν έχει οριστεί.", "warning")
        db.close()
        return redirect(url_for("agent_email_queue"))
    try:
        ok, err_msg = _brevo_send(eq.recipient_email, eq.recipient_email, eq.subject, eq.body_html)
        if ok:
            eq.status = m.EmailStatus.SENT
            eq.sent_at = datetime.now()
            flash(f"✅ Email στάλθηκε στο {eq.recipient_email}", "success")
        else:
            eq.status = m.EmailStatus.FAILED
            eq.error_message = err_msg[:500]
            flash(f"❌ Αποτυχία: {err_msg[:100]}", "danger")
        db.commit()
    except Exception as e:
        flash(f"Σφάλμα: {e}", "danger")
    finally:
        db.close()
    return redirect(url_for("agent_email_queue"))

# Agent: Commissions
@app.route("/agent/commissions")
@agent_required
def agent_commissions():
    db = m.get_session()
    try:
        scope = get_agent_scope()
        q_pol = db.query(m.Policy).filter_by(status=m.PolicyStatus.ACTIVE)
        if scope:
            q_pol = q_pol.filter(m.Policy.agent == scope)
        policies = q_pol.all()
        by_client = {}
        for p in policies:
            cid = p.client_id
            if cid not in by_client:
                c = db.query(m.Client).get(cid)
                by_client[cid] = {"client": c, "policies": [], "total_premium": 0, "total_commission": 0}
            comm = p.commission_amount or (p.premium or 0) * (p.commission_rate or 0) / 100
            by_client[cid]["policies"].append(p)
            by_client[cid]["total_premium"] += (p.premium or 0)
            by_client[cid]["total_commission"] += comm
        # Sort by commission desc
        sorted_data = sorted(by_client.values(), key=lambda x: x["total_commission"], reverse=True)
        # Serialize client objects in sorted_data
        for row in sorted_data:
            row["client"] = m.ser_client(row["client"])
            row["policies"] = [m.ser_policy(p) for p in row["policies"]]
        # By sector
        by_sector = {}
        for p in policies:
            sec = p.sector.value if p.sector else "Άλλο"
            if sec not in by_sector:
                by_sector[sec] = {"count": 0, "premium": 0, "commission": 0}
            by_sector[sec]["count"] += 1
            by_sector[sec]["premium"] += (p.premium or 0)
            by_sector[sec]["commission"] += (p.commission_amount or (p.premium or 0)*(p.commission_rate or 0)/100)
        total_premium = sum(p.premium or 0 for p in policies)
        total_commission = sum((p.commission_amount or (p.premium or 0)*(p.commission_rate or 0)/100) for p in policies)
        return render_template("agent/commissions.html", clients_data=sorted_data,
                               by_sector=by_sector, total_premium=total_premium,
                               total_commission=total_commission)
    finally:
        db.close()

# Agent: Tickets
@app.route("/agent/tickets")
@agent_required
def agent_tickets():
    db = m.get_session()
    scope = get_agent_scope()
    status_f = request.args.get("status","open")
    try:
        q = db.query(m.Ticket)
        if status_f == "open":
            q = q.filter(m.Ticket.status.in_([m.TicketStatus.OPEN, m.TicketStatus.IN_PROCESS]))
        elif status_f == "resolved":
            q = q.filter(m.Ticket.status.in_([m.TicketStatus.RESOLVED, m.TicketStatus.CLOSED]))
        if scope is not None:
            # Scoped agent: tickets where the linked policy belongs to them,
            # OR (no policy_id) where the client has at least one policy belonging to them.
            scoped_client_ids = db.query(m.Policy.client_id)\
                                   .filter(m.Policy.agent == scope)\
                                   .distinct().subquery()
            q = q.filter(m.Ticket.client_id.in_(scoped_client_ids))
        tickets = q.order_by(m.Ticket.created_date.desc()).all()
        data = []
        for t in tickets:
            c = db.query(m.Client).get(t.client_id)
            doc = db.query(m.Document).get(t.document_id) if t.document_id else None
            data.append({"ticket": m.ser_ticket(t), "client": m.ser_client(c), "document": m.ser_document(doc)})
        return render_template("agent/tickets.html", tickets=data, status_f=status_f)
    finally:
        db.close()

@app.route("/agent/ticket/add", methods=["GET","POST"])
@agent_required
def agent_add_ticket():
    db = m.get_session()
    clients = db.query(m.Client).order_by(m.Client.name).all()
    if request.method == "POST":
        try:
            cid = int(request.form.get("client_id"))
            pid_raw = request.form.get("policy_id")
            ticket = m.Ticket(
                client_id=cid,
                policy_id=int(pid_raw) if pid_raw else None,
                subject=request.form.get("subject"),
                description=request.form.get("description"),
                priority=m.TicketPriority[request.form.get("priority","MEDIUM")],
                status=m.TicketStatus.OPEN,
                created_by="agent"
            )
            db.add(ticket); db.commit()
            flash("✅ Ticket δημιουργήθηκε.", "success")
            db.close()
            return redirect(url_for("agent_tickets"))
        except Exception as e:
            db.rollback(); flash(f"Σφάλμα: {e}", "danger")
    db.close()
    clients_d = [m.ser_client(c) for c in clients]
    db.close()
    return render_template("agent/ticket_form.html", clients=clients_d,
                           priorities=[{"name":p.name,"value":p.value} for p in m.TicketPriority])

@app.route("/agent/ticket/<int:ticket_id>/update", methods=["POST"])
@agent_required
def agent_update_ticket(ticket_id):
    db = m.get_session()
    ticket = db.query(m.Ticket).get(ticket_id)
    if ticket:
        new_status = request.form.get("status")
        ticket.status = m.TicketStatus[new_status]
        ticket.resolution = request.form.get("resolution","")
        ticket.updated_date = datetime.now()
        if new_status in ("RESOLVED","CLOSED"):
            ticket.resolved_date = datetime.now()
        db.commit()
        flash("✅ Ticket ενημερώθηκε.", "success")
    db.close()
    return redirect(url_for("agent_tickets"))

# Agent: Claims
@app.route("/agent/client/<int:client_id>/claim/add", methods=["POST"])
@agent_required
def agent_add_claim(client_id):
    db = m.get_session()
    try:
        id_raw = request.form.get("incident_date")
        claim = m.Claim(
            policy_id=int(request.form.get("policy_id")),
            claim_number=request.form.get("claim_number"),
            description=request.form.get("description"),
            claim_amount=float(request.form.get("claim_amount") or 0) or None,
            incident_date=datetime.strptime(id_raw,"%Y-%m-%d").date() if id_raw else None,
            reported_date=date.today(),
            status=m.ClaimStatus.OPEN
        )
        db.add(claim); db.commit()
        flash("✅ Αξίωση καταχωρήθηκε.", "success")
    except Exception as e:
        db.rollback(); flash(f"Σφάλμα: {e}", "danger")
    finally:
        db.close()
    return redirect(url_for("agent_client_detail", client_id=client_id))

# Agent: Document upload
@app.route("/agent/client/<int:client_id>/upload", methods=["POST"])
@agent_required
def agent_upload_document(client_id):
    db = m.get_session()
    if "file" not in request.files:
        flash("Δεν επιλέχθηκε αρχείο.", "warning")
        return redirect(url_for("agent_client_detail", client_id=client_id))
    file = request.files["file"]
    if file and allowed_file(file.filename):
        data = file.read()
        ext  = file.filename.rsplit(".",1)[1].lower()
        doc  = m.Document(
            client_id=client_id,
            policy_id=int(request.form.get("policy_id")) if request.form.get("policy_id") else None,
            filename=secure_filename(file.filename),
            original_filename=file.filename,
            file_type=ext, file_data=data, file_size=len(data),
            uploaded_by="agent", is_policy_doc=bool(request.form.get("is_policy_doc"))
        )
        db.add(doc); db.commit()
        flash(f"✅ Αρχείο {file.filename} ανέβηκε.", "success")
    else:
        flash("Μη αποδεκτός τύπος αρχείου.", "danger")
    db.close()
    return redirect(url_for("agent_client_detail", client_id=client_id))

@app.route("/agent/document/<int:doc_id>/download")
@login_required
def download_document(doc_id):
    db = m.get_session()
    doc = db.query(m.Document).get(doc_id)
    if not doc:
        db.close(); abort(404)
    # Clients can only download their own docs
    if session.get("role") == "client":
        if doc.client_id != session.get("client_id"):
            db.close(); abort(403)
    data = io.BytesIO(doc.file_data)
    fname = doc.original_filename or doc.filename
    db.close()
    return send_file(data, download_name=fname, as_attachment=True)

@app.route("/agent/document/<int:doc_id>/delete", methods=["POST"])
@agent_required
def agent_delete_document(doc_id):
    db = m.get_session()
    doc = db.query(m.Document).get(doc_id)
    if doc:
        client_id = doc.client_id
        db.delete(doc); db.commit()
        db.close()
        return redirect(url_for("agent_client_detail", client_id=client_id))
    db.close(); abort(404)

# Agent: Payment management
@app.route("/agent/payments")
@agent_required
def agent_payments():
    db = m.get_session()
    status_f   = request.args.get("status","all")
    search     = request.args.get("q", "").strip()
    sector_f   = request.args.get("sector", "")
    provider_f = request.args.get("provider", "")
    agent_f    = request.args.get("agent", "")
    month_f    = request.args.get("month", "")
    year_f     = request.args.get("year", "")
    scope = get_agent_scope()
    try:
        all_providers = [r[0] for r in db.query(m.Policy.provider).filter(m.Policy.provider != None).distinct().order_by(m.Policy.provider).all()]
        all_agents    = [r[0] for r in db.query(m.Policy.agent).filter(m.Policy.agent != None).distinct().order_by(m.Policy.agent).all()]

        q = db.query(m.Payment).join(m.Policy).join(m.Client)
        if scope and not agent_f:
            agent_f = scope
        if scope:
            q = q.filter(m.Policy.agent == scope)
        if status_f != "all":
            try:
                q = q.filter(m.Payment.status == m.PaymentStatus[status_f.upper()])
            except KeyError:
                pass
        if search:
            q = q.filter(
                (m.Client.name.ilike(f"%{search}%")) |
                (m.Client.email.ilike(f"%{search}%")) |
                (m.Client.phone.ilike(f"%{search}%")) |
                (m.Client.tax_id.ilike(f"%{search}%")) |
                (m.Policy.policy_number.ilike(f"%{search}%"))
            )
        if sector_f:
            try: q = q.filter(m.Policy.sector == m.PolicySector[sector_f])
            except KeyError: pass
        if provider_f:
            q = q.filter(m.Policy.provider == provider_f)
        if agent_f:
            q = q.filter(m.Policy.agent == agent_f)

        payments = q.order_by(m.Payment.due_date.desc()).all()

        # Month/Year filter on the policy's expiration date — same as the
        # equivalent filter on the Πελάτες page — applied in Python since
        # it depends on the related Policy row, not a plain Payment column.
        if month_f or year_f:
            filtered = []
            for pay in payments:
                pol = db.query(m.Policy).get(pay.policy_id)
                if not pol or not pol.expiration_date:
                    continue
                if month_f and year_f:
                    if pol.expiration_date.month == int(month_f) and pol.expiration_date.year == int(year_f):
                        filtered.append(pay)
                elif month_f:
                    if pol.expiration_date.month == int(month_f):
                        filtered.append(pay)
                elif year_f:
                    if pol.expiration_date.year == int(year_f):
                        filtered.append(pay)
            payments = filtered

        payments = payments[:200]

        data = []
        for pay in payments:
            pol = db.query(m.Policy).get(pay.policy_id)
            c   = db.query(m.Client).get(pol.client_id) if pol else None
            # Serialize to plain dicts — avoids DetachedInstanceError in templates
            data.append({
                "pay_id":       pay.id,
                "pay_amount":   pay.amount or 0,
                "pay_due":      pay.due_date.strftime("%d/%m/%Y") if pay.due_date else "—",
                "pay_date":     pay.payment_date.strftime("%d/%m/%Y") if pay.payment_date else None,
                "pay_status":   pay.status.value if pay.status else "PENDING",
                "pay_receipt":  pay.receipt_num or "",
                "pol_id":       pol.id if pol else None,
                "pol_type":     pol.policy_type if pol else "—",
                "pol_number":   pol.policy_number if pol else "",
                "pol_provider": pol.provider if pol else "—",
                "pol_sector":   pol.sector.value if pol and pol.sector else "—",
                "pol_agent":    pol.agent if pol else "—",
                "pol_rf":       pol.payment_code if pol else "",
                "pol_start":    pol.start_date.strftime("%d/%m/%Y") if pol and pol.start_date else "—",
                "pol_expiry":   pol.expiration_date.strftime("%d/%m/%Y") if pol and pol.expiration_date else "—",
                "pol_plate":    pol.license_plate or "",
                "pol_n_inst":   _pol_installment_count(pol),
                "pay_inst_idx": _pay_installment_index(pay, pol, db),
                "client_id":    c.id if c else None,
                "client_name":  c.name if c else "—",
                "client_email": c.email if c else "",
                "client_phone": c.phone if c else "",
            })
        month_names = ["","Ιαν","Φεβ","Μαρ","Απρ","Μαι","Ιουν","Ιουλ","Αυγ","Σεπ","Οκτ","Νοε","Δεκ"]
        years = list(range(date.today().year - 1, date.today().year + 3))
        return render_template("agent/payments.html", payments=data, status_f=status_f,
                               search=search, sector_f=sector_f, provider_f=provider_f,
                               agent_f=agent_f, month_f=month_f, year_f=year_f,
                               sectors=m.PolicySector, all_providers=all_providers,
                               all_agents=all_agents, month_names=month_names,
                               months=range(1,13), years=years)
    finally:
        db.close()

@app.route("/agent/payment/<int:pay_id>/update", methods=["POST"])
@agent_required
def agent_update_payment(pay_id):
    db = m.get_session()
    pay = db.query(m.Payment).get(pay_id)
    if pay:
        pay.status = m.PaymentStatus[request.form.get("status","PENDING").upper()]
        if pay.status == m.PaymentStatus.PAID:
            pay.payment_date = date.today()
        db.commit()
        flash("✅ Πληρωμή ενημερώθηκε.", "success")
    db.close()
    return redirect(request.referrer or url_for("agent_payments"))

# ══════════════════════════════════════════════════════════════════════════════
# PORTAL 2 — CLIENT
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/client/dashboard")
@client_required
def client_dashboard():
    if session.get("role") in ("agent","backoffice"):
        return redirect(url_for("agent_dashboard"))
    client_id = session.get("client_id")
    if not client_id:
        flash("Πρόσβαση απορρίφθηκε.", "danger")
        return redirect(url_for("logout"))
    db = m.get_session()
    try:
        client = db.query(m.Client).get(client_id)
        if not client:
            return redirect(url_for("logout"))
        policies = db.query(m.Policy).filter_by(client_id=client_id).all()
        today = date.today()
        active = [p for p in policies if p.status == m.PolicyStatus.ACTIVE]
        # Next payment
        next_payment = None
        for p in active:
            pay = db.query(m.Payment).filter_by(policy_id=p.id, status=m.PaymentStatus.PENDING)\
                    .order_by(m.Payment.due_date).first()
            if pay:
                if not next_payment or pay.due_date < next_payment["due_date"]:
                    next_payment = {"amount": pay.amount, "due_date": pay.due_date,
                                    "policy": p.policy_type, "days": (pay.due_date - today).days}
        # Expiring soon
        expiring = [p for p in active if p.expiration_date and (p.expiration_date - today).days <= 30]

        def _ser_policy_with_days(p):
            d = m.ser_policy(p)
            d["days_left"] = (p.expiration_date - today).days if p.expiration_date else None
            return d

        documents = db.query(m.Document).filter_by(client_id=client_id).order_by(m.Document.uploaded_date.desc()).limit(5).all()
        return render_template("client/dashboard.html",
                               client=m.ser_client(client),
                               policies=[_ser_policy_with_days(p) for p in active],
                               next_payment=next_payment,
                               expiring=[_ser_policy_with_days(p) for p in expiring],
                               documents=[m.ser_document(d) for d in documents],
                               today=today.strftime("%Y-%m-%d"))
    finally:
        db.close()

@app.route("/client/policies")
@client_required
def client_policies():
    if session.get("role") in ("agent","backoffice"):
        return redirect(url_for("agent_clients"))
    db = m.get_session()
    client_id = session.get("client_id")
    try:
        client   = db.query(m.Client).get(client_id)
        policies = db.query(m.Policy).filter_by(client_id=client_id).order_by(m.Policy.expiration_date).all()
        today = date.today()
        pol_data = []
        for p in policies:
            payments = db.query(m.Payment).filter_by(policy_id=p.id).order_by(m.Payment.due_date).all()
            next_pay = next((pay for pay in payments if pay.status == m.PaymentStatus.PENDING), None)
            exp = p.expiration_date
            pol_data.append({"policy": m.ser_policy(p),
                             "next_pay": m.ser_payment(next_pay) if next_pay else None,
                             "days_left": (exp - today).days if exp else None,
                             "payments": [m.ser_payment(pay) for pay in payments]})
        return render_template("client/policies.html", client=m.ser_client(client),
                               pol_data=pol_data, today=today.strftime("%Y-%m-%d"))
    finally:
        db.close()

@app.route("/client/documents", methods=["GET","POST"])
@client_required
def client_documents():
    if session.get("role") in ("agent","backoffice"):
        return redirect(url_for("agent_clients"))
    db = m.get_session()
    client_id = session.get("client_id")
    client = db.query(m.Client).get(client_id)
    if request.method == "POST":
        if "file" in request.files:
            file = request.files["file"]
            if file and allowed_file(file.filename):
                data = file.read()
                ext  = file.filename.rsplit(".",1)[1].lower()
                doc  = m.Document(
                    client_id=client_id,
                    policy_id=int(request.form.get("policy_id")) if request.form.get("policy_id") else None,
                    filename=secure_filename(file.filename),
                    original_filename=file.filename,
                    file_type=ext, file_data=data, file_size=len(data),
                    uploaded_by=session.get("user_name","client")
                )
                db.add(doc); db.commit()
                flash("✅ Αρχείο ανέβηκε.", "success")
    policies  = db.query(m.Policy).filter_by(client_id=client_id).all()
    documents = db.query(m.Document).filter_by(client_id=client_id).order_by(m.Document.uploaded_date.desc()).all()
    db.close()
    data_d = {"client": m.ser_client(client),
             "policies": [m.ser_policy(p) for p in policies],
             "documents": [m.ser_document(d) for d in documents]}
    db.close()
    return render_template("client/documents.html", **data_d)

@app.route("/client/hal", methods=["GET","POST"])
@client_required
def client_hal():
    if session.get("role") in ("agent","backoffice"):
        return redirect(url_for("agent_dashboard"))
    db = m.get_session()
    client_id = session.get("client_id")
    client = db.query(m.Client).get(client_id)
    policies = db.query(m.Policy).filter_by(client_id=client_id, status=m.PolicyStatus.ACTIVE).all()
    db.close()
    context = _build_hal_context(client, policies)
    return render_template("client/hal.html", client=m.ser_client(client),
                           policies=[m.ser_policy(p) for p in policies], context=context)


def _build_hal_context(client, policies) -> str:
    """Build a detailed, real-data context string for HAL, one block per policy.
    Excludes internal commission/financial fields — those are not for client eyes."""
    if not client:
        return ""
    lines = [f"Πελάτης: {client.name}"]
    if not policies:
        lines.append("Ο πελάτης δεν έχει αυτή τη στιγμή ενεργά συμβόλαια.")
        return "\n".join(lines)
    lines.append(f"Έχει {len(policies)} ενεργό/ά συμβόλαιο/α:")
    for i, p in enumerate(policies, 1):
        d = m.ser_policy(p)
        block = [
            f"\n--- Συμβόλαιο {i} ---",
            f"Τύπος: {d['policy_type']} | Τομέας: {d['sector_name']} | Πάροχος: {d['provider']}",
            f"Αριθμός συμβολαίου: {d['policy_number'] or '—'}",
            f"Ασφάλιστρο: €{d['premium']:.2f} | Συχνότητα πληρωμής: {d['payment_frequency'] or '—'}",
            f"Έναρξη: {d['start_date'] or '—'} | Λήξη: {d['expiration_date'] or '—'}",
        ]
        if d['license_plate']:
            block.append(f"Όχημα: {d['vehicle_make']} {d['vehicle_model']} | Πινακίδα: {d['license_plate']}")
        if d['insured_value']:
            block.append(f"Ασφαλιζόμενη αξία: €{d['insured_value']:.2f}")
        if d['beneficiary']:
            block.append(f"Δικαιούχος: {d['beneficiary']}")
        if d['coverage_details']:
            block.append(f"Λεπτομέρειες κάλυψης: {d['coverage_details']}")
        if d['hal_summary']:
            block.append(f"Σύνοψη: {d['hal_summary']}")
        lines.extend(block)
    return "\n".join(lines)

@app.route("/client/hal/chat", methods=["POST"])
@client_required
def client_hal_chat():
    data = request.json or {}
    messages = data.get("messages", [])
    context  = data.get("context", "")
    response = hal.chat(messages, context)
    return jsonify({"response": response})

# ══════════════════════════════════════════════════════════════════════════════
# PORTAL 3 — BACK OFFICE
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/backoffice/dashboard")
@backoffice_required
def backoffice_dashboard():
    db = m.get_session()
    try:
        today = date.today()
        # Revenue & commissions
        all_active = db.query(m.Policy).filter_by(status=m.PolicyStatus.ACTIVE).all()
        total_premium    = sum((p.premium or 0) for p in all_active)
        total_commission = sum((p.commission_amount or (p.premium or 0)*(p.commission_rate or 0)/100) for p in all_active)
        total_policies   = len(all_active)
        total_clients    = db.query(m.Client).count()
        # By sector
        by_sector = {}
        for p in all_active:
            sec = p.sector.value if p.sector else "Άλλο"
            if sec not in by_sector:
                by_sector[sec] = {"count": 0, "premium": 0, "commission": 0}
            by_sector[sec]["count"] += 1
            by_sector[sec]["premium"] += (p.premium or 0)
            by_sector[sec]["commission"] += (p.commission_amount or (p.premium or 0)*(p.commission_rate or 0)/100)
        # By provider
        by_provider = {}
        for p in all_active:
            prov = p.provider or "Άγνωστος"
            if prov not in by_provider:
                by_provider[prov] = {"count": 0, "premium": 0, "commission": 0}
            by_provider[prov]["count"] += 1
            by_provider[prov]["premium"] += (p.premium or 0)
            by_provider[prov]["commission"] += (p.commission_amount or (p.premium or 0)*(p.commission_rate or 0)/100)
        by_provider_sorted = dict(sorted(by_provider.items(), key=lambda x: x[1]["commission"], reverse=True))
        # Pending commissions from statements
        pending_commissions = db.query(m.CommissionStatement).filter_by(paid=False).all()
        pending_comm_total  = sum((s.commission_amount or 0) for s in pending_commissions)
        # Open tickets
        open_tickets = db.query(m.Ticket).filter(
            m.Ticket.status.in_([m.TicketStatus.OPEN, m.TicketStatus.IN_PROCESS])
        ).count()
        # Lixiario this month
        this_month_lix = db.query(m.LixiariaEntry).filter_by(
            expiry_month=today.month, expiry_year=today.year, renewal_sent=False
        ).count()
        stats = {
            "total_premium": total_premium, "total_commission": total_commission,
            "total_policies": total_policies, "total_clients": total_clients,
            "pending_comm_total": pending_comm_total, "open_tickets": open_tickets,
            "this_month_lix": this_month_lix
        }
        return render_template("backoffice/dashboard.html", stats=stats,
                               by_sector=by_sector, by_provider=by_provider_sorted)
    finally:
        db.close()

@app.route("/backoffice/providers")
@backoffice_required
def backoffice_providers():
    db = m.get_session()
    providers = db.query(m.Provider).order_by(m.Provider.name).all()
    data = []
    for prov in providers:
        policy_count = db.query(m.Policy).filter_by(provider=prov.name, status=m.PolicyStatus.ACTIVE).count()
        total_prem   = db.query(m.Policy).filter_by(provider=prov.name, status=m.PolicyStatus.ACTIVE).all()
        premium      = sum((p.premium or 0) for p in total_prem)
        commission   = sum((p.commission_amount or (p.premium or 0)*(p.commission_rate or 0)/100) for p in total_prem)
        statements   = db.query(m.CommissionStatement).filter_by(provider_id=prov.id).count()
        unpaid       = db.query(m.CommissionStatement).filter_by(provider_id=prov.id, paid=False).all()
        unpaid_total = sum((s.commission_amount or 0) for s in unpaid)
        data.append({
            "provider": prov, "policy_count": policy_count, "premium": premium,
            "commission": commission, "statements": statements, "unpaid_total": unpaid_total
        })
    db.close()
    data_d = [{"provider": m.ser_provider(r["provider"]), "policy_count": r["policy_count"],
               "premium": r["premium"], "commission": r["commission"],
               "statements": r["statements"], "unpaid_total": r["unpaid_total"]} for r in data]
    db.close()
    return render_template("backoffice/providers.html", providers=data_d)

@app.route("/backoffice/provider/add", methods=["GET","POST"])
@backoffice_required
def backoffice_add_provider():
    if request.method == "POST":
        db = m.get_session()
        try:
            prov = m.Provider(
                name=request.form.get("name"), short_name=request.form.get("short_name"),
                sector=request.form.get("sector"), contact_person=request.form.get("contact_person"),
                email=request.form.get("email"), phone=request.form.get("phone"),
                website=request.form.get("website"),
                default_commission=float(request.form.get("default_commission") or 0),
                notes=request.form.get("notes"), active=True
            )
            db.add(prov); db.commit()
            flash(f"✅ Πάροχος {prov.name} προστέθηκε.", "success")
            return redirect(url_for("backoffice_providers"))
        except Exception as e:
            db.rollback(); flash(f"Σφάλμα: {e}", "danger")
        finally:
            db.close()
    return render_template("backoffice/provider_form.html", provider=None)

@app.route("/backoffice/commissions")
@backoffice_required
def backoffice_commissions():
    db = m.get_session()
    try:
        providers = db.query(m.Provider).filter_by(active=True).order_by(m.Provider.name).all()
        month_f = request.args.get("month", date.today().month, type=int)
        year_f  = request.args.get("year", date.today().year, type=int)
        statements = db.query(m.CommissionStatement).filter_by(
            period_month=month_f, period_year=year_f
        ).all()
        total_due  = sum((s.commission_amount or 0) for s in statements)
        total_paid = sum((s.commission_amount or 0) for s in statements if s.paid)
        # Enrich statements with provider name
        stmts_d = []
        for s in statements:
            sd = m.ser_commission(s)
            prov = db.query(m.Provider).get(s.provider_id) if s.provider_id else None
            sd["provider_name"] = prov.name if prov else "—"
            stmts_d.append(sd)
        return render_template("backoffice/commissions.html",
            providers=[m.ser_provider(p) for p in providers], statements=stmts_d,
            month_f=month_f, year_f=year_f,
            total_due=total_due, total_paid=total_paid,
            months=range(1,13), years=range(date.today().year-3, date.today().year+2))
    finally:
        db.close()

@app.route("/backoffice/commission/add", methods=["POST"])
@backoffice_required
def backoffice_add_commission():
    db = m.get_session()
    try:
        stmt = m.CommissionStatement(
            provider_id=int(request.form.get("provider_id")),
            period_month=int(request.form.get("period_month")),
            period_year=int(request.form.get("period_year")),
            total_premium=float(request.form.get("total_premium") or 0),
            commission_rate=float(request.form.get("commission_rate") or 0),
            commission_amount=float(request.form.get("commission_amount") or 0),
            paid=bool(request.form.get("paid")),
            notes=request.form.get("notes")
        )
        db.add(stmt); db.commit()
        flash("✅ Κατάσταση προμηθειών καταχωρήθηκε.", "success")
    except Exception as e:
        db.rollback(); flash(f"Σφάλμα: {e}", "danger")
    finally:
        db.close()
    return redirect(url_for("backoffice_commissions"))

@app.route("/backoffice/commission/<int:stmt_id>/mark-paid", methods=["POST"])
@backoffice_required
def backoffice_mark_paid(stmt_id):
    db = m.get_session()
    stmt = db.query(m.CommissionStatement).get(stmt_id)
    if stmt:
        stmt.paid = True; stmt.paid_date = date.today()
        db.commit(); flash("✅ Επισημάνθηκε ως πληρωμένη.", "success")
    db.close()
    return redirect(url_for("backoffice_commissions"))

@app.route("/backoffice/commission/hal-analysis", methods=["POST"])
@backoffice_required
def backoffice_commission_hal():
    db = m.get_session()
    month_f = request.form.get("month", type=int, default=date.today().month)
    year_f  = request.form.get("year",  type=int, default=date.today().year)
    statements = db.query(m.CommissionStatement).filter_by(
        period_month=month_f, period_year=year_f
    ).all()
    data = []
    for s in statements:
        prov = db.query(m.Provider).get(s.provider_id)
        data.append({
            "provider": prov.name if prov else "—",
            "premium": s.total_premium, "rate": s.commission_rate,
            "commission": s.commission_amount, "paid": s.paid
        })
    analysis = hal.commission_insights({"month": month_f, "year": year_f, "statements": data})
    db.close()
    return jsonify({"analysis": analysis})

# Back Office: Ληξιάριο
@app.route("/backoffice/lixiario")
@backoffice_required
def backoffice_lixiario():
    db = m.get_session()
    today = date.today()
    month_f = request.args.get("month", today.month, type=int)
    year_f  = request.args.get("year",  today.year,  type=int)
    try:
        # Get policies expiring in selected month/year
        from calendar import monthrange
        _, last_day = monthrange(year_f, month_f)
        start = date(year_f, month_f, 1)
        end   = date(year_f, month_f, last_day)
        policies = db.query(m.Policy).filter(
            m.Policy.expiration_date.between(start, end),
            m.Policy.status == m.PolicyStatus.ACTIVE
        ).order_by(m.Policy.expiration_date).all()
        entries = []
        for p in policies:
            c = db.query(m.Client).get(p.client_id)
            li = db.query(m.LixiariaEntry).filter_by(
                policy_id=p.id, expiry_month=month_f, expiry_year=year_f
            ).first()
            if not li:
                li = m.LixiariaEntry(policy_id=p.id, expiry_month=month_f, expiry_year=year_f)
                db.add(li); db.commit()
            entries.append({"policy": m.ser_policy(p), "client": m.ser_client(c),
                            "li": m.ser_lixiaria(li),
                            "days_left": (p.expiration_date - today).days})
        # Summary
        total_premium   = sum((e["policy"].get("premium") or 0) for e in entries)
        total_commission= sum(((e["policy"].get("commission_amount") or 0) or (e["policy"].get("premium") or 0)*(e["policy"].get("commission_rate") or 0)/100) for e in entries)
        sent_count      = sum(1 for e in entries if e["li"].get("renewal_sent"))
        # Month navigation
        months = [(m_num, ["","Ιαν","Φεβ","Μαρ","Απρ","Μαι","Ιουν",
                            "Ιουλ","Αυγ","Σεπ","Οκτ","Νοε","Δεκ"][m_num]) for m_num in range(1,13)]
        return render_template("backoffice/lixiario.html",
            entries=entries, month_f=month_f, year_f=year_f, months=months,
            years=range(today.year-1, today.year+3),
            total_premium=total_premium, total_commission=total_commission,
            sent_count=sent_count, today=today)
    finally:
        db.close()

@app.route("/backoffice/lixiario/hal-insights", methods=["POST"])
@backoffice_required
def backoffice_lixiario_hal():
    db = m.get_session()
    month_f = request.form.get("month", type=int, default=date.today().month)
    year_f  = request.form.get("year",  type=int, default=date.today().year)
    from calendar import monthrange
    _, last_day = monthrange(year_f, month_f)
    start = date(year_f, month_f, 1); end = date(year_f, month_f, last_day)
    policies = db.query(m.Policy).filter(
        m.Policy.expiration_date.between(start, end),
        m.Policy.status == m.PolicyStatus.ACTIVE
    ).all()
    data = []
    for p in policies:
        c = db.query(m.Client).get(p.client_id)
        data.append({"client": c.name if c else "—", "email": c.email if c else "",
                     "policy": p.policy_type, "provider": p.provider,
                     "premium": p.premium, "expiry": str(p.expiration_date)})
    insights = hal.lixiario_insights(data, month_f, year_f)
    db.close()
    return jsonify({"insights": insights})

# Back Office: Document Scanner
@app.route("/backoffice/scanner", methods=["GET","POST"])
@backoffice_required
def backoffice_scanner():
    result = None
    filename = None
    if request.method == "POST" and "file" in request.files:
        file = request.files["file"]
        if file and allowed_file(file.filename):
            filename = file.filename
            ext = filename.rsplit(".",1)[1].lower()
            content = ""
            file_data = file.read()
            if ext == "pdf":
                try:
                    import pdfplumber, io as _io
                    with pdfplumber.open(_io.BytesIO(file_data)) as pdf:
                        content = "\n".join(page.extract_text() or "" for page in pdf.pages[:5])
                except Exception:
                    content = "[PDF extraction failed — binary content]"
            else:
                try:
                    content = file_data.decode("utf-8", errors="ignore")[:3000]
                except Exception:
                    content = "[Cannot extract text from this file type]"
            doc_type = request.form.get("doc_type","policy")
            result = hal.analyze_document(content, doc_type)
    return render_template("backoffice/scanner.html", result=result, filename=filename)

# Back Office: Tickets (all)
@app.route("/backoffice/tickets")
@backoffice_required
def backoffice_tickets():
    db = m.get_session()
    tickets = db.query(m.Ticket).order_by(m.Ticket.created_date.desc()).limit(100).all()
    data = []
    for t in tickets:
        c = db.query(m.Client).get(t.client_id)
        data.append({"ticket": m.ser_ticket(t), "client": m.ser_client(c)})
    db.close()
    return render_template("backoffice/tickets.html", tickets=data,
                           statuses=[{"name":s.name,"value":s.value} for s in m.TicketStatus])

# ── API ENDPOINTS ──────────────────────────────────────────────────────────────

@app.route("/api/hal/stats")
def api_hal_stats():
    """HAL dashboard stats endpoint (for Streamlit HAL)."""
    expected = os.getenv("HAL_STATS_KEY","")
    if expected and request.args.get("key","") != expected:
        return jsonify({"error":"Unauthorized"}), 401
    db = m.get_session()
    try:
        today = date.today()
        thirty = today + timedelta(days=30)
        seven  = today + timedelta(days=7)
        return jsonify({
            "stats": {
                "total_clients":    db.query(m.Client).count(),
                "active_policies":  db.query(m.Policy).filter_by(status=m.PolicyStatus.ACTIVE).count(),
                "pending_payments": db.query(m.Payment).filter_by(status=m.PaymentStatus.PENDING).count(),
                "overdue_payments": db.query(m.Payment).filter_by(status=m.PaymentStatus.OVERDUE).count(),
                "expiring_30_days": db.query(m.Policy).filter(
                    m.Policy.expiration_date.between(today, thirty),
                    m.Policy.status==m.PolicyStatus.ACTIVE).count(),
                "expiring_7_days":  db.query(m.Policy).filter(
                    m.Policy.expiration_date.between(today, seven),
                    m.Policy.status==m.PolicyStatus.ACTIVE).count(),
            },
            "generated_at": today.strftime("%d/%m/%Y")
        })
    finally:
        db.close()

@app.route("/api/client/<int:client_id>/policies")
def api_client_policies(client_id):
    expected = os.getenv("HAL_STATS_KEY","")
    if expected and request.args.get("key","") != expected:
        return jsonify({"error":"Unauthorized"}), 401
    db = m.get_session()
    policies = db.query(m.Policy).filter_by(client_id=client_id, status=m.PolicyStatus.ACTIVE).all()
    data = [{"type": p.policy_type, "provider": p.provider, "premium": p.premium,
              "expiry": str(p.expiration_date), "sector": p.sector.value if p.sector else ""} for p in policies]
    db.close()
    return jsonify({"policies": data})


@app.route("/agent/policy/<int:policy_id>/coverage", methods=["POST"])
@agent_required
def agent_save_coverage(policy_id):
    """Save coverage details for a policy via AJAX."""
    db = m.get_session()
    policy = db.query(m.Policy).get(policy_id)
    if not policy:
        db.close(); return jsonify({"error": "Not found"}), 404
    try:
        data = request.json or {}
        policy.coverage_details = data.get("coverage_details", "")
        policy.hal_summary = None  # clear cache
        db.commit()
        db.close()
        return jsonify({"ok": True})
    except Exception as e:
        db.rollback(); db.close()
        return jsonify({"error": str(e)}), 500


@app.route("/agent/client/<int:client_id>/portal-access", methods=["POST"])
@agent_required
def agent_toggle_portal_access(client_id):
    """Give/revoke portal access for a client."""
    db = m.get_session()
    client = db.query(m.Client).get(client_id)
    if not client: db.close(); abort(404)
    try:
        action  = request.form.get("action","create")
        email   = request.form.get("email","").strip().lower()
        if action == "create" and email:
            # Check if user already exists
            existing = db.query(m.User).filter_by(email=email).first()
            if existing:
                existing.client_id = client_id
                existing.role = m.UserRole.CLIENT
                existing.must_change_password = True
                flash(f"✅ Portal user ενημερώθηκε: {email}", "success")
            else:
                db.add(m.User(
                    email=email,
                    password_hash=generate_password_hash(DEFAULT_PASSWORD),
                    role=m.UserRole.CLIENT,
                    name=client.name,
                    client_id=client_id,
                    must_change_password=True,
                    active=True,
                ))
            client.portal_access = True
            flash(f"✅ Portal access δόθηκε σε {client.name} — {email}", "success")
        elif action == "revoke":
            db.query(m.User).filter_by(client_id=client_id, role=m.UserRole.CLIENT).delete()
            client.portal_access = False
            flash(f"Portal access αφαιρέθηκε.", "warning")
        db.commit()
    except Exception as e:
        db.rollback(); flash(f"Σφάλμα: {e}", "danger")
    finally:
        db.close()
    return redirect(url_for("agent_client_detail", client_id=client_id))


# ── ΠΑΡΑΓΩΓΗ ΑΝΑ ΜΗΝΑ ───────────────────────────────────────────────────────

@app.route("/agent/production")
@agent_required
def agent_production():
    """Monthly production report."""
    db = m.get_session()
    scope      = get_agent_scope()
    today      = date.today()
    sel_year   = request.args.get("year",  today.year,  type=int)
    sel_month  = request.args.get("month", today.month, type=int)

    try:
        # All years available
        from sqlalchemy import extract, func
        years_q = db.query(extract("year", m.Policy.start_date).label("y")).distinct()
        if scope: years_q = years_q.filter(m.Policy.agent == scope)
        years = sorted(set(int(r.y) for r in years_q.all() if r.y), reverse=True)
        if today.year not in years: years.insert(0, today.year)

        # Monthly totals for the selected year (bar chart data)
        monthly = []
        for mo in range(1, 13):
            q = db.query(m.Policy).filter(
                extract("year",  m.Policy.start_date) == sel_year,
                extract("month", m.Policy.start_date) == mo,
            )
            if scope: q = q.filter(m.Policy.agent == scope)
            pols = q.all()
            active_pols = [p for p in pols if p.status != m.PolicyStatus.CANCELLED]
            premium = sum(p.premium or 0 for p in active_pols)
            comm    = sum((p.commission_amount or 0) or (p.premium or 0)*(p.commission_rate or 0)/100 for p in active_pols)
            monthly.append({
                "month": mo,
                "count": len(active_pols),
                "premium": round(premium, 2),
                "commission": round(comm, 2),
            })

        # Selected month detail
        q_m = db.query(m.Policy).filter(
            extract("year",  m.Policy.start_date) == sel_year,
            extract("month", m.Policy.start_date) == sel_month,
        )
        if scope: q_m = q_m.filter(m.Policy.agent == scope)
        sel_pols = q_m.order_by(m.Policy.start_date).all()

        # Breakdown by sector
        by_sector = {}
        for p in sel_pols:
            if p.status == m.PolicyStatus.CANCELLED: continue
            s = p.sector.value if p.sector else "Άλλο"
            if s not in by_sector:
                by_sector[s] = {"count": 0, "premium": 0, "commission": 0}
            by_sector[s]["count"]      += 1
            by_sector[s]["premium"]    += p.premium or 0
            by_sector[s]["commission"] += (p.commission_amount or 0) or (p.premium or 0)*(p.commission_rate or 0)/100
        by_sector = sorted(by_sector.items(), key=lambda x: -x[1]["premium"])

        # Breakdown by provider
        by_provider = {}
        for p in sel_pols:
            if p.status == m.PolicyStatus.CANCELLED: continue
            prov = p.provider or "—"
            if prov not in by_provider:
                by_provider[prov] = {"count": 0, "premium": 0}
            by_provider[prov]["count"]   += 1
            by_provider[prov]["premium"] += p.premium or 0
        by_provider = sorted(by_provider.items(), key=lambda x: -x[1]["premium"])[:10]

        # Policy list for selected month
        pol_data = []
        for p in sel_pols:
            c = db.query(m.Client).get(p.client_id)
            pol_data.append({
                "policy":      m.ser_policy(p),
                "client_name": c.name if c else "—",
                "client_id":   c.id if c else None,
            })

        # Totals for selected month
        active = [p for p in sel_pols if p.status != m.PolicyStatus.CANCELLED]
        total_premium    = round(sum(p.premium or 0 for p in active), 2)
        total_commission = round(sum((p.commission_amount or 0) or (p.premium or 0)*(p.commission_rate or 0)/100 for p in active), 2)
        total_cancelled  = len([p for p in sel_pols if p.status == m.PolicyStatus.CANCELLED])

        month_names = ["","Ιανουάριος","Φεβρουάριος","Μάρτιος","Απρίλιος","Μάιος","Ιούνιος",
                       "Ιούλιος","Αύγουστος","Σεπτέμβριος","Οκτώβριος","Νοέμβριος","Δεκέμβριος"]

        return render_template("agent/production.html",
            sel_year=sel_year, sel_month=sel_month,
            years=years, months=range(1,13), month_names=month_names,
            monthly=monthly, pol_data=pol_data,
            by_sector=by_sector, by_provider=by_provider,
            total_premium=total_premium, total_commission=total_commission,
            total_count=len(active), total_cancelled=total_cancelled,
            today=today.strftime("%Y-%m-%d"),
        )
    finally:
        db.close()

@app.route("/admin/fix-policy-agents", methods=["POST"])
@agent_required
def admin_fix_policy_agents():
    """Admin tool: update policy agent codes for existing policies."""
    if get_agent_scope() is not None:
        return redirect(url_for("agent_dashboard"))
    db = m.get_session()
    try:
        # Get all policies with null/empty agent or numeric codes
        updated = 0
        policies = db.query(m.Policy).all()
        for p in policies:
            new_code = request.form.get(f"agent_{p.id}")
            if new_code is not None:
                p.agent = new_code.strip() or None
                updated += 1
        db.commit()
        flash(f"✅ Ενημερώθηκαν {updated} συμβόλαια.", "success")
    except Exception as e:
        db.rollback(); flash(f"Σφάλμα: {e}", "danger")
    finally:
        db.close()
    return redirect(url_for("admin_agents"))


@app.route("/admin/policy/<int:policy_id>/set-agent", methods=["POST"])
@agent_required
def admin_set_policy_agent(policy_id):
    """Quick set agent code for a single policy."""
    if get_agent_scope() is not None:
        return jsonify({"error": "Μόνο admin"}), 403
    db = m.get_session()
    p = db.query(m.Policy).get(policy_id)
    if not p: db.close(); return jsonify({"error":"Not found"}), 404
    try:
        p.agent = request.json.get("agent","").strip() or None
        db.commit()
        db.close()
        return jsonify({"ok": True, "agent": p.agent})
    except Exception as e:
        db.rollback(); db.close()
        return jsonify({"error": str(e)}), 500


@app.route("/agent/client/<int:client_id>/delete", methods=["POST"])
@agent_required
def agent_delete_client(client_id):
    """Delete a client and all associated data."""
    db = m.get_session()
    client = db.query(m.Client).get(client_id)
    if not client:
        db.close(); abort(404)
    client_name = client.name
    try:
        # Delete in correct order (foreign keys)
        policies = db.query(m.Policy).filter_by(client_id=client_id).all()
        for p in policies:
            db.query(m.Payment).filter_by(policy_id=p.id).delete()
            db.query(m.Claim).filter_by(policy_id=p.id).delete()
            db.query(m.LixiariaEntry).filter_by(policy_id=p.id).delete()
            db.query(m.EmailQueue).filter_by(policy_id=p.id).delete()
            db.query(m.Document).filter_by(policy_id=p.id).delete()
        db.query(m.Policy).filter_by(client_id=client_id).delete()
        db.query(m.Ticket).filter_by(client_id=client_id).delete()
        db.query(m.Document).filter_by(client_id=client_id).delete()
        db.query(m.EmailQueue).filter_by(client_id=client_id).delete()
        # Remove portal user link
        portal_user = db.query(m.User).filter_by(client_id=client_id).first()
        if portal_user:
            portal_user.client_id = None
            portal_user.active = False
        db.delete(client)
        db.commit()
        flash(f"✅ Πελάτης '{client_name}' διαγράφηκε.", "success")
    except Exception as e:
        db.rollback()
        flash(f"❌ Σφάλμα διαγραφής: {e}", "danger")
    finally:
        db.close()
    return redirect(url_for("agent_clients"))


@app.route("/fix-name")
@login_required
def fix_name():
    """Quick fix: update session name and DB name for current user."""
    db = m.get_session()
    try:
        user = db.query(m.User).get(session.get("user_id"))
        if user and user.agent_code is None and user.role == m.UserRole.AGENT:
            user.name = "CHI Insurance Brokers"
            db.commit()
            session["user_name"] = "CHI Insurance Brokers"
            flash("✅ Όνομα ενημερώθηκε σε 'CHI Insurance Brokers'.", "success")
        else:
            flash("Δεν απαιτείται αλλαγή.", "info")
    except Exception as e:
        db.rollback(); flash(f"Σφάλμα: {e}", "danger")
    finally:
        db.close()
    return redirect(url_for("agent_dashboard"))


@app.route("/test-email")
@login_required
def test_email():
    """Debug route: test email sending and show env var status."""
    import os
    brevo_key  = bool(os.getenv("BREVO_API_KEY"))
    brevo_user = os.getenv("BREVO_SMTP_USER","")
    brevo_pass = bool(os.getenv("BREVO_SMTP_PASS"))
    gmail_user = os.getenv("GMAIL_USER","")
    gmail_pass = bool(os.getenv("GMAIL_APP_PASS"))
    status = {
        "BREVO_API_KEY":   "✓ set" if brevo_key  else "✗ NOT SET",
        "BREVO_SMTP_USER": brevo_user or "✗ NOT SET",
        "BREVO_SMTP_PASS": "✓ set" if brevo_pass else "✗ NOT SET",
        "GMAIL_USER":      gmail_user or "✗ NOT SET",
        "GMAIL_APP_PASS":  "✓ set" if gmail_pass else "✗ NOT SET",
    }
    # Try sending test email
    ok, err = _brevo_send("xiatropoulos@gmail.com","Chris","Test CHI Portal","<p>Test OK</p>")
    result = "✅ Email sent!" if ok else f"❌ {err}"
    rows = "".join(f"<tr><td style='padding:6px 12px;border-bottom:1px solid #eee'>{k}</td><td style='padding:6px 12px;border-bottom:1px solid #eee'>{v}</td></tr>" for k,v in status.items())
    return f"""<html><body style='font-family:sans-serif;padding:30px'>
    <h2>Email Debug</h2>
    <table border=0 style='border:1px solid #ddd;border-radius:8px;border-collapse:collapse;margin-bottom:20px'>
    {rows}</table>
    <h3>Send result: {result}</h3>
    <a href='/agent/dashboard'>← Back</a>
    </body></html>"""

# ── ERROR HANDLERS ─────────────────────────────────────────────────────────────

@app.errorhandler(404)
def not_found(e):
    return render_template("error.html", code=404, msg="Η σελίδα δεν βρέθηκε."), 404

@app.errorhandler(403)
def forbidden(e):
    return render_template("error.html", code=403, msg="Δεν έχετε πρόσβαση."), 403

@app.errorhandler(500)
def server_error(e):
    return render_template("error.html", code=500, msg=f"Σφάλμα διακομιστή: {e}"), 500

# ── INIT ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    m.init_db()
    port = int(os.getenv("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)

# ══════════════════════════════════════════════════════════════════════════════
# CSV IMPORT — from old portal ληξιάριο export
# ══════════════════════════════════════════════════════════════════════════════

SECTOR_MAP = {
    "ΥΓΕΙΑΣ": m.PolicySector.HEALTH,
    "ΥΓΕΙΑ": m.PolicySector.HEALTH,
    "ΖΩΗΣ": m.PolicySector.LIFE,
    "ΖΩΗ": m.PolicySector.LIFE,
    "ΠΥΡΟΣ-ΠΕΡΙΟΥΣΙΑΣ": m.PolicySector.PROPERTY,
    "ΠΥΡΟΣ-ΠΕΡΙΟΥΣΙΑ": m.PolicySector.PROPERTY,
    "ΠΕΡΙΟΥΣΙΑΣ": m.PolicySector.PROPERTY,
    "ΠΥΡΟΣ": m.PolicySector.PROPERTY,
    "ΑΣΤΙΚΗ ΕΥΘΥΝΗ": m.PolicySector.OTHER,
    "ΑΥΤΟΚΙΝΗΤΟΥ": m.PolicySector.MOTOR,
    "ΑΥΤΟΚΙΝΗΤΟ": m.PolicySector.MOTOR,
    "AYTOKINHTO": m.PolicySector.MOTOR,   # Latin chars from CSV
    "ΧΕΡΣΑΙΩΝ ΟΧΗΜΑΤΩΝ": m.PolicySector.MOTOR,
    "ΧΕΡΣΑΙΑ ΟΧΗΜΑΤΑ": m.PolicySector.MOTOR,
    "ΟΔΙΚΗ ΒΟΗΘΕΙΑ": m.PolicySector.MOTOR,
    "ΤΑΞΙΔΙΟΥ": m.PolicySector.TRAVEL,
    "ΤΑΞΙΔΙ": m.PolicySector.TRAVEL,
    "ΚΑΤΟΙΚΙΔΙΩΝ": m.PolicySector.PET,
    "ΚΑΤΟΙΚΙΔΙΑ": m.PolicySector.PET,
    "ΕΠΙΧΕΙΡΗΣΕΩΝ": m.PolicySector.BUSINESS,
    "ΕΠΙΧΕΙΡΗΣΗ": m.PolicySector.BUSINESS,
}

# Agent number → code mapping
AGENT_NUMBER_MAP = {
    "1032": "ca",
    "1868": "3p",
    "1000": "chi",
}

def _parse_num_gr(s):
    """Parse Greek/European number: 1.151,19 -> 1151.19. Strips currency
    symbols / stray whitespace too, e.g. "37.02€" -> 37.02."""
    if not s: return 0.0
    s = str(s).strip().strip('"')
    s = s.replace("€", "").replace("EUR", "").replace("ευρώ", "").strip()
    if not s: return 0.0
    try:
        if "," in s:
            s = s.replace(".", "").replace(",", ".")
        return float(s)
    except Exception:
        return 0.0

def _parse_date_gr(s):
    """Parse date string (YYYY-MM-DD HH:MM:SS or similar)."""
    if not s: return None
    s = str(s).strip().strip('"').replace(" 00:00:00","").strip()
    if not s or s == "0000-00-00": return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try: return datetime.strptime(s, fmt).date()
        except: pass
    return None

def _get_sector(raw):
    """Map sector string to PolicySector enum."""
    raw_up = raw.strip().upper()
    for k, v in SECTOR_MAP.items():
        if k in raw_up or raw_up in k:
            return v
    return m.PolicySector.OTHER

def _detect_delimiter(lines):
    """Pick whichever of ; or , actually splits the header into >1 column."""
    if not lines:
        return ";"
    header = lines[0]
    semi_cols  = len(header.split(";"))
    comma_cols = len(header.split(","))
    return ";" if semi_cols >= comma_cols else ","

def _looks_like_header(line, delim):
    """A header row is mostly non-numeric, non-date text in every field."""
    cells = [c.strip().strip('"') for c in line.split(delim)]
    if not cells or not any(cells):
        return False
    numericish = 0
    for c in cells:
        if not c:
            continue
        if _parse_date_gr(c) or _re_only_digits(c):
            numericish += 1
    # if most non-empty cells look like dates/numbers, this is a data row, not a header
    nonempty = [c for c in cells if c]
    return nonempty and numericish < len(nonempty) / 2

def _re_only_digits(s):
    import re as _re
    return bool(_re.match(r'^[\d.,€\s]+$', s))

def _strip_greek_accents(s):
    """Normalize Greek text for matching: uppercase + strip accents.
    Python's str.upper() does NOT remove the accent on Greek capitals
    (e.g. 'ό'.upper() == 'Ό', not 'Ο'), so a literal match against a
    plain-letter constant like "ΧΑΡΑΚΤΗΡΙΣΤΙΚΟ" silently fails against
    real-world headers that came from Excel/old exports with accents
    still in place. This collapses both forms to the same plain letters.
    """
    if not s:
        return ""
    s = s.upper()
    table = {
        "Ά": "Α", "Έ": "Ε", "Ή": "Η", "Ί": "Ι", "Ό": "Ο", "Ύ": "Υ", "Ώ": "Ω",
        "Ϊ": "Ι", "Ϋ": "Υ",
    }
    return "".join(table.get(ch, ch) for ch in s)

def _parse_lixiario_csv(file_bytes):
    """Auto-detect and parse CSV formats from the portal system / old exports.
    Format A - Ληξιάρια:  Έναρξη;Λήξη;Εταιρεία;Κλάδος;Συμβόλαιο;...;Πελάτης;ΑΦΜ;...
    Format B - Παραγωγή:  Χαρακτ/κό;Πελάτης;Συμβόλαιο;...;Κλάδος;Εταιρεία;Έκδοση;Έναρξη;Λήξη;Μικτά;...
    Format C - Ανανεώσεις: Συμβόλαιο,Χαρακτηριστικό,Πελάτης,Κλάδος,Εταιρεία,Έναρξη,Λήξη,Μικτά,Τηλέφωνο,Κινητό
    Delimiter (";" or ",") and number of header rows (1 or 2) are both
    auto-detected rather than assumed, since different exports vary.
    """
    for enc in ("iso-8859-7", "utf-8", "iso-8859-1", "cp1253"):
        try: text = file_bytes.decode(enc, errors="strict"); break
        except Exception: pass
    else: text = file_bytes.decode("utf-8", errors="replace")

    lines = text.splitlines()
    if not lines: return []

    delim = _detect_delimiter(lines)
    title = lines[0].split(delim)[0].strip().strip('"') if lines else ""
    header_row = lines[0]
    header_norm = _strip_greek_accents(header_row)
    title_norm = _strip_greek_accents(title)
    rows  = []

    # Decide how many leading rows are headers/titles (1 or 2) instead of
    # always assuming a title row + a header row.
    data_start = 1
    if len(lines) > 1 and _looks_like_header(lines[1], delim):
        data_start = 2

    if any(h in header_norm for h in ("ΣΥΜΒΟΛΑΙΟ,ΧΑΡΑΚΤΗΡΙΣΤΙΚΟ", "ΣΥΜΒΟΛΑΙΟ;ΧΑΡΑΚΤΗΡΙΣΤΙΚΟ")) or \
       (delim == "," and "ΣΥΜΒΟΛΑΙΟ" in header_norm and "ΠΕΛΑΤΗΣ" in header_norm and "ΑΦΜ" not in header_norm):
        # ── FORMAT C: ΑΝΑΝΕΩΣΕΙΣ (renewals export) ──────────────────
        # Cols: 0=Συμβόλαιο 1=Χαρακτηριστικό 2=Πελάτης 3=Κλάδος 4=Εταιρεία
        #       5=Έναρξη 6=Λήξη 7=Μικτά 8=Τηλέφωνο 9=Κινητό
        for line in lines[data_start:]:
            if not line.strip(): continue
            p = [x.strip().strip('"') for x in line.split(delim)]
            if len(p) < 7: continue
            expiry = _parse_date_gr(p[6]) if len(p) > 6 else None
            start  = _parse_date_gr(p[5]) if len(p) > 5 else None
            if not expiry: continue
            client_name = p[2].strip() if len(p) > 2 else ""
            if not client_name: continue
            sector_raw = p[3].strip() if len(p) > 3 else ""
            rows.append({
                "client_name":   client_name,
                "tax_id":        "",
                "phone":         p[8].strip() if len(p) > 8 else "",
                "mobile":        p[9].strip() if len(p) > 9 else "",
                "policy_number": p[0].strip() if len(p) > 0 else "",
                "receipt":       "",
                "kind":          "",
                "sector_raw":    sector_raw,
                "sector":        _get_sector(sector_raw).name,
                "provider":      p[4].strip() if len(p) > 4 else "",
                "license_plate": p[1].strip() if len(p) > 1 else "",
                "start_date":    str(start)  if start  else None,
                "expiry_date":   str(expiry) if expiry else None,
                "premium_gross": _parse_num_gr(p[7]) if len(p) > 7 else 0.0,
                "premium_net":   0.0,
                "commission":    0.0,
                "agent_code":    "",
                "csv_format":    "ananeoseis",
            })
        return rows

    if any(w in title for w in ("Παραγωγή","Παραγωγη","Paragogi")):
        # ── FORMAT B: ΠΑΡΑΓΩΓΗ ───────────────────────────────────────
        # Cols: 0=Χαρακτ/κό 1=Πελάτης 2=Συμβόλαιο 3=Απόδειξη
        #       4=Κατηγορία 5=Κλάδος 6=Εταιρεία 7=Έκδοση
        #       8=Έναρξη 9=Λήξη 10=Μικτά 11=Καθαρά 12=Εξ.Προμήθεια 13=Υπόλ.
        for line in lines[data_start:]:
            if not line.strip(): continue
            p = [x.strip().strip('"') for x in line.split(delim)]
            if len(p) < 10: continue
            client_name = p[1].strip() if len(p) > 1 else ""
            if not client_name: continue
            # col0: license plate only if looks like plate (letters+digits, no spaces, ≤10 chars)
            col0 = p[0].strip()
            import re as _re
            is_plate = bool(col0 and len(col0) <= 10 and _re.match(r'^[Α-Ωα-ωA-Za-z0-9]+$', col0) and any(c.isdigit() for c in col0))
            license_plate = col0 if is_plate else ""
            sector_raw = p[5].strip() if len(p) > 5 else ""
            expiry = _parse_date_gr(p[9]) if len(p) > 9 else None
            start  = _parse_date_gr(p[8]) if len(p) > 8 else None
            kind   = p[4].strip() if len(p) > 4 else ""
            rows.append({
                "client_name":   client_name,
                "tax_id":        "",
                "phone":         "",
                "mobile":        "",
                "policy_number": p[2].strip() if len(p) > 2 else "",
                "receipt":       p[3].strip() if len(p) > 3 else "",
                "kind":          kind,
                "sector_raw":    sector_raw,
                "sector":        _get_sector(sector_raw).name,
                "provider":      p[6].strip() if len(p) > 6 else "",
                "license_plate": license_plate,
                "start_date":    str(start) if start else None,
                "expiry_date":   str(expiry) if expiry else None,
                "premium_gross": _parse_num_gr(p[10]) if len(p) > 10 else 0.0,
                "premium_net":   _parse_num_gr(p[11]) if len(p) > 11 else 0.0,
                "commission":    _parse_num_gr(p[12]) if len(p) > 12 else 0.0,
                "agent_code":    "",
                "csv_format":    "paragogi",
            })
    else:
        # ── FORMAT A: ΛΗΞΙΑΡΙΑ ───────────────────────────────────────
        # Cols: 0=Έναρξη 1=Λήξη 2=Εταιρεία 3=Κλάδος 4=Συμβόλαιο
        #       5=Απόδειξη 6=Είδος 7=Χαρακτ/κό 8=Πελάτης 9=ΑΦΜ
        #       10=Τηλέφωνο 11=Κινητό 12=Συνεργάτης 13=Ημ.Εκτύπ. 14=Μικτά 15=Καθαρά
        for line in lines[data_start:]:
            if not line.strip(): continue
            p = [x.strip().strip('"') for x in line.split(delim)]
            if len(p) < 14: continue
            expiry = _parse_date_gr(p[1])
            start  = _parse_date_gr(p[0])
            if not expiry: continue
            sector_raw = p[3].strip()
            raw_agent  = p[12].strip()
            agent_code = AGENT_NUMBER_MAP.get(raw_agent, raw_agent) if raw_agent else ""
            rows.append({
                "client_name":   p[8].strip() if len(p) > 8 else "",
                "tax_id":        p[9].strip()  if len(p) > 9  else "",
                "phone":         p[10].strip() if len(p) > 10 else "",
                "mobile":        p[11].strip() if len(p) > 11 else "",
                "policy_number": p[4].strip()  if len(p) > 4  else "",
                "receipt":       p[5].strip()  if len(p) > 5  else "",
                "kind":          p[6].strip()  if len(p) > 6  else "",
                "sector_raw":    sector_raw,
                "sector":        _get_sector(sector_raw).name,
                "provider":      p[2].strip()  if len(p) > 2  else "",
                "license_plate": "",
                "start_date":    str(start)  if start  else None,
                "expiry_date":   str(expiry) if expiry else None,
                "premium_gross": _parse_num_gr(p[14]) if len(p) > 14 else 0.0,
                "premium_net":   _parse_num_gr(p[15]) if len(p) > 15 else 0.0,
                "commission":    0.0,
                "agent_code":    agent_code,
                "csv_format":    "lixiario",
            })
    return rows

@app.route("/agent/import", methods=["GET","POST"])
@agent_required
def agent_import():
    if request.method == "GET":
        return render_template("agent/import.html", preview=None, errors=[])

    # POST — preview or confirm
    action = request.form.get("action","preview")
    db = m.get_session()

    if action == "preview":
        all_rows = []
        errors = []
        files_seen = 0
        for field in ["file1","file2","file3"]:
            f = request.files.get(field)
            if f and f.filename:
                files_seen += 1
                try:
                    rows = _parse_lixiario_csv(f.read())
                    if not rows:
                        errors.append(f"{f.filename}: δεν βρέθηκαν έγκυρες εγγραφές — ελέγξτε ότι η μορφή του αρχείου ταιριάζει με μία από τις υποστηριζόμενες (διαχωριστικό ; ή , και σωστές στήλες).")
                    agent_code = request.form.get(f"agent_{field}", "chi")
                    for r in rows:
                        if not r["agent_code"]:
                            r["agent_code"] = agent_code
                        all_rows.append(r)
                except Exception as e:
                    errors.append(f"{f.filename}: {e}")
        db.close()
        if files_seen == 0:
            errors.append("Δεν επιλέχθηκε κανένα αρχείο. Επιλέξτε τουλάχιστον ένα αρχείο CSV πριν πατήσετε «Προεπισκόπηση».")
        if not all_rows:
            # Nothing parsed — re-show the upload form but WITH the errors
            # visible, instead of silently looking like nothing happened.
            return render_template("agent/import.html", preview=None, errors=errors)
        return render_template("agent/import.html", preview=all_rows, errors=errors)

    elif action == "confirm":
        # Parse from hidden JSON form data
        import json
        rows_json = request.form.get("rows_data","[]")
        try:
            rows = json.loads(rows_json)
        except Exception:
            flash("Σφάλμα ανάγνωσης δεδομένων.", "danger")
            db.close()
            return redirect(url_for("agent_import"))

        created_clients = 0
        created_policies = 0
        skipped = 0

        try:
            for r in rows:
                kind = r.get("kind","").upper()
                # Skip cancellations
                if "ΑΚΥΡ" in kind:
                    skipped += 1
                    continue

                # Find or create client by tax_id
                client = None
                if r.get("tax_id"):
                    client = db.query(m.Client).filter_by(tax_id=r["tax_id"]).first()
                if not client and r.get("client_name"):
                    client = db.query(m.Client).filter(
                        m.Client.name.ilike(r["client_name"])
                    ).first()
                if not client:
                    client = m.Client(
                        name=r["client_name"] or "Άγνωστος",
                        tax_id=r.get("tax_id") or None,
                        phone=r.get("phone") or None,
                        mobile=r.get("mobile") or None,
                    )
                    db.add(client)
                    db.flush()
                    created_clients += 1

                # Check if policy already exists
                existing = db.query(m.Policy).filter_by(
                    policy_number=r["policy_number"], client_id=client.id
                ).first() if r.get("policy_number") else None
                if existing:
                    skipped += 1
                    continue

                # Map sector from stored name string
                sector = m.PolicySector.OTHER
                sector_name = r.get("sector", "OTHER")
                try:
                    sector = m.PolicySector[sector_name]
                except (KeyError, ValueError):
                    for k, v in SECTOR_MAP.items():
                        if k in (r.get("sector_raw","").upper()):
                            sector = v; break

                expiry_date = None
                start_date  = None
                if r.get("expiry_date"):
                    try: expiry_date = datetime.strptime(r["expiry_date"], "%Y-%m-%d").date()
                    except: pass
                if r.get("start_date"):
                    try: start_date = datetime.strptime(r["start_date"], "%Y-%m-%d").date()
                    except: pass

                premium = float(r.get("premium_gross") or 0)
                policy = m.Policy(
                    client_id=client.id,
                    policy_number=r.get("policy_number"),
                    sector=sector,
                    policy_type=r.get("sector_raw","") or sector.value,
                    provider=r.get("provider",""),
                    premium=abs(premium),
                    start_date=start_date,
                    expiration_date=expiry_date,
                    status=m.PolicyStatus.ACTIVE if premium >= 0 else m.PolicyStatus.CANCELLED,
                    agent=r.get("agent_code","chi"),
                )
                db.add(policy)
                db.flush()
                created_policies += 1

                # Lixiario entry
                if expiry_date:
                    li = m.LixiariaEntry(
                        policy_id=policy.id,
                        expiry_month=expiry_date.month,
                        expiry_year=expiry_date.year,
                    )
                    db.add(li)

                # Payment installments based on payment_frequency
                if premium > 0:
                    _create_installments(db, policy, premium)

            db.commit()
            flash(f"✅ Import ολοκληρώθηκε: {created_clients} νέοι πελάτες, {created_policies} συμβόλαια, {skipped} παραλείφθηκαν.", "success")
        except Exception as e:
            db.rollback()
            flash(f"❌ Σφάλμα κατά το import: {e}", "danger")
        finally:
            db.close()
        return redirect(url_for("agent_clients"))

    db.close()
    return redirect(url_for("agent_import"))



@app.route("/agent/fix-import-data", methods=["POST"])
@agent_required
def agent_fix_import_data():
    """Fix sector and agent codes for previously imported data."""
    db = m.get_session()
    try:
        fixed_sectors = 0
        fixed_agents  = 0
        policies = db.query(m.Policy).all()
        for p in policies:
            changed = False
            # Fix agent numeric codes
            if p.agent in AGENT_NUMBER_MAP:
                p.agent = AGENT_NUMBER_MAP[p.agent]
                fixed_agents += 1
                changed = True
            # Fix sector from policy_type field
            pt = (p.policy_type or "").upper().strip()
            for key, val in SECTOR_MAP.items():
                if key in pt and p.sector == m.PolicySector.OTHER:
                    p.sector = val
                    fixed_sectors += 1
                    changed = True
                    break
            # Also fix based on provider name patterns
            if p.sector == m.PolicySector.OTHER and p.provider:
                prov = p.provider.upper()
                if "HD INSURANCE" in prov or "ΧΕΡΣΑΙ" in (p.policy_type or "").upper():
                    p.sector = m.PolicySector.MOTOR
                    fixed_sectors += 1
        db.commit()
        flash(f"✅ Διορθώθηκαν: {fixed_agents} agent codes, {fixed_sectors} κλάδοι.", "success")
    except Exception as e:
        db.rollback()
        flash(f"❌ Σφάλμα: {e}", "danger")
    finally:
        db.close()
    return redirect(url_for("agent_clients"))


# ══════════════════════════════════════════════════════════════════════════════
# PAYMENT DUE-DATE AUDIT & FIX TOOL
# ══════════════════════════════════════════════════════════════════════════════

def _pol_installment_count(policy):
    """Expected number of installments based on payment frequency."""
    if not policy:
        return 1
    return {
        m.PaymentFrequency.ANNUAL:    1,
        m.PaymentFrequency.SEMI:      2,
        m.PaymentFrequency.QUARTERLY: 4,
        m.PaymentFrequency.MONTHLY:   12,
    }.get(policy.payment_frequency, 1)


def _pay_installment_index(pay, policy, db):
    """Return 1-based index of this payment among all pending/paid for the policy."""
    if not policy:
        return 1
    all_pays = sorted(
        db.query(m.Payment).filter_by(policy_id=policy.id).all(),
        key=lambda p: (p.due_date or date.today(), p.id)
    )
    for i, p in enumerate(all_pays):
        if p.id == pay.id:
            return i + 1
    return 1


def _expected_due_dates(policy):
    """Return the list of expected due_dates for a policy based on its
    start_date and payment_frequency. Returns [] if data is insufficient."""
    if not policy.start_date and not policy.expiration_date:
        return []
    freq_map = {
        m.PaymentFrequency.ANNUAL:    (1,  12),
        m.PaymentFrequency.SEMI:      (2,   6),
        m.PaymentFrequency.QUARTERLY: (4,   3),
        m.PaymentFrequency.MONTHLY:   (12,  1),
    }
    n, step = freq_map.get(policy.payment_frequency, (1, 12))
    base = policy.start_date or policy.expiration_date
    return [_add_months(base, step * i) for i in range(n)]


@app.route("/agent/payments/audit")
@agent_required
def agent_payments_audit():
    """Show all payments whose due_date doesn't match the policy schedule."""
    db = m.get_session()
    scope = get_agent_scope()
    try:
        q = db.query(m.Payment).join(m.Policy).filter(
            m.Payment.status.in_([m.PaymentStatus.PENDING, m.PaymentStatus.OVERDUE])
        )
        if scope:
            q = q.filter(m.Policy.agent == scope)
        payments = q.order_by(m.Policy.id, m.Payment.due_date).all()

        issues = []
        seen_policy = {}   # policy_id → list of (payment, expected_date)

        # Group by policy
        from itertools import groupby
        policy_ids = list({pay.policy_id for pay in payments})
        for pid in policy_ids:
            pol = db.query(m.Policy).get(pid)
            if not pol:
                continue
            pol_pays = sorted(
                [p for p in payments if p.policy_id == pid],
                key=lambda p: p.due_date or date.today()
            )
            expected = _expected_due_dates(pol)
            if not expected:
                continue

            client = db.query(m.Client).get(pol.client_id)

            # Check count mismatch
            count_ok = len(pol_pays) == len(expected)
            # Check each date
            date_issues = []
            for i, pay in enumerate(pol_pays):
                exp_date = expected[i] if i < len(expected) else None
                if exp_date and pay.due_date != exp_date:
                    date_issues.append({
                        "pay_id":    pay.id,
                        "current":   pay.due_date.strftime("%d/%m/%Y") if pay.due_date else "—",
                        "expected":  exp_date.strftime("%d/%m/%Y"),
                        "amount":    pay.amount,
                        "status":    pay.status.value,
                    })

            if date_issues or not count_ok:
                freq_label = pol.payment_frequency.value if pol.payment_frequency else "—"
                issues.append({
                    "policy_id":    pol.id,
                    "policy_type":  pol.policy_type or "—",
                    "policy_num":   pol.policy_number or "—",
                    "provider":     pol.provider or "—",
                    "client_name":  client.name if client else "—",
                    "client_id":    client.id if client else None,
                    "start_date":   pol.start_date.strftime("%d/%m/%Y") if pol.start_date else "—",
                    "expiry_date":  pol.expiration_date.strftime("%d/%m/%Y") if pol.expiration_date else "—",
                    "frequency":    freq_label,
                    "expected_n":   len(expected),
                    "actual_n":     len(pol_pays),
                    "count_ok":     count_ok,
                    "date_issues":  date_issues,
                })

        return render_template("agent/payments_audit.html",
                               issues=issues, total=len(issues))
    finally:
        db.close()


@app.route("/agent/payments/fix", methods=["POST"])
@agent_required
def agent_payments_fix():
    """Fix due_dates for selected policies (or all if none selected)."""
    db = m.get_session()
    scope = get_agent_scope()
    policy_ids_raw = request.form.getlist("policy_ids")
    fix_all = request.form.get("fix_all") == "1"
    try:
        q = db.query(m.Policy)
        if scope:
            q = q.filter(m.Policy.agent == scope)
        if policy_ids_raw and not fix_all:
            q = q.filter(m.Policy.id.in_([int(x) for x in policy_ids_raw if x.isdigit()]))
        policies = q.all()

        fixed_policies = 0
        fixed_payments = 0
        rebuilt_policies = 0

        for pol in policies:
            expected = _expected_due_dates(pol)
            if not expected:
                continue

            annual_prem = pol.premium or 0
            if not annual_prem:
                continue

            freq_map = {
                m.PaymentFrequency.ANNUAL:    (1,  12),
                m.PaymentFrequency.SEMI:      (2,   6),
                m.PaymentFrequency.QUARTERLY: (4,   3),
                m.PaymentFrequency.MONTHLY:   (12,  1),
            }
            n_expected, step = freq_map.get(pol.payment_frequency, (1, 12))
            inst_amt = round(annual_prem / n_expected, 2)

            pending = sorted(
                db.query(m.Payment).filter(
                    m.Payment.policy_id == pol.id,
                    m.Payment.status.in_([m.PaymentStatus.PENDING,
                                          m.PaymentStatus.OVERDUE])
                ).all(),
                key=lambda p: (p.due_date or date.today(), p.id)
            )

            # ALWAYS delete all pending first to avoid duplicate accumulation,
            # then rebuild cleanly from the policy start_date.
            for pay in pending:
                db.delete(pay)
            db.flush()

            if pending:  # only count as rebuilt if there was something to fix
                rebuilt_policies += 1

            _create_installments(db, pol, annual_prem)

        db.commit()
        parts = []
        if fixed_payments:
            parts.append(f"{fixed_payments} πληρωμές σε {fixed_policies} συμβόλαια")
        if rebuilt_policies:
            parts.append(f"αναδημιουργήθηκαν δόσεις σε {rebuilt_policies} συμβόλαια")
        msg = " · ".join(parts) if parts else "Δεν βρέθηκαν διορθώσεις"
        flash(f"✅ Διόρθωση ολοκληρώθηκε: {msg}.", "success")
    except Exception as e:
        db.rollback()
        flash(f"❌ Σφάλμα: {e}", "danger")
    finally:
        db.close()
    return redirect(url_for("agent_payments_audit"))


@app.route("/agent/payment/<int:pay_id>/edit", methods=["GET", "POST"])
@agent_required
def agent_payment_edit(pay_id):
    """Manual edit of a single payment installment — due_date, amount, status."""
    db = m.get_session()
    pay = db.query(m.Payment).get(pay_id)
    if not pay:
        db.close(); abort(404)
    policy = db.query(m.Policy).get(pay.policy_id)
    client = db.query(m.Client).get(policy.client_id) if policy else None

    if request.method == "POST":
        try:
            action = request.form.get("action", "save")
            if action == "delete":
                db.delete(pay)
                db.commit()
                flash("🗑 Δόση διαγράφηκε.", "info")
                db.close()
                return redirect(url_for("agent_client_detail",
                                        client_id=client.id if client else 0))
            # Save edits
            due_str = request.form.get("due_date", "")
            if due_str:
                pay.due_date = datetime.strptime(due_str, "%Y-%m-%d").date()
            amt = request.form.get("amount", "")
            if amt:
                pay.amount = round(float(amt), 2)
            new_status = request.form.get("status", "")
            if new_status:
                pay.status = m.PaymentStatus[new_status]
                if pay.status == m.PaymentStatus.PAID and not pay.payment_date:
                    pay.payment_date = date.today()
                elif pay.status != m.PaymentStatus.PAID:
                    pay.payment_date = None
            pay.notes = request.form.get("notes", "")
            db.commit()
            flash("✅ Δόση ενημερώθηκε.", "success")
            db.close()
            return redirect(url_for("agent_client_detail",
                                    client_id=client.id if client else 0))
        except Exception as e:
            db.rollback()
            flash(f"❌ Σφάλμα: {e}", "danger")

    # Count installment index for display
    all_pays = sorted(
        db.query(m.Payment).filter_by(policy_id=pay.policy_id).all(),
        key=lambda p: p.due_date or date.today()
    )
    idx = next((i+1 for i, p in enumerate(all_pays) if p.id == pay_id), 1)
    total = len(all_pays)

    pay_d    = m.ser_payment(pay)
    pol_d    = m.ser_policy(policy) if policy else {}
    client_d = m.ser_client(client) if client else {}
    db.close()
    return render_template("agent/payment_edit.html",
                           pay=pay_d, policy=pol_d, client=client_d,
                           idx=idx, total=total,
                           statuses=[s.name for s in m.PaymentStatus])


@app.route("/agent/payments/cleanup", methods=["POST"])
@agent_required
def agent_payments_cleanup():
    """Remove duplicate PENDING installments — keeps the earliest per slot."""
    db = m.get_session()
    scope = get_agent_scope()
    deleted_total = 0
    try:
        q = db.query(m.Policy)
        if scope:
            q = q.filter(m.Policy.agent == scope)
        for pol in q.all():
            freq_map = {
                m.PaymentFrequency.ANNUAL:    1,
                m.PaymentFrequency.SEMI:      2,
                m.PaymentFrequency.QUARTERLY: 4,
                m.PaymentFrequency.MONTHLY:   12,
            }
            n_expected = freq_map.get(pol.payment_frequency, 1)
            pending = sorted(
                db.query(m.Payment).filter(
                    m.Payment.policy_id == pol.id,
                    m.Payment.status.in_([m.PaymentStatus.PENDING,
                                          m.PaymentStatus.OVERDUE])
                ).all(),
                key=lambda p: (p.due_date or date.today(), p.id)
            )
            if len(pending) <= n_expected:
                continue
            # Keep first n_expected, delete the rest
            to_delete = pending[n_expected:]
            for p in to_delete:
                db.delete(p)
                deleted_total += 1
        db.commit()
        flash(f"✅ Εκκαθάριση: διαγράφηκαν {deleted_total} διπλότυπες δόσεις.", "success")
    except Exception as e:
        db.rollback()
        flash(f"❌ Σφάλμα: {e}", "danger")
    finally:
        db.close()
    return redirect(url_for("agent_payments_audit"))

# ══════════════════════════════════════════════════════════════════════════════
# PAYMENT NOTIFICATION EMAIL SYSTEM
# ══════════════════════════════════════════════════════════════════════════════

# Sectors that show bank account details (NOT health/life)
PAYMENT_BANK_SECTORS = {
    m.PolicySector.MOTOR, m.PolicySector.PROPERTY,
    m.PolicySector.TRAVEL, m.PolicySector.PET, m.PolicySector.BUSINESS,
    m.PolicySector.OTHER
}

# Bank accounts per agent code
AGENT_BANK_ACCOUNTS = {
    "3p": {
        "company": "3P INSURANCE AGENTS ΑΕ",
        "afm": "800478440",
        "banks": [
            {"bank": "Alpha Bank",    "iban": "GR4801401340134002320003540"},
            {"bank": "Εθνική Τράπεζα", "iban": "GR3901108910000089147029808"},
            {"bank": "Eurobank",      "iban": "GR3302602210000370200676490"},
            {"bank": "Τράπεζα Πειραιώς", "iban": "GR6201720890005089072164520"},
        ]
    },
    "ca": {
        "company": "CA Insurance Agents",
        "afm": "800338387",
        "banks": [
            {"bank": "Alpha Bank",    "iban": "GR4101401460146002320015029"},
            {"bank": "Eurobank",      "iban": "GR6802600270000300201693054"},
            {"bank": "Εθνική Τράπεζα", "iban": "GR7301106690000066900657306"},
        ]
    },
    "bu": {
        "company": "BROKERS UNION Α.Ε.",
        "afm": "",
        "banks": [
            {"bank": "Alpha Bank",    "iban": "GR9701401270127002320005673",  "swift": "CRBAGRAAXXX"},
            {"bank": "Eurobank",      "iban": "GR6602600190005202008785811",  "swift": "EFGBGRAA"},
            {"bank": "Εθνική Τράπεζα", "iban": "GR5801107150000071547021072", "swift": "ETHNGRAA"},
            {"bank": "Τράπεζα Πειραιώς", "iban": "GR0601720190005019072804300", "swift": "PIRBGRAAXXX"},
        ]
    },
    "chi": {
        "company": "CHI Insurance Brokers",
        "afm": "",
        "banks": []  # Add CHI IBAN if needed
    }
}

def _build_payment_email_html(client, policy, payment, bank_info, show_banks: bool) -> tuple:
    """Build payment notification email from serialized dicts. Returns (subject, body_html)."""
    # Support both ORM objects and plain dicts
    def _g(obj, attr, default=""):
        if obj is None: return default
        if isinstance(obj, dict): return obj.get(attr, default) or default
        return getattr(obj, attr, default) or default

    sector_name  = _g(policy, "sector") or (_g(policy, "sector_name") if isinstance(policy, dict) else "")
    expiry_raw   = _g(policy, "expiration_date")
    # Καταληκτική ημερομηνία πληρωμής = η due_date της συγκεκριμένης δόσης (Payment),
    # με fallback στην ημερομηνία έναρξης συμβολαίου μόνο αν λείπει η due_date.
    pay_due_raw  = _g(payment, "due_date")
    start_raw    = _g(policy, "start_date")
    due_raw      = pay_due_raw if pay_due_raw else start_raw
    expiry_str   = chi_date_filter(expiry_raw) if expiry_raw else "—"
    due_str      = chi_date_filter(due_raw) if due_raw else "—"
    policy_type   = _g(policy, "policy_type")
    provider      = _g(policy, "provider")
    policy_num    = _g(policy, "policy_number")
    payment_code  = _g(policy, "payment_code")
    coverage      = _g(policy, "coverage_details")
    license_plate = _g(policy, "license_plate")
    start_raw_pol = _g(policy, "start_date")
    start_str     = chi_date_filter(start_raw_pol) if start_raw_pol else ""
    client_name   = _g(client, "name")
    amount       = _g(payment, "amount", 0) or 0
    if not isinstance(amount, (int, float)):
        try: amount = float(amount)
        except: amount = 0

    subject = f"Ειδοποίηση Πληρωμής — {policy_type} — €{amount:,.2f}"

    # Build bank table HTML
    banks_html = ""
    if show_banks and bank_info and bank_info.get("banks"):
        rows = ""
        for b in bank_info["banks"]:
            swift_row = f"<tr><td style='padding:4px 10px;color:#64748B;font-size:12px'>Swift</td><td style='padding:4px 10px;font-size:12px'>{b.get('swift','')}</td></tr>" if b.get("swift") else ""
            rows += f"""
            <tr style='border-bottom:1px solid #F1F5F9'>
              <td colspan='2' style='padding:8px 10px;font-weight:700;font-size:13px;color:#1B2B5E;background:#F8FAFC'>{b['bank']}</td>
            </tr>
            <tr>
              <td style='padding:4px 10px;color:#64748B;font-size:12px'>IBAN</td>
              <td style='padding:4px 10px;font-size:13px;font-family:monospace;letter-spacing:1px'>{b['iban']}</td>
            </tr>
            {swift_row}"""
        banks_html = f"""
        <div style='margin:20px 0;padding:16px;background:#F8FAFC;border-radius:10px;border:1px solid #E2E8F0'>
          <div style='font-weight:700;font-size:13px;color:#1B2B5E;margin-bottom:10px'>
            💳 Τραπεζικοί Λογαριασμοί Πληρωμής
          </div>
          <div style='font-size:12px;color:#64748B;margin-bottom:10px'>
            Δικαιούχος: <strong>{bank_info.get('company','')}</strong>
            {f" · ΑΦΜ: {bank_info['afm']}" if bank_info.get('afm') else ''}
          </div>
          <table style='width:100%;border-collapse:collapse'>
            {rows}
          </table>
          <div style='margin-top:10px;font-size:11.5px;color:#94A3B8'>
            Παρακαλούμε αναφέρετε τον αριθμό συμβολαίου στην αιτιολογία της μεταφοράς.
          </div>
        </div>"""
    elif not show_banks:
        banks_html = """
        <div style='margin:20px 0;padding:14px;background:#EFF6FF;border-radius:10px;border:1px solid #DBEAFE'>
          <div style='font-size:13px;color:#1D4ED8'>
            📞 Για οδηγίες πληρωμής του κλάδου <strong>Υγείας/Ζωής</strong>, επικοινωνήστε μαζί μας:<br>
            <strong>xiatropoulos@gmail.com</strong> · +30 697 590 0189
          </div>
        </div>"""

    # RF code row
    rf_html = ""
    if payment_code:
        rf_html = f"""
        <tr>
          <td style='padding:6px 0;color:#64748B;font-size:13px'>Κωδικός RF</td>
          <td style='padding:6px 0;font-weight:700;font-size:14px;font-family:monospace;
                     color:#1B2B5E;letter-spacing:1px'>{payment_code}</td>
        </tr>"""

    # Coverage section (only if exists)
    coverage_html = ""
    if coverage:
        coverage_html = f"""
    <div style='margin:20px 0;padding:16px;background:#F0FDF4;border-radius:10px;border:1px solid #BBF7D0'>
      <div style='font-weight:700;font-size:13px;color:#15803D;margin-bottom:8px'>
        🛡️ Λεπτομέρειες Κάλυψης
      </div>
      <div style='font-size:13px;color:#374151;line-height:1.7;white-space:pre-wrap'>{coverage}</div>
    </div>"""

    body_html = f"""
<!DOCTYPE html>
<html lang="el">
<head><meta charset="UTF-8"></head>
<body style='margin:0;padding:0;background:#F4F6FB;font-family:"Segoe UI",Arial,sans-serif'>
<table width='100%' cellpadding='0' cellspacing='0' style='background:#F4F6FB;padding:30px 0'>
<tr><td align='center'>
<table width='600' cellpadding='0' cellspacing='0' style='background:white;border-radius:16px;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,0.08)'>

  <!-- Header -->
  <tr><td style='background:linear-gradient(135deg,#1B2B5E,#2E4BA3);padding:28px 36px'>
    <div style='color:#C9A96E;font-size:28px;font-weight:900;letter-spacing:4px'>CHI</div>
    <div style='color:rgba(255,255,255,0.6);font-size:11px;letter-spacing:2px;text-transform:uppercase'>Insurance Brokers</div>
  </td></tr>

  <!-- Body -->
  <tr><td style='padding:32px 36px'>
    <h2 style='color:#1B2B5E;margin:0 0 6px 0;font-size:20px'>Ειδοποίηση Πληρωμής Ασφαλίστρου</h2>
    <p style='color:#64748B;font-size:13.5px;margin:0 0 24px 0'>
      Αγαπητέ/ή <strong>{client_name}</strong>, σας ενημερώνουμε για την επερχόμενη πληρωμή ασφαλίστρου.
    </p>

    <!-- Policy Details -->
    <div style='background:#F8FAFC;border-radius:10px;padding:18px 20px;border:1px solid #E2E8F0;margin-bottom:20px'>
      <div style='font-weight:700;font-size:12px;color:#94A3B8;letter-spacing:1px;text-transform:uppercase;margin-bottom:12px'>
        Στοιχεία Συμβολαίου
      </div>
      <table style='width:100%;border-collapse:collapse'>
        <tr>
          <td style='padding:6px 0;color:#64748B;font-size:13px;width:40%'>Ασφαλιστήριο</td>
          <td style='padding:6px 0;font-weight:600;font-size:13px;color:#1B2B5E'>{policy_type}</td>
        </tr>
        <tr style='border-top:1px solid #F1F5F9'>
          <td style='padding:6px 0;color:#64748B;font-size:13px'>Ασφαλιστική</td>
          <td style='padding:6px 0;font-weight:600;font-size:13px'>{provider or '—'}</td>
        </tr>
        {"<tr style='border-top:1px solid #F1F5F9'><td style='padding:6px 0;color:#64748B;font-size:13px'>Αρ. Συμβολαίου</td><td style='padding:6px 0;font-weight:600;font-size:13px'>" + str(policy_num) + "</td></tr>" if policy_num else ""}
        <tr style='border-top:1px solid #F1F5F9'>
          <td style='padding:6px 0;color:#64748B;font-size:13px'>Κλάδος</td>
          <td style='padding:6px 0;font-size:13px'>{sector_name}</td>
        </tr>
        <tr style='border-top:1px solid #F1F5F9'>
          <td style='padding:6px 0;color:#64748B;font-size:13px'>Περίοδος Ασφάλισης</td>
          <td style='padding:6px 0;font-size:13px;font-weight:600;color:#1B2B5E'>
            {f"{start_str} &nbsp;→&nbsp; " if start_str else ""}{expiry_str}
          </td>
        </tr>
        {f"<tr style='border-top:1px solid #F1F5F9'><td style='padding:6px 0;color:#64748B;font-size:13px'>Πινακίδα</td><td style='padding:6px 0'><span style='background:#F1F5F9;border:1px solid #CBD5E1;border-radius:5px;padding:2px 10px;font-family:monospace;font-weight:700;font-size:14px;color:#1B2B5E;letter-spacing:2px'>{license_plate}</span></td></tr>" if license_plate else ""}
        {rf_html}
      </table>
    </div>

    {coverage_html}

    <!-- Amount -->
    <div style='background:linear-gradient(135deg,#1B2B5E,#2E4BA3);border-radius:12px;padding:20px 24px;margin-bottom:20px;text-align:center'>
      <div style='color:rgba(255,255,255,0.7);font-size:12px;letter-spacing:1px;text-transform:uppercase;margin-bottom:6px'>Ποσό Πληρωμής</div>
      <div style='color:#C9A96E;font-size:36px;font-weight:900'>€{amount:,.2f}</div>
      <div style='color:rgba(255,255,255,0.7);font-size:13px;margin-top:4px'>Καταληκτική ημερομηνία: <strong style='color:white'>{due_str}</strong></div>
    </div>

    {banks_html}

    <!-- Footer note -->
    <div style='background:#FEF3C7;border-radius:8px;padding:12px 16px;margin-top:16px'>
      <div style='font-size:12.5px;color:#92400E'>
        ⚠️ <strong>Σημαντικό:</strong> Αναφέρετε πάντα τον αριθμό συμβολαίου
        <strong>{policy_num or policy_type}</strong> στην αιτιολογία πληρωμής.
      </div>
    </div>
  </td></tr>

  <!-- Footer -->
  <tr><td style='background:#F8FAFC;padding:20px 36px;border-top:1px solid #E2E8F0'>
    <div style='font-size:12px;color:#94A3B8;line-height:1.8'>
      <strong style='color:#1B2B5E'>CHI Insurance Brokers</strong><br>
      xiatropoulos@gmail.com &nbsp;·&nbsp; <strong>+30 697 590 0189</strong><br>
      Για οποιαδήποτε απορία επικοινωνήστε μαζί μας.
    </div>
  </td></tr>

</table>
</td></tr>
</table>
</body></html>"""

    return subject, body_html


@app.route("/agent/payment/<int:pay_id>/notify", methods=["POST"])
@agent_required
def agent_send_payment_notification(pay_id):
    db = m.get_session()
    pay    = db.query(m.Payment).get(pay_id)
    if not pay:
        db.close(); return jsonify({"error": "Not found"}), 404

    policy = db.query(m.Policy).get(pay.policy_id)
    client = db.query(m.Client).get(policy.client_id) if policy else None

    if not client or not client.email:
        db.close()
        return jsonify({"error": "Ο πελάτης δεν έχει email"}), 400

    # Serialize BEFORE db.close()
    show_banks = policy.sector in PAYMENT_BANK_SECTORS if policy and policy.sector else False
    agent_code = (policy.agent or "chi").lower().strip() if policy else "chi"
    bank_info  = AGENT_BANK_ACCOUNTS.get(agent_code, AGENT_BANK_ACCOUNTS.get("chi", {}))
    pay_d    = m.ser_payment(pay)
    policy_d = m.ser_policy(policy)
    client_d = m.ser_client(client)
    client_email = client.email
    client_name  = client.name

    subject, body_html = _build_payment_email_html(client_d, policy_d, pay_d, bank_info, show_banks)

    # Send via Brevo
    brevo_key = os.getenv("BREVO_API_KEY", "")
    if not brevo_key:
        db.close()
        return jsonify({"error": "BREVO_API_KEY δεν έχει οριστεί"}), 500

    try:
        ok, err_msg = _brevo_send(client_email, client_name, subject, body_html)
        if ok:
            # Log in email queue
            eq = m.EmailQueue(
                client_id=client.id, policy_id=policy.id, payment_id=pay_id,
                recipient_email=client_email, subject=subject, body_html=body_html,
                status=m.EmailStatus.SENT, sent_at=datetime.now()
            )
            db.add(eq); db.commit()
            db.close()
            return jsonify({"success": True, "message": f"Email στάλθηκε στο {client.email}"})
        else:
            db.close()
            return jsonify({"error": f"Email error: {err_msg[:200]}"}), 500
    except Exception as e:
        db.close()
        return jsonify({"error": str(e)}), 500


@app.route("/agent/payment/<int:pay_id>/preview-notification")
@agent_required
def agent_preview_payment_notification(pay_id):
    """Preview the payment notification email in browser."""
    db = m.get_session()
    pay    = db.query(m.Payment).get(pay_id)
    policy = db.query(m.Policy).get(pay.policy_id) if pay else None
    client = db.query(m.Client).get(policy.client_id) if policy else None
    if not all([pay, policy, client]):
        db.close(); abort(404)

    show_banks = policy.sector in PAYMENT_BANK_SECTORS if policy.sector else False
    agent_code = (policy.agent or "chi").lower().strip()
    bank_info  = AGENT_BANK_ACCOUNTS.get(agent_code, {})
    # Serialize before close
    pay_d    = m.ser_payment(pay)
    policy_d = m.ser_policy(policy)
    client_d = m.ser_client(client)
    _, body_html = _build_payment_email_html(client_d, policy_d, pay_d, bank_info, show_banks)
    db.close()
    return body_html

# ══════════════════════════════════════════════════════════════════════════════
# DOCUMENT INTELLIGENCE — AI Scanner with Auto-Registration
# ══════════════════════════════════════════════════════════════════════════════

def _extract_text_from_file(file_bytes: bytes, filename: str, content_type: str = "") -> tuple:
    """Extract text from PDF/Excel/CSV. Returns (text, is_image, image_b64, media_type)."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    # Images → Vision API
    if ext in ("jpg", "jpeg", "png", "webp", "gif"):
        b64 = base64.b64encode(file_bytes).decode()
        mt  = f"image/{'jpeg' if ext in ('jpg','jpeg') else ext}"
        return "", True, b64, mt

    # PDF — try text extraction first, fallback to Vision
    if ext == "pdf":
        try:
            import pdfplumber, io as _io
            with pdfplumber.open(_io.BytesIO(file_bytes)) as pdf:
                text = "\n".join(page.extract_text() or "" for page in pdf.pages[:6])
            if len(text.strip()) > 100:
                return text, False, "", ""
        except Exception:
            pass
        # Scanned PDF → convert first page to image for Vision
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            page = doc[0]
            pix  = page.get_pixmap(dpi=150)
            img_bytes = pix.tobytes("jpeg")
            b64 = base64.b64encode(img_bytes).decode()
            return "", True, b64, "image/jpeg"
        except Exception:
            pass
        return "[PDF - could not extract text]", False, "", ""

    # Excel
    if ext in ("xlsx", "xls"):
        try:
            import openpyxl, io as _io
            wb   = openpyxl.load_workbook(_io.BytesIO(file_bytes), data_only=True)
            text = ""
            for ws in wb.worksheets[:2]:
                for row in ws.iter_rows(max_row=50, values_only=True):
                    vals = [str(v) for v in row if v is not None]
                    if vals:
                        text += " | ".join(vals) + "\n"
            return text, False, "", ""
        except Exception:
            return "[Excel - could not extract]", False, "", ""

    # CSV
    if ext == "csv":
        try:
            text = file_bytes.decode("utf-8", errors="replace")[:4000]
            return text, False, "", ""
        except Exception:
            return "[CSV error]", False, "", ""

    # Text files
    try:
        return file_bytes.decode("utf-8", errors="replace")[:4000], False, "", ""
    except Exception:
        return "[Unknown format]", False, "", ""


@app.route("/agent/scanner", methods=["GET", "POST"])
@agent_required
def agent_scanner():
    """AI Document Scanner — upload any file, Claude extracts & prepares auto-registration."""
    if request.method == "GET":
        return render_template("agent/scanner.html", result=None, filename=None)

    if "file" not in request.files or not request.files["file"].filename:
        flash("Δεν επιλέχθηκε αρχείο.", "warning")
        return redirect(url_for("agent_scanner"))

    f        = request.files["file"]
    filename = f.filename
    data     = f.read()

    # Extract text / image
    text, is_image, img_b64, media_type = _extract_text_from_file(data, filename)

    # AI classification & extraction
    if is_image:
        result = hal.classify_document_image(img_b64, media_type, filename)
    else:
        result = hal.classify_document(text, filename)

    # Store extracted data in session for confirmation step
    session["scanner_result"] = result
    session["scanner_filename"] = filename

    # Get matching clients/policies for preview
    db = m.get_session()
    suggestions = {}
    d = result.get("data", {})
    if d.get("client_name"):
        clients = db.query(m.Client).filter(
            m.Client.name.ilike(f"%{d['client_name'][:15]}%")
        ).limit(5).all()
        suggestions["clients"] = [{"id": c.id, "name": c.name, "tax_id": c.tax_id} for c in clients]
    if d.get("policy_number"):
        pols = db.query(m.Policy).filter(
            m.Policy.policy_number.ilike(f"%{d['policy_number']}%")
        ).limit(3).all()
        suggestions["policies"] = [{"id": p.id, "number": p.policy_number, "type": p.policy_type} for p in pols]
    providers = [r[0] for r in db.query(m.Provider.name).all()]
    db.close()

    return render_template("agent/scanner.html", result=result, filename=filename,
                           suggestions=suggestions, providers=providers)


@app.route("/agent/scanner/register", methods=["POST"])
@agent_required
def agent_scanner_register():
    """Auto-register extracted document data into the database."""
    result   = session.get("scanner_result", {})
    filename = session.get("scanner_filename", "")
    doc_type = result.get("doc_type", "unknown")
    d        = result.get("data", {})
    db = m.get_session()

    try:
        action = request.form.get("action", doc_type)

        # ── Commission Statement ──────────────────────────────────────────────
        if action == "commission_statement":
            provider_name = request.form.get("provider_name") or d.get("provider_name")
            provider = db.query(m.Provider).filter(
                m.Provider.name.ilike(f"%{provider_name[:20]}%")
            ).first() if provider_name else None
            if not provider and provider_name:
                provider = m.Provider(name=provider_name, active=True)
                db.add(provider); db.flush()
            stmt = m.CommissionStatement(
                provider_id=provider.id if provider else None,
                period_month=int(request.form.get("period_month") or d.get("period_month") or date.today().month),
                period_year=int(request.form.get("period_year") or d.get("period_year") or date.today().year),
                total_premium=float(request.form.get("total_premium") or d.get("total_premium") or 0),
                commission_rate=float(request.form.get("commission_rate") or d.get("commission_rate") or 0),
                commission_amount=float(request.form.get("commission_amount") or d.get("commission_amount") or 0),
                paid=bool(request.form.get("paid")),
                notes=f"Auto-imported from: {filename}"
            )
            db.add(stmt); db.commit()
            flash(f"✅ Κατάσταση Προμηθειών καταχωρήθηκε — {provider_name} ({stmt.period_month}/{stmt.period_year})", "success")
            return redirect(url_for("backoffice_commissions"))

        # ── Policy (new or renewal) ───────────────────────────────────────────
        elif action == "policy":
            client_id = request.form.get("client_id")
            if client_id:
                client = db.query(m.Client).get(int(client_id))
            else:
                # Find or create client
                tax_id = request.form.get("client_tax_id") or d.get("client_tax_id")
                client = db.query(m.Client).filter_by(tax_id=tax_id).first() if tax_id else None
                if not client:
                    client_name = request.form.get("client_name") or d.get("client_name", "Άγνωστος")
                    client = db.query(m.Client).filter(m.Client.name.ilike(f"%{client_name[:15]}%")).first()
                if not client:
                    client = m.Client(
                        name=request.form.get("client_name") or d.get("client_name", "Άγνωστος"),
                        tax_id=tax_id,
                        phone=d.get("client_phone"), mobile=d.get("client_mobile")
                    )
                    db.add(client); db.flush()

            # Map sector
            sector_raw = (request.form.get("sector") or d.get("sector") or "").upper()
            sector = m.PolicySector.OTHER
            for k, v in SECTOR_MAP.items():
                if k in sector_raw:
                    sector = v; break

            # Dates
            def parse_date(val):
                if not val: return None
                for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
                    try: return datetime.strptime(str(val), fmt).date()
                    except: pass
                return None

            prem = float(request.form.get("premium") or d.get("premium") or 0)
            expiry = parse_date(request.form.get("expiration_date") or d.get("expiration_date"))
            policy = m.Policy(
                client_id=client.id,
                policy_number=request.form.get("policy_number") or d.get("policy_number"),
                policy_type=request.form.get("policy_type") or d.get("policy_type", ""),
                sector=sector,
                provider=request.form.get("provider") or d.get("provider", ""),
                premium=prem,
                payment_code=d.get("payment_code"),
                license_plate=d.get("license_plate"),
                start_date=parse_date(d.get("start_date")),
                expiration_date=expiry,
                agent=d.get("agent_code", "chi"),
                status=m.PolicyStatus.ACTIVE,
            )
            db.add(policy); db.flush()
            if expiry:
                db.add(m.LixiariaEntry(policy_id=policy.id, expiry_month=expiry.month, expiry_year=expiry.year))
            if prem > 0:
                _create_installments(db, policy, prem)
            db.commit()
            flash(f"✅ Συμβόλαιο καταχωρήθηκε για {client.name}", "success")
            return redirect(url_for("agent_client_detail", client_id=client.id))

        # ── Payment Receipt ───────────────────────────────────────────────────
        elif action == "payment_receipt":
            pol_num = request.form.get("policy_number") or d.get("policy_number")
            policy  = db.query(m.Policy).filter_by(policy_number=pol_num).first() if pol_num else None
            if policy:
                pay = db.query(m.Payment).filter_by(
                    policy_id=policy.id, status=m.PaymentStatus.PENDING
                ).order_by(m.Payment.due_date).first()
                if pay:
                    pay.status = m.PaymentStatus.PAID
                    pay.payment_date = date.today()
                    pay.receipt_num = d.get("receipt_number", "")
                    db.commit()
                    flash(f"✅ Πληρωμή επισημάνθηκε ως PAID — {pol_num}", "success")
                    return redirect(url_for("agent_payments"))
            flash("⚠️ Δεν βρέθηκε αντίστοιχο συμβόλαιο/πληρωμή.", "warning")

        # ── Claim ─────────────────────────────────────────────────────────────
        elif action == "claim":
            pol_num = request.form.get("policy_number") or d.get("policy_number")
            policy  = db.query(m.Policy).filter_by(policy_number=pol_num).first() if pol_num else None
            if policy:
                def _pd(v):
                    if not v: return None
                    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
                        try: return datetime.strptime(str(v), fmt).date()
                        except: pass
                claim = m.Claim(
                    policy_id=policy.id,
                    claim_number=d.get("claim_number", ""),
                    description=request.form.get("description") or d.get("description", ""),
                    claim_amount=float(d.get("claim_amount") or 0) or None,
                    incident_date=_pd(d.get("incident_date")),
                    reported_date=date.today(),
                    status=m.ClaimStatus.OPEN
                )
                db.add(claim)
                # Auto-create ticket
                client = db.query(m.Client).get(policy.client_id)
                ticket = m.Ticket(
                    client_id=client.id if client else policy.client_id,
                    policy_id=policy.id,
                    subject=f"Αξίωση — {d.get('claim_number', 'Νέα')} — {policy.policy_type}",
                    description=d.get("description", ""),
                    status=m.TicketStatus.OPEN,
                    priority=m.TicketPriority.HIGH,
                    created_by="scanner"
                )
                db.add(ticket); db.commit()
                flash(f"✅ Αξίωση + Ticket δημιουργήθηκαν για {pol_num}", "success")
                return redirect(url_for("agent_tickets"))
            flash("⚠️ Δεν βρέθηκε συμβόλαιο.", "warning")

        # ── Client Email → Ticket ─────────────────────────────────────────────
        elif action == "client_email":
            client_email = request.form.get("client_email") or d.get("client_email")
            client = db.query(m.Client).filter_by(email=client_email).first() if client_email else None
            if not client and d.get("client_name"):
                client = db.query(m.Client).filter(
                    m.Client.name.ilike(f"%{d['client_name'][:15]}%")
                ).first()
            priority_map = {"high": m.TicketPriority.HIGH, "urgent": m.TicketPriority.URGENT,
                           "medium": m.TicketPriority.MEDIUM, "low": m.TicketPriority.LOW}
            priority = priority_map.get((d.get("priority") or "medium").lower(), m.TicketPriority.MEDIUM)
            ticket = m.Ticket(
                client_id=client.id if client else None,
                subject=request.form.get("subject") or d.get("subject", "Αίτημα πελάτη"),
                description=request.form.get("description") or d.get("description", ""),
                status=m.TicketStatus.OPEN,
                priority=priority,
                created_by=client_email or "scanner"
            )
            db.add(ticket); db.commit()
            flash(f"✅ Ticket δημιουργήθηκε — {ticket.subject[:50]}", "success")
            return redirect(url_for("agent_tickets"))

        db.close()
        flash("Άγνωστος τύπος εγγράφου.", "warning")
        return redirect(url_for("agent_scanner"))

    except Exception as e:
        db.rollback()
        flash(f"❌ Σφάλμα καταχώρησης: {e}", "danger")
        return redirect(url_for("agent_scanner"))
    finally:
        db.close()

# ══════════════════════════════════════════════════════════════════════════════
# AGENT MANAGEMENT (admin only)
# ══════════════════════════════════════════════════════════════════════════════

def get_agent_scope():
    """Returns agent code to filter by, or None if admin (sees all)."""
    if session.get('role') == 'backoffice':
        return None  # backoffice sees everything
    return session.get('agent_scope')  # None = admin, 'ca'/'3p'/etc = scoped

@app.route("/admin/agents")
@agent_required
def admin_agents():
    """Agent management — admin only."""
    if get_agent_scope() is not None:
        flash("Μόνο ο admin έχει πρόσβαση.", "danger")
        return redirect(url_for("agent_dashboard"))
    db = m.get_session()
    try:
        agents = db.query(m.Agent).filter((m.Agent.is_admin == False) | (m.Agent.is_admin == None)).order_by(m.Agent.code).all()
        data = []
        for ag in agents:
            user = db.query(m.User).filter_by(agent_code=ag.code).first()
            pols = db.query(m.Policy).filter(
                m.Policy.agent == ag.code,
                m.Policy.status == m.PolicyStatus.ACTIVE
            ).all()
            total_premium = sum((p.premium or 0) for p in pols)
            commission    = sum((p.commission_amount or (p.premium or 0)*(p.commission_rate or 0)/100) for p in pols)
            # Serialize BEFORE db.close()
            data.append({
                "agent":        m.ser_agent(ag),
                "user_email":   user.email if user else None,
                "user_id":      user.id if user else None,
                "pol_count":    len(pols),
                "clients_count":len(set(p.client_id for p in pols)),
                "total_premium":total_premium,
                "commission":   commission,
            })
        return render_template("admin/agents.html", agents=data)
    except Exception as e:
        import traceback
        flash(f"Σφάλμα φόρτωσης agents: {e}", "danger")
        return render_template("admin/agents.html", agents=[])
    finally:
        db.close()

@app.route("/admin/agent/add", methods=["GET","POST"])
@agent_required
def admin_add_agent():
    if get_agent_scope() is not None:
        return redirect(url_for("agent_dashboard"))
    if request.method == "POST":
        db = m.get_session()
        try:
            code = request.form.get("code","").strip().lower()
            if db.query(m.Agent).filter_by(code=code).first():
                flash(f"Κωδικός '{code}' υπάρχει ήδη.", "warning")
                db.close()
                return redirect(url_for("admin_add_agent"))
            ag = m.Agent(
                code=code, name=request.form.get("name"),
                email=request.form.get("email"), phone=request.form.get("phone"),
                mobile=request.form.get("mobile"), address=request.form.get("address"),
                company_name=request.form.get("company_name"),
                tax_id=request.form.get("tax_id"),
                commission_rate=float(request.form.get("commission_rate") or 0),
                is_admin=bool(request.form.get("is_admin")),
                notes=request.form.get("notes"), active=True
            )
            db.add(ag); db.flush()
            # Create portal user if requested
            if request.form.get("create_user") and request.form.get("user_email"):
                pw = request.form.get("user_password","chi2026!")
                db.add(m.User(
                    email=request.form.get("user_email"),
                    password_hash=generate_password_hash(pw),
                    role=m.UserRole.AGENT,
                    name=ag.name, agent_code=ag.code
                ))
            db.commit()
            flash(f"✅ Agent '{ag.code}' ({ag.name}) δημιουργήθηκε.", "success")
            return redirect(url_for("admin_agents"))
        except Exception as e:
            db.rollback(); flash(f"Σφάλμα: {e}", "danger")
        finally:
            db.close()
    return render_template("admin/agent_form.html", agent={}, action="add")

@app.route("/admin/agent/<int:agent_id>/edit", methods=["GET","POST"])
@agent_required
def admin_edit_agent(agent_id):
    if get_agent_scope() is not None:
        return redirect(url_for("agent_dashboard"))
    db = m.get_session()
    ag = db.query(m.Agent).get(agent_id)
    if not ag: db.close(); abort(404)
    if request.method == "POST":
        try:
            ag.name            = request.form.get("name")
            ag.email           = request.form.get("email")
            ag.phone           = request.form.get("phone")
            ag.mobile          = request.form.get("mobile")
            ag.address         = request.form.get("address")
            ag.company_name    = request.form.get("company_name")
            ag.tax_id          = request.form.get("tax_id")
            ag.commission_rate = float(request.form.get("commission_rate") or 0)
            ag.is_admin        = bool(request.form.get("is_admin"))
            ag.active          = bool(request.form.get("active"))
            ag.notes           = request.form.get("notes")
            db.commit()
            db.close()
            flash(f"✅ Agent '{ag.code}' ενημερώθηκε.", "success")
            return redirect(url_for("admin_agents"))
        except Exception as e:
            db.rollback()
            flash(f"Σφάλμα: {e}", "danger")
        finally:
            db.close()
    # GET
    ag_d = m.ser_agent(ag)
    user = db.query(m.User).filter_by(agent_code=ag.code).first()
    user_email = user.email if user else None
    db.close()
    return render_template("admin/agent_form.html", agent=ag_d,
                           user_email=user_email, action="edit")

@app.route("/admin/agent/<int:agent_id>/create-user", methods=["POST"])
@agent_required
def admin_create_agent_user(agent_id):
    """Create or reset portal user for an agent."""
    if get_agent_scope() is not None:
        return redirect(url_for("agent_dashboard"))
    db = m.get_session()
    ag = db.query(m.Agent).get(agent_id)
    if not ag: db.close(); abort(404)
    # Serialize before any operations
    ag_email = ag.email
    ag_name  = ag.name
    ag_code  = ag.code
    email = request.form.get("email") or ag_email
    # Use provided password if given, else DEFAULT_PASSWORD
    pw = request.form.get("password","").strip() or DEFAULT_PASSWORD
    must_change_pw = (pw == DEFAULT_PASSWORD)
    try:
        existing = db.query(m.User).filter_by(email=email).first()
        if existing:
            existing.password_hash = generate_password_hash(pw)
            existing.agent_code    = ag_code
            existing.name          = ag_name
            existing.must_change_password = must_change_pw
            flash(f"✅ Password reset για {email}", "success")
        else:
            db.add(m.User(email=email, password_hash=generate_password_hash(pw),
                          role=m.UserRole.AGENT, name=ag_name, agent_code=ag_code,
                          must_change_password=True))
            flash(f"✅ User δημιουργήθηκε: {email} / {pw}", "success")
        db.commit()
    except Exception as e:
        db.rollback(); flash(f"Σφάλμα: {e}", "danger")
    finally:
        db.close()
    return redirect(url_for("admin_agents"))

# ══════════════════════════════════════════════════════════════════════════════
# PASSWORD MANAGEMENT — Change / Reset / Forgot
# ══════════════════════════════════════════════════════════════════════════════

DEFAULT_PASSWORD = "YouM@tt3r!"

def _brevo_send(to_email: str, to_name: str, subject: str, body_html: str) -> tuple:
    """Send email via Brevo. Returns (success, error_message)."""
    import requests as req
    brevo_key = os.getenv("BREVO_API_KEY", "")
    if not brevo_key:
        return False, "BREVO_API_KEY not set"
    
    payload = {
        "sender": {"name": "CHI Insurance Brokers", "email": "xiatropoulos@gmail.com"},
        "to": [{"email": to_email, "name": to_name}],
        "bcc": [{"email": "xiatropoulos@gmail.com", "name": "CHI Archive"}],
        "subject": subject,
        "htmlContent": body_html
    }
    try:
        resp = req.post("https://api.brevo.com/v3/smtp/email",
            headers={"api-key": brevo_key, "Content-Type": "application/json"},
            json=payload, timeout=20)
        if resp.status_code in (200, 201, 202):
            return True, ""
        # Handle IP restriction error
        err = resp.text[:300]
        if "unrecognised IP" in err or "IP address" in err.lower():
            # Fallback: try SMTP
            return _brevo_smtp_send(to_email, to_name, subject, body_html)
        return False, f"Brevo error {resp.status_code}: {err}"
    except Exception as e:
        return False, str(e)

def _brevo_smtp_send(to_email: str, to_name: str, subject: str, body_html: str) -> tuple:
    """Send via SMTP. Tries Brevo SMTP first, then Gmail as fallback.
    Env vars:
      BREVO_SMTP_USER + BREVO_SMTP_PASS  → Brevo SMTP (smtp-relay.brevo.com:587)
      GMAIL_USER      + GMAIL_APP_PASS   → Gmail SMTP (smtp.gmail.com:587)
    """
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    def _build_msg(from_addr):
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = f"CHI Insurance Brokers <{from_addr}>"
        msg["To"]      = f"{to_name} <{to_email}>"
        msg["Bcc"]     = "xiatropoulos@gmail.com"
        msg.attach(MIMEText(body_html, "html", "utf-8"))
        return msg

    last_error = ""

    # 1. Try Gmail SMTP first (App Password — most reliable)
    gmail_user = os.getenv("GMAIL_USER", "")
    gmail_pass = os.getenv("GMAIL_APP_PASS", "")
    if gmail_user and gmail_pass:
        try:
            msg = _build_msg(gmail_user)
            with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as srv:
                srv.ehlo(); srv.starttls(); srv.ehlo()
                srv.login(gmail_user, gmail_pass)
                recipients = list({to_email, "xiatropoulos@gmail.com"})
                srv.sendmail(gmail_user, recipients, msg.as_string())
            return True, ""
        except Exception as e:
            last_error = f"Gmail SMTP error: {e}"
    else:
        last_error = f"GMAIL_USER/APP_PASS not set"

    # 2. Fallback: Brevo SMTP
    brevo_user = os.getenv("BREVO_SMTP_USER", "")
    brevo_pass = os.getenv("BREVO_SMTP_PASS", "")
    if brevo_user and brevo_pass:
        try:
            msg = _build_msg("xiatropoulos@gmail.com")
            with smtplib.SMTP("smtp-relay.brevo.com", 587, timeout=30) as srv:
                srv.ehlo(); srv.starttls(); srv.ehlo()
                srv.login(brevo_user, brevo_pass)
                recipients = list({to_email, "xiatropoulos@gmail.com"})
                srv.sendmail("xiatropoulos@gmail.com", recipients, msg.as_string())
            return True, ""
        except Exception as e:
            last_error += f" | Brevo SMTP error: {e}"

    return False, last_error

def _send_reset_email(to_email: str, to_name: str, reset_url: str) -> bool:
    """Send password reset email via Brevo."""
    body_html = f"""
<!DOCTYPE html><html lang="el"><head><meta charset="UTF-8"></head>
<body style='font-family:Segoe UI,sans-serif;background:#F4F6FB;padding:30px 0'>
<table width='520' cellpadding='0' cellspacing='0' style='margin:0 auto;background:white;border-radius:14px;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,0.08)'>
<tr><td style='background:linear-gradient(135deg,#1B2B5E,#2E4BA3);padding:28px 32px'>
  <div style='color:#C9A96E;font-size:26px;font-weight:900;letter-spacing:3px'>CHI</div>
  <div style='color:rgba(255,255,255,0.6);font-size:10px;letter-spacing:2px'>INSURANCE BROKERS</div>
</td></tr>
<tr><td style='padding:32px'>
  <h2 style='color:#1B2B5E;margin:0 0 10px'>Επαναφορά Κωδικού</h2>
  <p style='color:#374151;font-size:14px;line-height:1.7'>Γεια σου <strong>{to_name}</strong>,<br>
  Λάβαμε αίτημα επαναφοράς κωδικού για τον λογαριασμό σου στο CHI Insurance Portal.</p>
  <div style='text-align:center;margin:28px 0'>
    <a href='{reset_url}' style='background:linear-gradient(135deg,#1B2B5E,#2E4BA3);color:white;
       padding:14px 32px;text-decoration:none;border-radius:10px;font-size:15px;font-weight:600;
       display:inline-block'>🔐 Επαναφορά Κωδικού</a>
  </div>
  <p style='color:#94A3B8;font-size:12px;line-height:1.7'>
    Ο σύνδεσμος ισχύει για <strong>1 ώρα</strong>.<br>
    Αν δεν ζήτησες επαναφορά κωδικού, αγνόησε αυτό το email.<br><br>
    Ή αντέγραψε αυτό το link:<br>
    <span style='color:#2E4BA3;word-break:break-all'>{reset_url}</span>
  </p>
</td></tr>
<tr><td style='background:#F8FAFC;padding:16px 32px;border-top:1px solid #E2E8F0'>
  <div style='font-size:11px;color:#94A3B8'>CHI Insurance Brokers · xiatropoulos@gmail.com</div>
</td></tr>
</table></body></html>"""
    ok, _ = _brevo_send(to_email, to_name, "Επαναφορά Κωδικού — CHI Insurance Portal", body_html)
    return ok


@app.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    """Voluntary password change from settings."""
    return _handle_password_change(forced=False)

@app.route("/change-password/first-login", methods=["GET", "POST"])
@login_required
def change_password_forced():
    """Forced password change on first login."""
    return _handle_password_change(forced=True)

def _handle_password_change(forced: bool):
    if request.method == "POST":
        db = m.get_session()
        user = db.query(m.User).get(session["user_id"])
        if not user:
            db.close(); return redirect(url_for("logout"))
        new_pw  = request.form.get("new_password", "")
        confirm = request.form.get("confirm_password", "")
        current = request.form.get("current_password", "")
        # Validate
        if len(new_pw) < 8:
            flash("Ο κωδικός πρέπει να έχει τουλάχιστον 8 χαρακτήρες.", "danger")
            db.close(); return render_template("auth/change_password.html", forced=forced)
        if new_pw != confirm:
            flash("Οι κωδικοί δεν ταιριάζουν.", "danger")
            db.close(); return render_template("auth/change_password.html", forced=forced)
        if new_pw == DEFAULT_PASSWORD:
            flash("Δεν μπορείς να χρησιμοποιήσεις τον default κωδικό.", "danger")
            db.close(); return render_template("auth/change_password.html", forced=forced)
        if not forced:
            if not check_password_hash(user.password_hash, current):
                flash("Ο τρέχων κωδικός είναι λάθος.", "danger")
                db.close(); return render_template("auth/change_password.html", forced=forced)
        user.password_hash       = generate_password_hash(new_pw)
        user.must_change_password = False
        db.commit(); db.close()
        flash("✅ Ο κωδικός άλλαξε επιτυχώς!", "success")
        role = session.get("role")
        if role == "agent":      return redirect(url_for("agent_dashboard"))
        if role == "backoffice": return redirect(url_for("backoffice_dashboard"))
        return redirect(url_for("client_dashboard"))
    return render_template("auth/change_password.html", forced=forced)


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        db = m.get_session()
        user  = db.query(m.User).filter_by(email=email, active=True).first()
        # Always show success (don't reveal if email exists)
        if user:
            import secrets
            token = secrets.token_urlsafe(32)
            # Delete old tokens for this user
            db.query(m.PasswordResetToken).filter_by(user_id=user.id, used=False).delete()
            reset = m.PasswordResetToken(
                user_id=user.id, token=token, email=user.email,
                expires_at=datetime.now() + timedelta(hours=1)
            )
            db.add(reset); db.commit()
            reset_url = request.url_root.rstrip("/") + url_for("reset_password", token=token)
            _send_reset_email(user.email, user.name or user.email, reset_url)
        db.close()
        return render_template("auth/forgot_password.html", sent=True, email=email)
    return render_template("auth/forgot_password.html", sent=False)


@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    db = m.get_session()
    reset = db.query(m.PasswordResetToken).filter_by(token=token, used=False).first()
    if not reset or reset.expires_at < datetime.now():
        db.close()
        return render_template("auth/reset_password.html", error="Ο σύνδεσμος έχει λήξει ή δεν είναι έγκυρος.")
    if request.method == "POST":
        new_pw  = request.form.get("new_password", "")
        confirm = request.form.get("confirm_password", "")
        if len(new_pw) < 8:
            db.close()
            return render_template("auth/reset_password.html", error="Τουλάχιστον 8 χαρακτήρες.", token=token)
        if new_pw != confirm:
            db.close()
            return render_template("auth/reset_password.html", error="Οι κωδικοί δεν ταιριάζουν.", token=token)
        if new_pw == DEFAULT_PASSWORD:
            db.close()
            return render_template("auth/reset_password.html", error="Μη χρησιμοποιείς τον default κωδικό.", token=token)
        user = db.query(m.User).get(reset.user_id)
        if user:
            user.password_hash        = generate_password_hash(new_pw)
            user.must_change_password = False
        reset.used = True
        db.commit(); db.close()
        flash("✅ Ο κωδικός άλλαξε! Συνδέσου με τον νέο σου κωδικό.", "success")
        return redirect(url_for("login"))
    db.close()
    return render_template("auth/reset_password.html", token=token, error=None)
