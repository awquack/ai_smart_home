# app.py - Flask dashboard (Vercel-compatible cloud demo)

import os
import sqlite3
import datetime
import time
from functools import wraps
from flask import (Flask, Response, render_template, redirect,
                   url_for, request, session, jsonify)

SECRET_KEY         = "change_this_to_a_random_string"
DASHBOARD_USERNAME = "admin"
DASHBOARD_PASSWORD = "admin123"
DB_PATH            = os.path.join(os.path.dirname(os.path.abspath(__file__)), "security_events.db")

app = Flask(__name__)
app.secret_key = SECRET_KEY

def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c

def get_event_counts():
    try:
        c = _conn()
        rows = c.execute("SELECT event_type, COUNT(*) as cnt FROM events GROUP BY event_type").fetchall()
        c.close()
        return {r[0]: r[1] for r in rows}
    except Exception:
        return {}

def get_recent_events(limit=50):
    try:
        c = _conn()
        rows = c.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        c.close()
        return [dict(r) for r in rows]
    except Exception:
        return []

def get_events_by_type(event_type, limit=100):
    try:
        c = _conn()
        rows = c.execute("SELECT * FROM events WHERE event_type=? ORDER BY id DESC LIMIT ?",
                         (event_type, limit)).fetchall()
        c.close()
        return [dict(r) for r in rows]
    except Exception:
        return []

def get_known_faces():
    try:
        c = _conn()
        rows = c.execute("SELECT * FROM known_faces").fetchall()
        c.close()
        return [dict(r) for r in rows]
    except Exception:
        return []

def get_hourly_counts():
    try:
        today = datetime.date.today().strftime("%Y-%m-%d")
        c = _conn()
        rows = c.execute(
            "SELECT CAST(strftime('%H', timestamp) AS INTEGER) as hr, COUNT(*) "
            "FROM events WHERE timestamp LIKE ? GROUP BY hr", (f"{today}%",)
        ).fetchall()
        c.close()
        counts = [0] * 24
        for hr, cnt in rows:
            counts[hr] = cnt
        return counts
    except Exception:
        return [0] * 24

def get_daily_counts():
    try:
        c = _conn()
        rows = c.execute(
            "SELECT date(timestamp) as day, COUNT(*) FROM events "
            "WHERE date(timestamp) >= date('now', '-6 days') GROUP BY day ORDER BY day"
        ).fetchall()
        c.close()
        today  = datetime.date.today()
        labels = [(today - datetime.timedelta(days=i)).strftime("%Y-%m-%d") for i in range(6, -1, -1)]
        data   = {r[0]: r[1] for r in rows}
        return {"labels": labels, "values": [data.get(d, 0) for d in labels]}
    except Exception:
        return {"labels": [], "values": []}

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

def generate_mjpeg():
    try:
        import numpy as np, cv2
        img = np.zeros((360, 640, 3), dtype="uint8")
        cv2.putText(img, "Live feed unavailable in cloud demo",
                    (60, 160), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (100, 100, 100), 2)
        cv2.putText(img, "Run locally for live camera stream",
                    (100, 210), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (60, 60, 60), 1)
        _, buf = cv2.imencode(".jpg", img)
        frame = buf.tobytes()
    except Exception:
        frame = b""
    while True:
        yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")
        time.sleep(2)

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        if (request.form.get("username") == DASHBOARD_USERNAME and
                request.form.get("password") == DASHBOARD_PASSWORD):
            session["logged_in"] = True
            return redirect(url_for("dashboard"))
        error = "Invalid username or password."
    return render_template("login.html", error=error)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/")
@login_required
def dashboard():
    counts = get_event_counts()
    total  = sum(counts.values())
    recent = get_recent_events(limit=5)
    return render_template("dashboard.html", counts=counts, total=total, recent=recent)

@app.route("/events")
@login_required
def events():
    filter_type = request.args.get("type", "all")
    rows   = (get_recent_events(limit=100) if filter_type == "all"
              else get_events_by_type(filter_type, limit=100))
    counts = get_event_counts()
    return render_template("events.html", events=rows, filter_type=filter_type, counts=counts)

@app.route("/video_feed")
@login_required
def video_feed():
    return Response(generate_mjpeg(), mimetype="multipart/x-mixed-replace; boundary=frame")

@app.route("/clips")
@login_required
def clips():
    return render_template("clips.html", clips=[])

@app.route("/faces")
@login_required
def faces():
    return render_template("faces.html", faces=get_known_faces())

@app.route("/faces/register", methods=["POST"])
@login_required
def register_face():
    return render_template("faces.html", faces=get_known_faces(),
                           error="Face registration requires local installation.")

@app.route("/faces/delete/<int:face_id>", methods=["POST"])
@login_required
def delete_face(face_id):
    return redirect(url_for("faces"))

@app.route("/status")
@login_required
def status():
    return render_template("status.html", health_rows=[])

@app.route("/api/events")
@login_required
def api_events():
    filter_type = request.args.get("type", "all")
    limit       = int(request.args.get("limit", 50))
    rows = (get_recent_events(limit=limit) if filter_type == "all"
            else get_events_by_type(filter_type, limit=limit))
    return jsonify(rows)

@app.route("/api/chart_data")
@login_required
def api_chart_data():
    return jsonify({"hourly": get_hourly_counts(), "daily": get_daily_counts()})

@app.route("/api/stats")
@login_required
def api_stats():
    counts = get_event_counts()
    return jsonify({
        "counts":       counts,
        "total":        sum(counts.values()),
        "fps":          0,
        "status":       "Cloud Demo - run locally for live detection",
        "running":      False,
        "motion_count": 0,
        "audio_active": False,
        "high_conf":    False,
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
