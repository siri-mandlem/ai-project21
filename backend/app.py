from __future__ import annotations

import hashlib
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import date
from functools import wraps
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory, session

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:  # pragma: no cover - optional for local SQLite development
    psycopg2 = None
    RealDictCursor = None


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
SQLITE_PATH = os.getenv("SQLITE_PATH", str(ROOT / "study_planner.db"))

app = Flask(__name__, static_folder=str(FRONTEND), static_url_path="/static")
app.config.update(
    SECRET_KEY=os.getenv("SECRET_KEY", secrets.token_hex(32)),
    MAX_CONTENT_LENGTH=1 * 1024 * 1024,
)


def _is_postgres() -> bool:
    return bool(DATABASE_URL) and psycopg2 is not None


def _placeholder_sql(sql: str) -> str:
    return sql.replace("?", "%s") if _is_postgres() else sql


@contextmanager
def connection():
    if _is_postgres():
        conn = psycopg2.connect(DATABASE_URL, sslmode="require")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    else:
        conn = sqlite3.connect(SQLITE_PATH)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def query(sql: str, params=()):
    with connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor) if _is_postgres() else conn.cursor()
        cursor.execute(_placeholder_sql(sql), params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def execute(sql: str, params=(), returning=False):
    with connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor) if _is_postgres() else conn.cursor()
        cursor.execute(_placeholder_sql(sql), params)
        if returning:
            row = cursor.fetchone()
            return dict(row) if row else None
        return cursor.rowcount


def _sqlite_schema(schema: str) -> str:
    return (schema.replace("SERIAL", "INTEGER")
            .replace("VARCHAR(100)", "TEXT")
            .replace("VARCHAR(255)", "TEXT"))


def init_database():
    schema = (ROOT / "database" / "schema.sql").read_text(encoding="utf-8")
    if not _is_postgres():
        schema = _sqlite_schema(schema)
    with connection() as conn:
        cursor = conn.cursor()
        for statement in schema.split(";"):
            statement = statement.strip()
            if statement:
                cursor.execute(statement)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"scrypt${salt.hex()}${digest.hex()}"


def check_password(password: str, stored: str) -> bool:
    try:
        algorithm, salt_hex, digest_hex = stored.split("$", 2)
        if algorithm != "scrypt":
            return False
        digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex), n=2**14, r=8, p=1)
        return secrets.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def current_user_id() -> int | None:
    user_id = session.get("user_id")
    return int(user_id) if user_id else None


def login_required(handler):
    @wraps(handler)
    def wrapped(*args, **kwargs):
        if current_user_id() is None:
            return jsonify({"error": "Authentication required"}), 401
        return handler(*args, **kwargs)
    return wrapped


def payload():
    return request.get_json(silent=True) or request.form.to_dict()


@app.get("/health")
def health():
    return jsonify({"status": "ok", "database": "postgres" if _is_postgres() else "sqlite"})


@app.get("/ready")
def ready():
    return jsonify({"status": "ready"})


@app.post("/api/register")
def register():
    data = payload()
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))
    if len(username) < 3 or len(password) < 8:
        return jsonify({"error": "Username must be 3+ characters and password 8+ characters."}), 400
    if query("SELECT id FROM users WHERE username = ?", (username,)):
        return jsonify({"error": "That username is already registered."}), 409
    user = execute(
        "INSERT INTO users (username, password, role) VALUES (?, ?, ?) RETURNING id, username",
        (username, hash_password(password), "student"),
        returning=True,
    ) if _is_postgres() else None
    if not _is_postgres():
        with connection() as conn:
            cur = conn.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", (username, hash_password(password), "student"))
            user = {"id": cur.lastrowid, "username": username}
    session["user_id"] = user["id"]
    return jsonify({"user": user}), 201


@app.post("/api/login")
def login():
    data = payload()
    username = str(data.get("username", "")).strip()
    user = query("SELECT id, username, password, role FROM users WHERE username = ?", (username,))
    if not user or not check_password(str(data.get("password", "")), user[0]["password"]):
        return jsonify({"error": "Invalid username or password."}), 401
    session["user_id"] = user[0]["id"]
    return jsonify({"user": {key: user[0][key] for key in ("id", "username", "role")}})


@app.post("/api/logout")
def logout():
    session.clear()
    return jsonify({"message": "Logged out"})


@app.get("/api/me")
def me():
    user_id = current_user_id()
    if user_id is None:
        return jsonify({"user": None})
    rows = query("SELECT id, username, role FROM users WHERE id = ?", (user_id,))
    return jsonify({"user": rows[0] if rows else None})


def _resource(table: str, columns: str, order: str = "created_at DESC"):
    return query(f"SELECT {columns} FROM {table} WHERE user_id = ? ORDER BY {order}", (current_user_id(),))


@app.get("/api/subjects")
@login_required
def subjects():
    return jsonify(_resource("subjects", "id, name, color, created_at", "name ASC"))


@app.post("/api/subjects")
@login_required
def create_subject():
    data = payload()
    name = str(data.get("name", "")).strip()
    if not name:
        return jsonify({"error": "Subject name is required."}), 400
    color = str(data.get("color", "#6c63ff"))[:20]
    if _is_postgres():
        row = execute("INSERT INTO subjects (user_id, name, color) VALUES (?, ?, ?) RETURNING id, name, color", (current_user_id(), name, color), True)
    else:
        with connection() as conn:
            cur = conn.execute("INSERT INTO subjects (user_id, name, color) VALUES (?, ?, ?)", (current_user_id(), name, color))
            row = {"id": cur.lastrowid, "name": name, "color": color}
    return jsonify(row), 201


@app.route("/api/subjects/<int:item_id>", methods=["PUT", "DELETE"])
@login_required
def subject_detail(item_id):
    owned = query("SELECT id FROM subjects WHERE id = ? AND user_id = ?", (item_id, current_user_id()))
    if not owned:
        return jsonify({"error": "Subject not found."}), 404
    if request.method == "DELETE":
        execute("DELETE FROM subjects WHERE id = ? AND user_id = ?", (item_id, current_user_id()))
        return jsonify({"message": "Subject deleted"})
    data = payload()
    name = str(data.get("name", "")).strip()
    if not name:
        return jsonify({"error": "Subject name is required."}), 400
    execute("UPDATE subjects SET name = ?, color = ? WHERE id = ? AND user_id = ?", (name, data.get("color", "#6c63ff"), item_id, current_user_id()))
    return jsonify({"message": "Subject updated"})


@app.get("/api/goals")
@login_required
def goals():
    return jsonify(_resource("goals", "id, subject_id, title, target_hours, completed_hours, goal_date", "goal_date ASC"))


@app.post("/api/goals")
@login_required
def create_goal():
    data = payload()
    try:
        subject_id = int(data["subject_id"])
        target_hours = float(data.get("target_hours", 1))
        goal_date = data.get("goal_date") or date.today().isoformat()
    except (KeyError, TypeError, ValueError):
        return jsonify({"error": "Subject, target hours, and date are required."}), 400
    execute("INSERT INTO goals (user_id, subject_id, title, target_hours, completed_hours, goal_date) VALUES (?, ?, ?, ?, 0, ?)", (current_user_id(), subject_id, data.get("title", "Daily study goal"), target_hours, goal_date))
    return jsonify({"message": "Goal created"}), 201


@app.route("/api/goals/<int:item_id>", methods=["PUT", "DELETE"])
@login_required
def goal_detail(item_id):
    if not query("SELECT id FROM goals WHERE id = ? AND user_id = ?", (item_id, current_user_id())):
        return jsonify({"error": "Goal not found."}), 404
    if request.method == "DELETE":
        execute("DELETE FROM goals WHERE id = ? AND user_id = ?", (item_id, current_user_id()))
        return jsonify({"message": "Goal deleted"})
    data = payload()
    execute("UPDATE goals SET completed_hours = ?, target_hours = ?, title = ? WHERE id = ? AND user_id = ?", (float(data.get("completed_hours", 0)), float(data.get("target_hours", 1)), data.get("title", "Daily study goal"), item_id, current_user_id()))
    return jsonify({"message": "Goal updated"})


@app.get("/api/sessions")
@login_required
def sessions():
    return jsonify(_resource("sessions", "id, subject_id, title, session_date, start_time, duration_hours, completed", "session_date ASC, start_time ASC"))


@app.post("/api/sessions")
@login_required
def create_session():
    data = payload()
    required = ("subject_id", "session_date", "start_time", "duration_hours")
    if any(not data.get(key) for key in required):
        return jsonify({"error": "Subject, date, start time, and duration are required."}), 400
    execute("INSERT INTO sessions (user_id, subject_id, title, session_date, start_time, duration_hours, completed) VALUES (?, ?, ?, ?, ?, ?, ?)", (current_user_id(), int(data["subject_id"]), data.get("title", "Study session"), data["session_date"], data["start_time"], float(data["duration_hours"]), bool(data.get("completed", False))))
    return jsonify({"message": "Session scheduled"}), 201


@app.route("/api/sessions/<int:item_id>", methods=["PUT", "DELETE"])
@login_required
def session_detail(item_id):
    if not query("SELECT id FROM sessions WHERE id = ? AND user_id = ?", (item_id, current_user_id())):
        return jsonify({"error": "Session not found."}), 404
    if request.method == "DELETE":
        execute("DELETE FROM sessions WHERE id = ? AND user_id = ?", (item_id, current_user_id()))
        return jsonify({"message": "Session deleted"})
    data = payload()
    execute("UPDATE sessions SET completed = ? WHERE id = ? AND user_id = ?", (bool(data.get("completed")), item_id, current_user_id()))
    return jsonify({"message": "Session updated"})


@app.get("/api/dashboard")
@login_required
def dashboard_data():
    uid = current_user_id()
    summary = query("""
        SELECT
            COALESCE((SELECT SUM(duration_hours) FROM sessions WHERE user_id = ? AND completed = TRUE), 0) AS completed_hours,
            COALESCE((SELECT COUNT(*) FROM sessions WHERE user_id = ? AND completed = FALSE), 0) AS pending_sessions,
            COALESCE((SELECT SUM(target_hours - completed_hours) FROM goals WHERE user_id = ? AND goal_date = CURRENT_DATE), 0) AS pending_goal_hours
    """, (uid, uid, uid))[0]
    if not _is_postgres():
        summary = query("SELECT COALESCE((SELECT SUM(duration_hours) FROM sessions WHERE user_id = ? AND completed = 1), 0) AS completed_hours, COALESCE((SELECT COUNT(*) FROM sessions WHERE user_id = ? AND completed = 0), 0) AS pending_sessions, COALESCE((SELECT SUM(target_hours - completed_hours) FROM goals WHERE user_id = ? AND goal_date = date('now')), 0) AS pending_goal_hours", (uid, uid, uid))[0]
    progress = query("""
        SELECT subjects.name, subjects.color, COALESCE(SUM(sessions.duration_hours), 0) AS study_hours
        FROM subjects LEFT JOIN sessions ON sessions.subject_id = subjects.id AND sessions.completed = TRUE
        WHERE subjects.user_id = ? GROUP BY subjects.id ORDER BY study_hours DESC
    """, (uid,))
    if not _is_postgres():
        progress = query("SELECT subjects.name, subjects.color, COALESCE(SUM(sessions.duration_hours), 0) AS study_hours FROM subjects LEFT JOIN sessions ON sessions.subject_id = subjects.id AND sessions.completed = 1 WHERE subjects.user_id = ? GROUP BY subjects.id ORDER BY study_hours DESC", (uid,))
    return jsonify({"summary": summary, "subject_progress": progress})


@app.route("/", defaults={"page": "index.html"})
@app.route("/<page>")
def frontend(page):
    aliases = {"dashboard": "dashboard.html", "goals": "goals.html", "login": "login.html", "progress": "progress.html", "register": "register.html", "schedule": "schedule.html", "subjects": "subjects.html", "dashboards": "dashboard.html"}
    page = aliases.get(page, page)
    allowed = {"index.html", "dashboard.html", "goals.html", "login.html", "progress.html", "register.html", "schedule.html", "subjects.html"}
    if page not in allowed:
        return send_from_directory(FRONTEND, "index.html")
    return send_from_directory(FRONTEND, page)


with app.app_context():
    init_database()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=False)
