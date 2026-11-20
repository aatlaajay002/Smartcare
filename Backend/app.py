"""
AI-Powered Smart Healthcare Appointment & Assistance System - Flask backend.
Two roles:  user  -> patient website (booking, dashboard, AI tools)
            admin -> Admin Portal (monitor users, doctors, appointments, AI usage)
Admin APIs and the /admin pages are protected on the SERVER, so normal users can never open them.
Run:  python app.py   ->  http://127.0.0.1:5000
"""
import re
from datetime import datetime, timedelta
from functools import wraps

import os, socket, threading, webbrowser
from flask import Flask, jsonify, redirect, request, send_from_directory, session
from werkzeug.security import check_password_hash, generate_password_hash

from config import Config
from db import db
import ml_service
import genai_service

app = Flask(__name__, static_folder=str(Config.FRONTEND_DIR), static_url_path="")
app.config["SECRET_KEY"] = Config.SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = Config.MAX_UPLOAD_MB * 1024 * 1024
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
db.init()

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def ensure_admin():
    """Create the admin account on first start (credentials come from .env, see README)."""
    u = db.query("SELECT id, role FROM users WHERE email=?", (Config.ADMIN_EMAIL,), one=True)
    if not u:
        db.execute("INSERT INTO users (name,email,phone,password_hash,role) VALUES (?,?,?,?,'admin')",
                   (Config.ADMIN_NAME, Config.ADMIN_EMAIL, "", generate_password_hash(Config.ADMIN_PASSWORD)))
    elif u["role"] != "admin":
        db.execute("UPDATE users SET role='admin' WHERE id=?", (u["id"],))


ensure_admin()


# ------------------------------------------------------------------ helpers
def err(msg, code=400):
    return jsonify(error=msg), code


def log_activity(action, detail="", user_id=None):
    try:
        db.execute("INSERT INTO activity_log (user_id, action, detail) VALUES (?,?,?)",
                   (user_id if user_id is not None else session.get("user_id"), action, (detail or "")[:250]))
    except Exception:
        pass                                              # logging must never break a request


def current_user():
    uid = session.get("user_id")
    return db.query("SELECT id, name, email, role FROM users WHERE id=?", (uid,), one=True) if uid else None


def login_required(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        if not current_user():
            session.clear()
            return err("Please log in first.", 401)
        return fn(*a, **kw)
    return wrapper


def admin_required(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        u = current_user()
        if not u:
            return err("Please log in first.", 401)
        if u["role"] != "admin":
            return err("Admin access only.", 403)
        return fn(*a, **kw)
    return wrapper


@app.before_request
def protect_admin_pages():
    """The /admin page and every admin file (HTML/JS/CSS) are served only to a logged-in admin."""
    if request.path == "/admin" or request.path.startswith("/admin/"):
        u = current_user()
        if not u or u["role"] != "admin":
            return redirect("/") if request.path == "/admin" else err("Admin access only.", 403)


def doctor_json(d):
    return {**d, "available_days": d["available_days"].split(","), "timing": f"{d['start_time']} - {d['end_time']}"}


def generate_slots(doctor, date_str):
    """30-minute slots for a doctor on a date, minus already-booked ones (and past times for today)."""
    date = datetime.strptime(date_str, "%Y-%m-%d")
    if DAYS[date.weekday()] not in doctor["available_days"].split(","):
        return []
    cur = datetime.strptime(f"{date_str} {doctor['start_time']}", "%Y-%m-%d %H:%M")
    end = datetime.strptime(f"{date_str} {doctor['end_time']}", "%Y-%m-%d %H:%M")
    booked = {r["appt_time"] for r in db.query(
        "SELECT appt_time FROM appointments WHERE doctor_id=? AND appt_date=? AND status='Booked'", (doctor["id"], date_str))}
    now, slots = datetime.now(), []
    while cur < end:
        t = cur.strftime("%H:%M")
        if t not in booked and cur > now:
            slots.append(t)
        cur += timedelta(minutes=30)
    return slots


# ------------------------------------------------------------------ pages
@app.after_request
def no_cache(resp):
    """Never let the browser reuse an old copy of the pages/styles (fixes 'my changes do not show')."""
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.route("/")
def index():
    return app.send_static_file("index.html")


@app.route("/admin")
def admin_page():
    return send_from_directory(str(Config.FRONTEND_DIR / "admin"), "index.html")


@app.route("/api/health")
def health():
    return jsonify(status="ok", database=db.kind, llm_provider=genai_service._provider() or "offline-fallback")


# ------------------------------------------------------------------ auth
@app.post("/api/register")
def register():
    d = request.get_json(silent=True) or {}
    name, email, pw = (d.get("name") or "").strip(), (d.get("email") or "").strip().lower(), d.get("password") or ""
    phone = (d.get("phone") or "").strip()
    if len(name) < 2: return err("Please enter your full name.")
    if not EMAIL_RE.match(email): return err("Please enter a valid email address.")
    if not re.fullmatch(r"\d{10}", phone): return err("Phone number must be exactly 10 digits.")
    if len(pw) < 6: return err("Password must be at least 6 characters.")
    if db.query("SELECT id FROM users WHERE email=?", (email,), one=True):
        return err("This email is already registered. Please log in.", 409)
    uid = db.execute("INSERT INTO users (name,email,phone,password_hash,role) VALUES (?,?,?,?,'user')",   # public sign-up is ALWAYS a normal user
                     (name, email, phone, generate_password_hash(pw)))
    session["user_id"] = uid
    log_activity("register", name, uid)
    return jsonify(message="Registration successful", user={"id": uid, "name": name, "email": email, "role": "user"})


@app.post("/api/login")
def login():
    d = request.get_json(silent=True) or {}
    email, pw = (d.get("email") or "").strip().lower(), d.get("password") or ""
    u = db.query("SELECT * FROM users WHERE email=?", (email,), one=True)
    if not u or not check_password_hash(u["password_hash"], pw):
        return err("Invalid email or password.", 401)
    session.clear(); session["user_id"] = u["id"]
    log_activity("login", u["role"], u["id"])
    return jsonify(message="Login successful", user={"id": u["id"], "name": u["name"], "email": u["email"], "role": u["role"]})


@app.post("/api/logout")
def logout():
    session.clear()
    return jsonify(message="Logged out")


@app.get("/api/me")
def me():
    return jsonify(user=current_user())


# ------------------------------------------------------------------ doctors (public list)
@app.get("/api/specializations")
def specializations():
    return jsonify([r["specialization"] for r in db.query("SELECT DISTINCT specialization FROM doctors ORDER BY specialization")])


@app.get("/api/doctors")
def doctors():
    spec, q = request.args.get("specialization", "").strip(), request.args.get("q", "").strip()
    sql, params = "SELECT * FROM doctors WHERE 1=1", []
    if spec:
        sql += " AND specialization=?"; params.append(spec)
    if q:
        sql += " AND (name LIKE ? OR specialization LIKE ?)"; params += [f"%{q}%", f"%{q}%"]
    return jsonify([doctor_json(d) for d in db.query(sql + " ORDER BY specialization, name", tuple(params))])


@app.get("/api/doctors/<int:doc_id>/slots")
def slots(doc_id):
    date = request.args.get("date", "")
    doc = db.query("SELECT * FROM doctors WHERE id=?", (doc_id,), one=True)
    if not doc: return err("Doctor not found.", 404)
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        return err("Invalid date.")
    return jsonify(slots=generate_slots(doc, date), available_days=doc["available_days"].split(","))


# ------------------------------------------------------------------ appointments (patient)
@app.post("/api/appointments")
@login_required
def book():
    d = request.get_json(silent=True) or {}
    try:
        doc_id, date, time = int(d.get("doctor_id")), d.get("date", ""), d.get("time", "")
        day = datetime.strptime(date, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return err("Please select a doctor, date and time.")
    doc = db.query("SELECT * FROM doctors WHERE id=?", (doc_id,), one=True)
    if not doc: return err("Doctor not found.", 404)
    if day < datetime.now().date() or day > datetime.now().date() + timedelta(days=60):
        return err("Choose a date within the next 60 days.")
    if time not in generate_slots(doc, date):          # re-validate on the server (availability + double booking)
        return err("That slot is not available. Please pick another time.", 409)
    aid = db.execute("INSERT INTO appointments (user_id,doctor_id,appt_date,appt_time,reason) VALUES (?,?,?,?,?)",
                     (session["user_id"], doc_id, date, time, (d.get("reason") or "").strip()[:250]))
    log_activity("booking", f"{doc['name']} {date} {time}")
    return jsonify(message=f"Appointment confirmed with {doc['name']} on {date} at {time}.", id=aid)


@app.get("/api/appointments")
@login_required
def history():
    return jsonify(db.query(
        "SELECT a.id, a.appt_date, a.appt_time, a.reason, a.status, d.name AS doctor_name, d.specialization "
        "FROM appointments a JOIN doctors d ON d.id=a.doctor_id WHERE a.user_id=? "
        "ORDER BY a.appt_date DESC, a.appt_time DESC", (session["user_id"],)))


@app.post("/api/appointments/<int:aid>/cancel")
@login_required
def cancel(aid):
    a = db.query("SELECT * FROM appointments WHERE id=? AND user_id=?", (aid, session["user_id"]), one=True)
    if not a: return err("Appointment not found.", 404)
    if a["status"] != "Booked": return err("This appointment is already cancelled.")
    db.execute("UPDATE appointments SET status='Cancelled' WHERE id=?", (aid,))
    log_activity("cancel", f"appointment #{aid}")
    return jsonify(message="Appointment cancelled.")


@app.get("/api/dashboard")
@login_required
def dashboard():
    rows = db.query("SELECT a.id, a.appt_date, a.appt_time, a.reason, a.status, d.name AS doctor_name, d.specialization "
                    "FROM appointments a JOIN doctors d ON d.id=a.doctor_id WHERE a.user_id=? "
                    "ORDER BY a.appt_date, a.appt_time", (session["user_id"],))
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    upcoming = [r for r in rows if r["status"] == "Booked" and f"{r['appt_date']} {r['appt_time']}" >= now]
    return jsonify(total=len(rows), upcoming=len(upcoming), cancelled=sum(r["status"] == "Cancelled" for r in rows),
                   completed=sum(r["status"] == "Booked" and f"{r['appt_date']} {r['appt_time']}" < now for r in rows),
                   next=upcoming[0] if upcoming else None, upcoming_list=upcoming[:5])


# ------------------------------------------------------------------ ML: symptom -> doctor recommendation
@app.post("/api/predict")
@login_required
def predict():
    symptoms = ((request.get_json(silent=True) or {}).get("symptoms") or "").strip()
    if len(symptoms) < 3: return err("Please describe your symptoms (e.g. 'chest pain and dizziness').")
    if len(symptoms) > 500: return err("Please keep the description under 500 characters.")
    preds = ml_service.predict_specializations(symptoms, top_k=3)
    top = preds[0]
    docs = db.query("SELECT * FROM doctors WHERE specialization=? ORDER BY experience_years DESC", (top["specialization"],))
    log_activity("symptom_check", f"-> {top['specialization']} ({top['probability']:.0%})")
    return jsonify(predictions=preds, recommended=top["specialization"],
                   low_confidence=top["probability"] < 0.40, doctors=[doctor_json(x) for x in docs])


# ------------------------------------------------------------------ GenAI: report summarisation
@app.post("/api/summarize")
@login_required
def summarize():
    try:
        if request.files.get("file"):
            f = request.files["file"]
            text = genai_service.extract_text(f.filename or "", f.read())
        else:
            text = ((request.get_json(silent=True) or request.form or {}).get("text") or "")
        result = genai_service.summarize_report(text)
        log_activity("report_summary", f"{result['source']} {result.get('provider') or ''}".strip())   # report text itself is NOT stored
        return jsonify(result)
    except ValueError as e:
        return err(str(e))
    except Exception as e:
        return err(f"Could not process the report: {e}", 500)


# ------------------------------------------------------------------ GenAI + ML: AI Health Assistant (chat)
@app.post("/api/assistant")
@login_required
def assistant():
    d = request.get_json(silent=True) or {}
    msg = (d.get("message") or "").strip()
    if len(msg) < 2: return err("Please type your question.")
    if len(msg) > 600: return err("Please keep your message under 600 characters.")
    top = ml_service.predict_specializations(msg, top_k=1)[0]
    hint = top if top["probability"] >= 0.45 else None
    result = genai_service.assistant_reply(msg, d.get("history"), hint)
    spec = result.pop("specialization", None)
    if spec:                                                 # always offer doctors to book for the topic that was asked about
        docs = db.query("SELECT * FROM doctors WHERE specialization=? ORDER BY experience_years DESC", (spec,))
        prob = hint["probability"] if hint and hint["specialization"] == spec else None
        result["recommended"] = {"specialization": spec, "probability": prob, "doctors": [doctor_json(x) for x in docs[:3]]}
    log_activity("assistant_chat", f"{result['source']}" + (f" -> {spec}" if spec else ""))
    return jsonify(result)


# =================================================================== ADMIN PORTAL APIs (admin only)
def _s(v):
    return None if v is None else str(v)


@app.get("/api/admin/stats")
@admin_required
def admin_stats():
    today = datetime.now().date()
    count = lambda sql, p=(): db.query(sql, p, one=True)["c"]
    booked = db.query("SELECT a.appt_date, d.specialization FROM appointments a JOIN doctors d ON d.id=a.doctor_id WHERE a.status='Booked'")
    week = [(today + timedelta(days=i)).isoformat() for i in range(7)]
    by_spec = {}
    for r in booked:
        by_spec[r["specialization"]] = by_spec.get(r["specialization"], 0) + 1
    usage = {r["action"]: r["c"] for r in db.query("SELECT action, COUNT(*) AS c FROM activity_log GROUP BY action")}
    return jsonify(
        patients=count("SELECT COUNT(*) AS c FROM users WHERE role='user'"),
        doctors=count("SELECT COUNT(*) AS c FROM doctors"),
        appointments=count("SELECT COUNT(*) AS c FROM appointments"),
        booked=len(booked),
        cancelled=count("SELECT COUNT(*) AS c FROM appointments WHERE status='Cancelled'"),
        today=sum(r["appt_date"] == today.isoformat() for r in booked),
        next7=[{"date": d, "count": sum(r["appt_date"] == d for r in booked)} for d in week],
        by_specialization=sorted(({"specialization": k, "count": v} for k, v in by_spec.items()), key=lambda x: -x["count"]),
        ai_usage={"symptom_check": usage.get("symptom_check", 0), "report_summary": usage.get("report_summary", 0),
                  "assistant_chat": usage.get("assistant_chat", 0)},
        llm_provider=genai_service._provider() or "offline-fallback", database=db.kind)


@app.get("/api/admin/users")
@admin_required
def admin_users():
    rows = db.query("SELECT u.id, u.name, u.email, u.phone, u.created_at, "
                    "(SELECT COUNT(*) FROM appointments a WHERE a.user_id=u.id) AS appointments "
                    "FROM users u WHERE u.role='user' ORDER BY u.id DESC")
    return jsonify([{**r, "created_at": _s(r["created_at"])} for r in rows])


@app.delete("/api/admin/users/<int:uid>")
@admin_required
def admin_delete_user(uid):
    u = db.query("SELECT role FROM users WHERE id=?", (uid,), one=True)
    if not u: return err("User not found.", 404)
    if u["role"] == "admin": return err("Admin accounts cannot be deleted.", 403)
    db.execute("DELETE FROM appointments WHERE user_id=?", (uid,))
    db.execute("DELETE FROM users WHERE id=?", (uid,))
    log_activity("admin_delete_user", f"user #{uid}")
    return jsonify(message="Patient deleted.")


@app.get("/api/admin/appointments")
@admin_required
def admin_appointments():
    rows = db.query("SELECT a.id, a.appt_date, a.appt_time, a.reason, a.status, a.created_at, u.name AS patient, u.email AS patient_email, "
                    "d.name AS doctor_name, d.specialization FROM appointments a JOIN users u ON u.id=a.user_id "
                    "JOIN doctors d ON d.id=a.doctor_id ORDER BY a.appt_date DESC, a.appt_time DESC")
    return jsonify([{**r, "created_at": _s(r["created_at"])} for r in rows])


@app.post("/api/admin/appointments/<int:aid>/cancel")
@admin_required
def admin_cancel(aid):
    a = db.query("SELECT status FROM appointments WHERE id=?", (aid,), one=True)
    if not a: return err("Appointment not found.", 404)
    if a["status"] != "Booked": return err("Already cancelled.")
    db.execute("UPDATE appointments SET status='Cancelled' WHERE id=?", (aid,))
    log_activity("admin_cancel", f"appointment #{aid}")
    return jsonify(message="Appointment cancelled.")


def _doctor_payload(d):
    """Validate and normalise doctor form data. Returns (values, error)."""
    name, spec = (d.get("name") or "").strip(), (d.get("specialization") or "").strip()
    days = [x for x in DAYS if x in (d.get("available_days") or [])]
    start, end = (d.get("start_time") or "").strip(), (d.get("end_time") or "").strip()
    try:
        exp, fee = int(d.get("experience_years")), int(d.get("fee"))
    except (TypeError, ValueError):
        return None, "Experience and fee must be numbers."
    if len(name) < 3: return None, "Doctor name is required."
    if len(spec) < 3: return None, "Specialization is required."
    if not days: return None, "Select at least one available day."
    if not (TIME_RE.match(start) and TIME_RE.match(end) and start < end): return None, "Enter valid timings (start must be before end)."
    if not (0 <= exp <= 60) or fee < 0: return None, "Enter a valid experience (0-60) and fee."
    return (name, spec, exp, ",".join(days), start, end, fee), None


@app.get("/api/admin/doctors")
@admin_required
def admin_doctors():
    rows = db.query("SELECT d.*, (SELECT COUNT(*) FROM appointments a WHERE a.doctor_id=d.id AND a.status='Booked') AS booked "
                    "FROM doctors d ORDER BY d.specialization, d.name")
    return jsonify([doctor_json(r) for r in rows])


@app.post("/api/admin/doctors")
@admin_required
def admin_add_doctor():
    vals, e = _doctor_payload(request.get_json(silent=True) or {})
    if e: return err(e)
    did = db.execute("INSERT INTO doctors (name,specialization,experience_years,available_days,start_time,end_time,fee) VALUES (?,?,?,?,?,?,?)", vals)
    log_activity("admin_add_doctor", vals[0])
    return jsonify(message="Doctor added.", id=did)


@app.put("/api/admin/doctors/<int:did>")
@admin_required
def admin_edit_doctor(did):
    if not db.query("SELECT id FROM doctors WHERE id=?", (did,), one=True): return err("Doctor not found.", 404)
    vals, e = _doctor_payload(request.get_json(silent=True) or {})
    if e: return err(e)
    db.execute("UPDATE doctors SET name=?,specialization=?,experience_years=?,available_days=?,start_time=?,end_time=?,fee=? WHERE id=?", vals + (did,))
    log_activity("admin_edit_doctor", vals[0])
    return jsonify(message="Doctor updated.")


@app.delete("/api/admin/doctors/<int:did>")
@admin_required
def admin_delete_doctor(did):
    doc = db.query("SELECT name FROM doctors WHERE id=?", (did,), one=True)
    if not doc: return err("Doctor not found.", 404)
    if db.query("SELECT id FROM appointments WHERE doctor_id=? AND status='Booked' LIMIT 1", (did,), one=True):
        return err("This doctor has booked appointments. Cancel them first.", 409)
    db.execute("DELETE FROM appointments WHERE doctor_id=?", (did,))       # only cancelled ones remain
    db.execute("DELETE FROM doctors WHERE id=?", (did,))
    log_activity("admin_delete_doctor", doc["name"])
    return jsonify(message="Doctor deleted.")


@app.get("/api/admin/activity")
@admin_required
def admin_activity():
    limit = min(max(request.args.get("limit", 100, type=int), 1), 500)
    rows = db.query("SELECT a.id, a.action, a.detail, a.created_at, u.name AS user_name FROM activity_log a "
                    "LEFT JOIN users u ON u.id=a.user_id ORDER BY a.id DESC LIMIT ?", (limit,))
    return jsonify([{**r, "created_at": _s(r["created_at"])} for r in rows])


def _free_port(start=5000):
    """First port from 5000 upwards that nothing is listening on (an old copy may still hold 5000)."""
    for p in range(start, start + 20):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", p)) != 0:
                return p
    return start


if __name__ == "__main__":
    port = _free_port(5000)
    url = f"http://127.0.0.1:{port}"
    print("=" * 62)
    print(f" SmartCare  |  Database: {db.kind}  |  LLM: {genai_service._provider() or 'offline fallback'}")
    print(f" Admin login: {Config.ADMIN_EMAIL}")
    if port != 5000:
        print(" NOTE: port 5000 is busy - an OLD copy is probably still running.")
        print("       Close the old black window, or just use the address below.")
    print(f" OPEN THIS ADDRESS:  {url}")
    print("=" * 62)
    if not os.getenv("NO_BROWSER"):
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    app.run(host="127.0.0.1", port=port, debug=False)
