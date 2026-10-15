from flask import Flask, request, jsonify, send_from_directory, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from sqlalchemy import inspect, text
from datetime import datetime
import os, re
app = Flask(__name__, static_folder="static")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///grievances.db").replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY") or os.urandom(32)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = bool(os.environ.get("RENDER_SERVICE_ID") or os.environ.get("RENDER_EXTERNAL_URL") or os.environ.get("HTTPS_ONLY", "").lower() == "true")
db = SQLAlchemy(app)

class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(254), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

class Grievance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    title = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(80), nullable=False)
    priority = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(30), default="Submitted", nullable=False)
    department = db.Column(db.String(100), default="General Administration")
    location = db.Column(db.String(160), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def json(self):
        return {"id": f"GRV-{self.id:04d}", "title": self.title, "description": self.description,
                "category": self.category, "priority": self.priority, "status": self.status,
                "department": self.department, "location": self.location,
                "created_at": self.created_at.isoformat() + "Z"}

def classify(text):
    t = text.lower()
    rules = [
        (r"water|drain|garbage|sewage|sanitation|waste|toilet", "Water & Sanitation"),
        (r"school|college|teacher|classroom|student|exam|education", "Education"),
        (r"hospital|doctor|medicine|health|clinic|ambulance", "Healthcare"),
        (r"electric|power cut|transformer|voltage|street light|road|pothole|bridge|footpath|traffic", "Public Infrastructure"),
        (r"pension|certificate|document|application|official|permit|identity", "Administration")
    ]
    category = next((name for pattern,name in rules if re.search(pattern,t)), "Other")
    priority = "High" if re.search(r"urgent|emergency|danger|unsafe|accident|fire|life.?threat|contaminat|severe|exposed wire",t) else ("Medium" if re.search(r"delay|broken|not working|overflow|failure|leak|outage|blocked|repeated",t) else "Low")
    return category, priority

@app.get("/")
def home():
    return send_from_directory("static", "index.html")

def login_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return jsonify({"error": "Please log in to continue."}), 401
        return fn(*args, **kwargs)
    return wrapped

def current_user():
    return db.session.get(User, session.get("user_id"))

@app.get("/api/auth/me")
def auth_me():
    user = current_user()
    if not user:
        session.clear()
        return jsonify({"authenticated": False})
    return jsonify({"authenticated": True, "user": {"id": user.id, "name": user.name, "email": user.email}})

@app.post("/api/auth/signup")
def signup():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    if len(name) < 2 or len(name) > 100:
        return jsonify({"error": "Enter a name between 2 and 100 characters."}), 400
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email) or len(email) > 254:
        return jsonify({"error": "Enter a valid email address."}), 400
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters long."}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "An account with this email already exists. Please log in."}), 409
    user = User(name=name, email=email, password_hash=generate_password_hash(password))
    db.session.add(user)
    db.session.commit()
    session.clear()
    session["user_id"] = user.id
    return jsonify({"message": "Account created successfully.", "user": {"id": user.id, "name": user.name, "email": user.email}}), 201

@app.post("/api/auth/login")
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    user = User.query.filter_by(email=email).first()
    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({"error": "Incorrect email or password."}), 401
    session.clear()
    session["user_id"] = user.id
    return jsonify({"message": "Logged in successfully.", "user": {"id": user.id, "name": user.name, "email": user.email}})

@app.post("/api/auth/logout")
def logout():
    session.clear()
    return jsonify({"message": "Logged out successfully."})

@app.get("/api/grievances")
@login_required
def list_grievances():
    rows = Grievance.query.filter_by(owner_id=session["user_id"]).order_by(Grievance.created_at.desc()).all()
    return jsonify([r.json() for r in rows])

@app.post("/api/grievances")
@login_required
def create_grievance():
    data = request.get_json(silent=True) or {}
    title, desc = (data.get("title") or "").strip(), (data.get("description") or "").strip()
    if not title or not desc:
        return jsonify({"error":"Title and description are required."}), 400
    category, priority = classify(title + " " + desc)
    requested = (data.get("department") or "Auto-detect with AI").strip()
    department = category if requested == "Auto-detect with AI" else requested
    row = Grievance(owner_id=session["user_id"], title=title[:160], description=desc[:5000], category=category if requested == "Auto-detect with AI" else requested,
                    priority=priority, department=department, location=(data.get("location") or "")[:160])
    db.session.add(row); db.session.commit()
    return jsonify(row.json()), 201

@app.patch("/api/grievances/<int:case_id>")
@login_required
def update_grievance(case_id):
    row = Grievance.query.filter_by(id=case_id, owner_id=session["user_id"]).first()
    if not row: return jsonify({"error":"Grievance not found."}), 404
    data = request.get_json(silent=True) or {}
    if data.get("status") in ["Submitted","Under Review","In Progress","Resolved"]:
        row.status = data["status"]
    if data.get("department"): row.department = str(data["department"])[:100]
    db.session.commit()
    return jsonify(row.json())

@app.get("/api/stats")
@login_required
def stats():
    rows = Grievance.query.filter_by(owner_id=session["user_id"]).all()
    return jsonify({"total":len(rows),"pending":sum(x.status in ("Submitted","Under Review") for x in rows),
                    "urgent":sum(x.priority=="High" and x.status!="Resolved" for x in rows),
                    "resolved":sum(x.status=="Resolved" for x in rows)})

with app.app_context():
    db.create_all()
    # Add the ownership column to an existing deployment database without deleting data.
    columns = {column["name"] for column in inspect(db.engine).get_columns("grievances")}
    if "owner_id" not in columns:
        with db.engine.begin() as connection:
            connection.execute(text("ALTER TABLE grievances ADD COLUMN owner_id INTEGER REFERENCES users(id)"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
