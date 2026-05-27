"""
CHI Insurance Portal v2 — Main Application
Flask + SQLAlchemy | Railway PostgreSQL | HAL AI Brain
Three Portals: Agent · Client · Back Office
"""
import os, io, json, base64
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

ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png", "docx", "xlsx", "doc"}

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
            role = user.role.value
            uid  = user.id
            name = user.name or email
            cid  = user.client_id
            user.last_login = datetime.now()
            db.commit()
            db.close()
            session["user_id"]   = uid
            session["role"]      = role
            session["user_name"] = name
            session["client_id"] = cid
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
            agent_pw = os.getenv("AGENT_PASSWORD", "chi2026!")
            backoffice_pw = os.getenv("BACKOFFICE_PASSWORD", "chi-bo-2026!")
            if not db.query(m.User).filter_by(email="info@chiinsurancebrokers.com").first():
                db.add(m.User(
                    email="info@chiinsurancebrokers.com",
                    password_hash=generate_password_hash(agent_pw),
                    role=m.UserRole.AGENT,
                    name="Παντελής Κουρμπελάς"
                ))
                created.append("Agent user")
            if not db.query(m.User).filter_by(email="backoffice@chiinsurancebrokers.com").first():
                db.add(m.User(
                    email="backoffice@chiinsurancebrokers.com",
                    password_hash=generate_password_hash(backoffice_pw),
                    role=m.UserRole.BACKOFFICE,
                    name="Back Office CHI"
                ))
                created.append("Backoffice user")
            db.commit()
            db.close()
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
        total_clients    = db.query(m.Client).count()
        active_policies  = db.query(m.Policy).filter_by(status=m.PolicyStatus.ACTIVE).count()
        pending_payments = db.query(m.Payment).filter_by(status=m.PaymentStatus.PENDING).count()
        overdue_payments = db.query(m.Payment).filter_by(status=m.PaymentStatus.OVERDUE).count()
        expiring_30      = db.query(m.Policy).filter(
            m.Policy.expiration_date.between(today, thirty),
            m.Policy.status == m.PolicyStatus.ACTIVE
        ).count()
        expiring_7 = db.query(m.Policy).filter(
            m.Policy.expiration_date.between(today, seven),
            m.Policy.status == m.PolicyStatus.ACTIVE
        ).count()
        open_tickets = db.query(m.Ticket).filter(
            m.Ticket.status.in_([m.TicketStatus.OPEN, m.TicketStatus.IN_PROCESS])
        ).count()
        # Total active premium
        total_premium = db.query(m.Policy).filter_by(status=m.PolicyStatus.ACTIVE).all()
        total_premium_val = sum((p.premium or 0) for p in total_premium)
        # Commission (30% avg estimated)
        total_commission = sum(((p.commission_amount or 0) if p.commission_amount else (p.premium or 0) * (p.commission_rate or 0) / 100) for p in total_premium)
        # Urgent renewals
        urgent = db.query(m.Policy).filter(
            m.Policy.expiration_date.between(today, seven),
            m.Policy.status == m.PolicyStatus.ACTIVE
        ).order_by(m.Policy.expiration_date).limit(8).all()
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
        # Recent clients
        recent_clients = db.query(m.Client).order_by(m.Client.created_date.desc()).limit(5).all()
        stats = {
            "total_clients": total_clients, "active_policies": active_policies,
            "pending_payments": pending_payments, "overdue_payments": overdue_payments,
            "expiring_30": expiring_30, "expiring_7": expiring_7,
            "open_tickets": open_tickets, "total_premium": total_premium_val,
            "total_commission": total_commission
        }
        return render_template("agent/dashboard.html", stats=stats,
                               urgent=urgent_data, recent_clients=recent_clients,
                               today=today)
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
        q = db.query(m.Client)
        if search:
            q = q.filter(
                (m.Client.name.ilike(f"%{search}%")) |
                (m.Client.email.ilike(f"%{search}%")) |
                (m.Client.phone.ilike(f"%{search}%")) |
                (m.Client.tax_id.ilike(f"%{search}%"))
            )
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

@app.route("/agent/client/add", methods=["GET", "POST"])
@agent_required
def agent_add_client():
    if request.method == "POST":
        db = m.get_session()
        try:
            dob_str = request.form.get("date_of_birth")
            dob = datetime.strptime(dob_str, "%Y-%m-%d").date() if dob_str else None
            client = m.Client(
                name=request.form.get("name"), email=request.form.get("email"),
                phone=request.form.get("phone"), mobile=request.form.get("mobile"),
                address=request.form.get("address"), postal_code=request.form.get("postal_code"),
                city=request.form.get("city"), tax_id=request.form.get("tax_id"),
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
    return render_template("agent/client_form.html", client=None, action="add")

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
        return render_template("agent/client_detail.html",
            client=client, pol_data=pol_data, tickets=tickets, documents=documents,
            claims=claims, today=today, total_premium=total_premium,
            total_commission=total_commission, sectors=[s for s in m.PolicySector])
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
            dob_str = request.form.get("date_of_birth")
            client.name        = request.form.get("name")
            client.email       = request.form.get("email")
            client.phone       = request.form.get("phone")
            client.mobile      = request.form.get("mobile")
            client.address     = request.form.get("address")
            client.postal_code = request.form.get("postal_code")
            client.city        = request.form.get("city")
            client.tax_id      = request.form.get("tax_id")
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
    return render_template("agent/client_form.html", client=client, action="edit")

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
            # Auto-create payment
            if prem > 0:
                pay = m.Payment(
                    policy_id=policy.id,
                    amount=prem,
                    due_date=policy.expiration_date or date.today(),
                    status=m.PaymentStatus.PENDING
                )
                db.add(pay)
            db.commit()
            flash(f"✅ Συμβόλαιο {policy.policy_number or policy.policy_type} προστέθηκε.", "success")
            return redirect(url_for("agent_client_detail", client_id=client_id))
        except Exception as e:
            db.rollback(); flash(f"Σφάλμα: {e}", "danger")
        finally:
            db.close()
    return render_template("agent/policy_form.html", client=client, policy=None,
                           sectors=m.PolicySector, providers=providers,
                           freq=m.PaymentFrequency, action="add")

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
            policy.hal_summary    = None   # clear cache
            policy.updated_date   = datetime.now()
            db.commit()
            flash("✅ Συμβόλαιο ενημερώθηκε.", "success")
            return redirect(url_for("agent_client_detail", client_id=client.id))
        except Exception as e:
            db.rollback(); flash(f"Σφάλμα: {e}", "danger")
        finally:
            db.close()
    return render_template("agent/policy_form.html", client=client, policy=policy,
                           sectors=m.PolicySector, providers=providers,
                           freq=m.PaymentFrequency, action="edit")

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
                "policy": p, "client": c,
                "days_left": (p.expiration_date - today).days,
                "pending_pay": pending_pay,
                "queued": bool(queued), "sent": bool(sent)
            })
        month_names = ["","Ιαν","Φεβ","Μαρ","Απρ","Μαι","Ιουν","Ιουλ","Αυγ","Σεπ","Οκτ","Νοε","Δεκ"]
        years = list(range(today.year - 1, today.year + 3))
        total_premium = sum((r["policy"].premium or 0) for r in renewals)
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
    emails = db.query(m.EmailQueue).order_by(m.EmailQueue.created_date.desc()).limit(100).all()
    data = []
    for e in emails:
        c = db.query(m.Client).get(e.client_id)
        p = db.query(m.Policy).get(e.policy_id)
        data.append({"eq": e, "client_name": c.name if c else "—",
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
    import requests as req
    try:
        resp = req.post("https://api.brevo.com/v3/smtp/email",
            headers={"api-key": brevo_key, "Content-Type": "application/json"},
            json={"sender": {"name":"CHI Insurance","email":"info@chiinsurancebrokers.com"},
                  "to": [{"email": eq.recipient_email}],
                  "subject": eq.subject, "htmlContent": eq.body_html}, timeout=15)
        if resp.status_code in (200, 201):
            eq.status = m.EmailStatus.SENT
            eq.sent_at = datetime.now()
            flash(f"✅ Email στάλθηκε στο {eq.recipient_email}", "success")
        else:
            eq.status = m.EmailStatus.FAILED
            eq.error_message = resp.text[:500]
            flash(f"❌ Αποτυχία: {resp.text[:100]}", "danger")
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
        policies = db.query(m.Policy).filter_by(status=m.PolicyStatus.ACTIVE).all()
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
    status_f = request.args.get("status","open")
    try:
        q = db.query(m.Ticket)
        if status_f == "open":
            q = q.filter(m.Ticket.status.in_([m.TicketStatus.OPEN, m.TicketStatus.IN_PROCESS]))
        elif status_f == "resolved":
            q = q.filter(m.Ticket.status.in_([m.TicketStatus.RESOLVED, m.TicketStatus.CLOSED]))
        tickets = q.order_by(m.Ticket.created_date.desc()).all()
        data = []
        for t in tickets:
            c = db.query(m.Client).get(t.client_id)
            data.append({"ticket": t, "client": c})
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
    return render_template("agent/ticket_form.html", clients=clients,
                           priorities=m.TicketPriority)

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
    status_f = request.args.get("status","all")
    try:
        q = db.query(m.Payment).join(m.Policy).join(m.Client)
        if status_f != "all":
            q = q.filter(m.Payment.status == m.PaymentStatus[status_f.upper()])
        payments = q.order_by(m.Payment.due_date.desc()).limit(200).all()
        data = []
        for pay in payments:
            pol = db.query(m.Policy).get(pay.policy_id)
            c   = db.query(m.Client).get(pol.client_id) if pol else None
            data.append({"payment": pay, "policy": pol, "client": c})
        return render_template("agent/payments.html", payments=data, status_f=status_f)
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
        documents = db.query(m.Document).filter_by(client_id=client_id).order_by(m.Document.uploaded_date.desc()).limit(5).all()
        return render_template("client/dashboard.html", client=client, policies=active,
                               next_payment=next_payment, expiring=expiring,
                               documents=documents, today=today)
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
            pol_data.append({"policy": p, "next_pay": next_pay,
                             "days_left": (p.expiration_date - today).days if p.expiration_date else None,
                             "payments": payments})
        return render_template("client/policies.html", client=client, pol_data=pol_data, today=today)
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
    return render_template("client/documents.html", client=client, policies=policies, documents=documents)

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
    context = f"Πελάτης: {client.name}\nΣυμβόλαια: " + ", ".join(
        f"{p.policy_type} ({p.provider})" for p in policies) if client else ""
    return render_template("client/hal.html", client=client, policies=policies, context=context)

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
    return render_template("backoffice/providers.html", providers=data)

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
        return render_template("backoffice/commissions.html",
            providers=providers, statements=statements,
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
            entries.append({"policy": p, "client": c, "li": li,
                            "days_left": (p.expiration_date - today).days})
        # Summary
        total_premium   = sum((e["policy"].premium or 0) for e in entries)
        total_commission= sum(((e["policy"].commission_amount or 0) or (e["policy"].premium or 0)*(e["policy"].commission_rate or 0)/100) for e in entries)
        sent_count      = sum(1 for e in entries if e["li"].renewal_sent)
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
        data.append({"ticket": t, "client": c})
    db.close()
    return render_template("backoffice/tickets.html", tickets=data, statuses=m.TicketStatus)

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
    "ΖΩΗΣ": m.PolicySector.LIFE,
    "ΠΥΡΟΣ-ΠΕΡΙΟΥΣΙΑΣ": m.PolicySector.PROPERTY,
    "ΠΕΡΙΟΥΣΙΑΣ": m.PolicySector.PROPERTY,
    "ΑΣΤΙΚΗ ΕΥΘΥΝΗ": m.PolicySector.OTHER,
    "ΑΥΤΟΚΙΝΗΤΟΥ": m.PolicySector.MOTOR,
    "ΑΥΤΟΚΙΝΗΤΟ": m.PolicySector.MOTOR,
    "ΤΑΞΙΔΙΟΥ": m.PolicySector.TRAVEL,
    "ΤΑΞΙΔΙ": m.PolicySector.TRAVEL,
    "ΚΑΤΟΙΚΙΔΙΩΝ": m.PolicySector.PET,
    "ΕΠΙΧΕΙΡΗΣΕΩΝ": m.PolicySector.BUSINESS,
}

def _parse_lixiario_csv(file_bytes):
    """Parse old-portal ληξιάριο CSV. Returns list of dicts."""
    import csv, io
    try:
        text = file_bytes.decode("iso-8859-7", errors="replace")
    except Exception:
        text = file_bytes.decode("utf-8", errors="replace")
    rows = []
    lines = text.splitlines()
    # Skip title row + header row
    data_lines = [l for l in lines[2:] if l.strip()]
    for line in data_lines:
        parts = [p.strip().strip('"') for p in line.split(";")]
        if len(parts) < 15:
            continue
        try:
            start_str  = parts[0].replace(" 00:00:00","").strip()
            expiry_str = parts[1].replace(" 00:00:00","").strip()
            start_date  = datetime.strptime(start_str,  "%Y-%m-%d").date() if start_str and start_str != "0000-00-00" else None
            expiry_date = datetime.strptime(expiry_str, "%Y-%m-%d").date() if expiry_str and expiry_str != "0000-00-00" else None
        except Exception:
            continue
        gross_str = parts[14].replace(".","").replace(",",".").strip() if len(parts) > 14 else "0"
        net_str   = parts[15].replace(".","").replace(",",".").strip() if len(parts) > 15 else "0"
        try:
            gross = float(gross_str) if gross_str else 0.0
            net   = float(net_str)   if net_str   else 0.0
        except Exception:
            gross = net = 0.0
        sector_raw = parts[3].strip().upper()
        sector = SECTOR_MAP.get(sector_raw, m.PolicySector.OTHER)
        rows.append({
            "start_date":    str(start_date) if start_date else None,
            "expiry_date":   str(expiry_date) if expiry_date else None,
            "provider":      parts[2].strip(),
            "sector_raw":    parts[3].strip(),
            "sector":        sector.name,
            "policy_number": parts[4].strip(),
            "receipt":       parts[5].strip(),
            "kind":          parts[6].strip(),
            "client_name":   parts[8].strip(),
            "tax_id":        parts[9].strip(),
            "phone":         parts[10].strip(),
            "mobile":        parts[11].strip(),
            "agent_code":    parts[12].strip(),
            "premium_gross": gross,
            "premium_net":   net,
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
        for field in ["file1","file2","file3"]:
            f = request.files.get(field)
            if f and f.filename:
                try:
                    rows = _parse_lixiario_csv(f.read())
                    agent_code = request.form.get(f"agent_{field}", "chi")
                    for r in rows:
                        if not r["agent_code"]:
                            r["agent_code"] = agent_code
                        all_rows.append(r)
                except Exception as e:
                    errors.append(f"{f.filename}: {e}")
        db.close()
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

                # Payment entry
                if premium > 0:
                    pay = m.Payment(
                        policy_id=policy.id,
                        amount=premium,
                        due_date=expiry_date or date.today(),
                        status=m.PaymentStatus.PENDING,
                    )
                    db.add(pay)

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
    """Build payment notification email. Returns (subject, body_html)."""
    from_name = "CHI Insurance Brokers"
    sector_name = policy.sector.value if policy.sector else ""
    expiry_str  = policy.expiration_date.strftime("%d/%m/%Y") if policy.expiration_date else "—"
    due_str     = payment.due_date.strftime("%d/%m/%Y") if payment.due_date else "—"

    subject = f"Ειδοποίηση Πληρωμής — {policy.policy_type} — €{payment.amount:,.2f}"

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
            <strong>info@chiinsurancebrokers.com</strong> · 210-XXXXXXX
          </div>
        </div>"""

    # RF code row
    rf_html = ""
    if policy.payment_code:
        rf_html = f"""
        <tr>
          <td style='padding:6px 0;color:#64748B;font-size:13px'>Κωδικός RF</td>
          <td style='padding:6px 0;font-weight:700;font-size:14px;font-family:monospace;
                     color:#1B2B5E;letter-spacing:1px'>{policy.payment_code}</td>
        </tr>"""

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
      Αγαπητέ/ή <strong>{client.name}</strong>, σας ενημερώνουμε για την επερχόμενη πληρωμή ασφαλίστρου.
    </p>

    <!-- Policy Details -->
    <div style='background:#F8FAFC;border-radius:10px;padding:18px 20px;border:1px solid #E2E8F0;margin-bottom:20px'>
      <div style='font-weight:700;font-size:12px;color:#94A3B8;letter-spacing:1px;text-transform:uppercase;margin-bottom:12px'>
        Στοιχεία Συμβολαίου
      </div>
      <table style='width:100%;border-collapse:collapse'>
        <tr>
          <td style='padding:6px 0;color:#64748B;font-size:13px;width:40%'>Ασφαλιστήριο</td>
          <td style='padding:6px 0;font-weight:600;font-size:13px;color:#1B2B5E'>{policy.policy_type}</td>
        </tr>
        <tr style='border-top:1px solid #F1F5F9'>
          <td style='padding:6px 0;color:#64748B;font-size:13px'>Ασφαλιστική</td>
          <td style='padding:6px 0;font-weight:600;font-size:13px'>{policy.provider or '—'}</td>
        </tr>
        {"<tr style='border-top:1px solid #F1F5F9'><td style='padding:6px 0;color:#64748B;font-size:13px'>Αρ. Συμβολαίου</td><td style='padding:6px 0;font-weight:600;font-size:13px'>" + policy.policy_number + "</td></tr>" if policy.policy_number else ""}
        <tr style='border-top:1px solid #F1F5F9'>
          <td style='padding:6px 0;color:#64748B;font-size:13px'>Κλάδος</td>
          <td style='padding:6px 0;font-size:13px'>{sector_name}</td>
        </tr>
        <tr style='border-top:1px solid #F1F5F9'>
          <td style='padding:6px 0;color:#64748B;font-size:13px'>Λήξη</td>
          <td style='padding:6px 0;font-size:13px'>{expiry_str}</td>
        </tr>
        {rf_html}
      </table>
    </div>

    <!-- Amount -->
    <div style='background:linear-gradient(135deg,#1B2B5E,#2E4BA3);border-radius:12px;padding:20px 24px;margin-bottom:20px;text-align:center'>
      <div style='color:rgba(255,255,255,0.7);font-size:12px;letter-spacing:1px;text-transform:uppercase;margin-bottom:6px'>Ποσό Πληρωμής</div>
      <div style='color:#C9A96E;font-size:36px;font-weight:900'>€{payment.amount:,.2f}</div>
      <div style='color:rgba(255,255,255,0.7);font-size:13px;margin-top:4px'>Καταληκτική ημερομηνία: <strong style='color:white'>{due_str}</strong></div>
    </div>

    {banks_html}

    <!-- Footer note -->
    <div style='background:#FEF3C7;border-radius:8px;padding:12px 16px;margin-top:16px'>
      <div style='font-size:12.5px;color:#92400E'>
        ⚠️ <strong>Σημαντικό:</strong> Αναφέρετε πάντα τον αριθμό συμβολαίου 
        <strong>{policy.policy_number or policy.policy_type}</strong> στην αιτιολογία πληρωμής.
      </div>
    </div>
  </td></tr>

  <!-- Footer -->
  <tr><td style='background:#F8FAFC;padding:20px 36px;border-top:1px solid #E2E8F0'>
    <div style='font-size:12px;color:#94A3B8;line-height:1.8'>
      <strong style='color:#1B2B5E'>CHI Insurance Brokers</strong><br>
      info@chiinsurancebrokers.com<br>
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

    # Determine if we show bank accounts
    show_banks = policy.sector in PAYMENT_BANK_SECTORS if policy and policy.sector else False
    agent_code = (policy.agent or "chi").lower().strip() if policy else "chi"
    bank_info  = AGENT_BANK_ACCOUNTS.get(agent_code, AGENT_BANK_ACCOUNTS.get("chi", {}))

    subject, body_html = _build_payment_email_html(client, policy, pay, bank_info, show_banks)

    # Send via Brevo
    brevo_key = os.getenv("BREVO_API_KEY", "")
    if not brevo_key:
        db.close()
        return jsonify({"error": "BREVO_API_KEY δεν έχει οριστεί"}), 500

    import requests as req
    try:
        resp = req.post("https://api.brevo.com/v3/smtp/email",
            headers={"api-key": brevo_key, "Content-Type": "application/json"},
            json={
                "sender": {"name": "CHI Insurance Brokers", "email": "info@chiinsurancebrokers.com"},
                "to": [{"email": client.email, "name": client.name}],
                "subject": subject,
                "htmlContent": body_html
            }, timeout=15)

        if resp.status_code in (200, 201, 202):
            # Log in email queue
            eq = m.EmailQueue(
                client_id=client.id, policy_id=policy.id, payment_id=pay.id,
                recipient_email=client.email, subject=subject, body_html=body_html,
                status=m.EmailStatus.SENT, sent_at=datetime.now()
            )
            db.add(eq); db.commit()
            db.close()
            return jsonify({"success": True, "message": f"Email στάλθηκε στο {client.email}"})
        else:
            db.close()
            return jsonify({"error": f"Brevo error: {resp.text[:200]}"}), 500
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

    _, body_html = _build_payment_email_html(client, policy, pay, bank_info, show_banks)
    db.close()
    return body_html
