from flask import Flask, request, jsonify, send_from_directory, render_template, redirect, url_for, session, abort
from flask_sqlalchemy import SQLAlchemy
from functools import wraps
from datetime import datetime
import hmac
import os
import re

app = Flask(__name__, static_folder="static", template_folder="templates")
app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY") or os.urandom(32),
    SQLALCHEMY_DATABASE_URI=os.environ.get("DATABASE_URL", "sqlite:///grievances.db").replace("postgres://", "postgresql://", 1),
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "true").lower() == "true",
    PERMANENT_SESSION_LIFETIME=60 * 60 * 8,
)
db = SQLAlchemy(app)


class Grievance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(80), nullable=False)
    priority = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(30), default="Submitted", nullable=False)
    department = db.Column(db.String(100), default="General Administration")
    location = db.Column(db.String(160), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def json(self):
        return {
            "id": f"GRV-{self.id:04d}",
            "title": self.title,
            "description": self.description,
            "category": self.category,
            "priority": self.priority,
            "status": self.status,
            "department": self.department,
            "location": self.location,
            "created_at": self.created_at.isoformat() + "Z",
        }


def classify(text):
    t = text.lower()
    rules = [
        (r"water|drain|garbage|sewage|sanitation|waste|washroom", "Water & Sanitation"),
        (r"school|college|teacher|classroom|student|exam|education", "Education"),
        (r"hospital|doctor|medicine|health|clinic|ambulance", "Healthcare"),
        (r"electric|power cut|transformer|voltage|street light|road|pothole|bridge|footpath|traffic", "Public Infrastructure"),
        (r"pension|certificate|document|application|official|permit|identity", "Administration"),
    ]
    category = next((name for pattern, name in rules if re.search(pattern, t)), "Other")
    priority = "High" if re.search(
        r"urgent|emergency|danger|unsafe|accident|fire|life.?threat|contaminat|severe|exposed wire", t
    ) else ("Medium" if re.search(
        r"delay|broken|not working|overflow|failure|leak|outage|blocked|repeated", t
    ) else "Low")
    return category, priority


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("is_admin"):
            if request.path.startswith("/api/"):
                return jsonify({"error": "Administrator login required."}), 401
            return redirect(url_for("admin_login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


@app.get("/")
def home():
    return send_from_directory("static", "index.html")


@app.get("/admin/login")
def admin_login():
    if session.get("is_admin"):
        return redirect(url_for("admin_dashboard"))
    return render_template("login.html", error=None, next=request.args.get("next", "/admin"))


@app.post("/admin/login")
def admin_login_submit():
    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""
    expected_username = os.environ.get("ADMIN_USERNAME", "")
    expected_password = os.environ.get("ADMIN_PASSWORD", "")
    next_url = request.form.get("next", "/admin")

    # No default admin credentials: configure both values in the hosting environment.
    valid = bool(expected_username and expected_password)
    valid = valid and hmac.compare_digest(username, expected_username)
    valid = valid and hmac.compare_digest(password, expected_password)
    if not valid:
        return render_template("login.html", error="Invalid login, or administrator credentials are not configured.", next=next_url), 401

    session.clear()
    session["is_admin"] = True
    session["admin_username"] = expected_username
    session.permanent = True
    if not next_url.startswith("/") or next_url.startswith("//"):
        next_url = "/admin"
    return redirect(next_url)


@app.get("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))


@app.get("/admin")
@admin_required
def admin_dashboard():
    return render_template("admin.html")


@app.get("/api/grievances")
@admin_required
def list_grievances():
    rows = Grievance.query.order_by(Grievance.created_at.desc()).all()
    return jsonify([r.json() for r in rows])


@app.post("/api/grievances")
def create_grievance():
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    desc = (data.get("description") or "").strip()
    if not title or not desc:
        return jsonify({"error": "Title and description are required."}), 400
    if len(title) > 160 or len(desc) > 5000:
        return jsonify({"error": "Title must be 160 characters or fewer and description 5,000 characters or fewer."}), 400

    category, priority = classify(title + " " + desc)
    # Public users may submit a complaint but cannot choose priority, status, or department routing.
    requested_location = (data.get("location") or "").strip()[:160]
    row = Grievance(
        title=title,
        description=desc,
        category=category,
        priority=priority,
        department=category,
        location=requested_location,
        status="Submitted",
    )
    db.session.add(row)
    db.session.commit()
    # Only return the receipt ID to the public submitter; never return case details here.
    return jsonify({"id": f"GRV-{row.id:04d}", "message": "Your grievance has been submitted."}), 201


@app.patch("/api/grievances/<int:case_id>")
@admin_required
def update_grievance(case_id):
    row = db.session.get(Grievance, case_id)
    if not row:
        return jsonify({"error": "Grievance not found."}), 404
    data = request.get_json(silent=True) or {}
    if data.get("status") in ["Submitted", "Under Review", "In Progress", "Resolved"]:
        row.status = data["status"]
    if data.get("department"):
        row.department = str(data["department"])[:100]
    db.session.commit()
    return jsonify(row.json())


@app.get("/api/stats")
@admin_required
def stats():
    rows = Grievance.query.all()
    return jsonify({
        "total": len(rows),
        "pending": sum(x.status in ("Submitted", "Under Review") for x in rows),
        "urgent": sum(x.priority == "High" and x.status != "Resolved" for x in rows),
        "resolved": sum(x.status == "Resolved" for x in rows),
    })


with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
