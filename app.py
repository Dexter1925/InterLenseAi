from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_from_directory
from functools import wraps
import os
import uuid
import json
import sqlite3
from datetime import datetime, timedelta
import mimetypes
import ai_engine
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_db_connection, calculate_capability_score, make_public_id, make_entity_id, init_db
from ml_module import predictor
from chatbot import chatbot_engine

app = Flask(__name__)
app.secret_key = "internlens_super_secret_key_1337"

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024 # 16 MB max
ALLOWED_UPLOAD_EXTENSIONS = {"txt", "py", "js", "ts", "tsx", "html", "css", "json", "md", "pdf", "doc", "docx", "ppt", "pptx", "zip", "png", "jpg", "jpeg", "webp"}

# Apply additive migrations before serving requests. This preserves existing
# records while ensuring permanent IDs, requests, badges and audit tables exist.
init_db()

# Authentication helper decorators/functions
def get_logged_in_user():
    if "user_id" in session:
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM Users WHERE id = ?", (session["user_id"],)).fetchone()
        conn.close()
        return user
    return None


def api_role_required(*roles):
    """Session-backed authorization for state-changing production APIs."""
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = get_logged_in_user()
            if not user:
                return jsonify({"error": "Authentication required"}), 401
            if user["role"] not in roles:
                return jsonify({"error": "You do not have permission for this action"}), 403
            return view(user, *args, **kwargs)
        return wrapped
    return decorator


def audit(conn, actor_id, action, entity_type, entity_id, details=""):
    conn.execute("""INSERT INTO AuditLogs (actor_id, action, entity_type, entity_id, details)
                    VALUES (?, ?, ?, ?, ?)""", (actor_id, action, entity_type, str(entity_id), details))


def faculty_can_evaluate_student(conn, faculty_id, student_public_id):
    """Resolve a public Student ID only when it belongs to the faculty's cohort."""
    return conn.execute("""
        SELECT DISTINCT u.id, u.public_id, u.username
        FROM Users u
        JOIN Classroom_Students cs ON cs.student_id = u.id
        JOIN Classrooms c ON c.id = cs.classroom_id
        WHERE u.public_id = ? AND u.role = 'student' AND c.created_by = ?
    """, (student_public_id.strip().upper(), faculty_id)).fetchone()


def save_presentation_prediction(conn, evaluation_db_id, student_id):
    """Persist a presentation-aware prediction without replacing the base model."""
    presentations = conn.execute("""
        SELECT presentation_average FROM PresentationEvaluation
        WHERE student_id = ? AND status = 'SUBMITTED' ORDER BY evaluated_at ASC, id ASC
    """, (student_id,)).fetchall()
    averages = [float(row["presentation_average"]) for row in presentations]
    presentation_average = sum(averages) / len(averages)
    presentation_trend = averages[-1] - averages[-2] if len(averages) > 1 else 0.0
    criteria_row = conn.execute("""
        SELECT AVG(c.marks) AS average_score FROM PresentationEvaluationCriteria c
        JOIN PresentationEvaluation e ON e.id = c.evaluation_id
        WHERE e.student_id = ? AND e.status = 'SUBMITTED'
    """, (student_id,)).fetchone()
    criteria_average = float(criteria_row["average_score"] or presentation_average)
    submission_rows = conn.execute("SELECT marks FROM Submissions WHERE student_id = ? AND marks IS NOT NULL", (student_id,)).fetchall()
    submission_average = sum(row["marks"] for row in submission_rows) / len(submission_rows) if submission_rows else 75.0
    blended_marks = submission_average * 0.75 + presentation_average * 0.25
    attendance_row = conn.execute("SELECT AVG(CASE WHEN status IN ('Present', 'Excused') THEN 100.0 ELSE 0.0 END) AS score FROM Attendance WHERE student_id = ?", (student_id,)).fetchone()
    attendance = float(attendance_row["score"] or 80.0)
    task_row = conn.execute("""
        SELECT COUNT(*) AS total, SUM(CASE WHEN s.status = 'APPROVED' THEN 1 ELSE 0 END) AS completed
        FROM Tasks t JOIN Classroom_Students cs ON cs.classroom_id = t.classroom_id
        LEFT JOIN Submissions s ON s.task_id = t.id AND s.student_id = cs.student_id
        WHERE cs.student_id = ?
    """, (student_id,)).fetchone()
    task_completion = 100.0 * float(task_row["completed"] or 0) / task_row["total"] if task_row["total"] else 75.0
    chat_count = conn.execute("SELECT COUNT(*) FROM ChatbotLogs WHERE student_id = ?", (student_id,)).fetchone()[0]
    prediction = predictor.predict(attendance, task_completion, blended_marks, 0, 60.0, chat_count,
        presentation_marks=presentation_average, criteria_average=criteria_average,
        presentation_trend=presentation_trend, presentation_count=len(averages))
    success_probability = prediction["success_probability"]
    placement_probability = round(max(15.0, min(98.0, success_probability * 0.90 + presentation_average * 0.10)), 2)
    risk_score = round(100.0 - success_probability, 2)
    rating = "Excellent" if success_probability >= 80 else ("Strong" if success_probability >= 65 else ("Developing" if success_probability >= 50 else "At Risk"))
    conn.execute("""
        INSERT INTO PresentationPredictions (evaluation_id, student_id, academic_success_probability, placement_probability,
            performance_rating, risk_score, presentation_average, presentation_trend, presentation_count)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (evaluation_db_id, student_id, success_probability, placement_probability, rating, risk_score,
          presentation_average, presentation_trend, len(averages)))
    return prediction


def save_attachment(file, owner_id, entity_type, entity_id):
    if not file or not file.filename:
        return None
    original_name = secure_filename(file.filename)
    if not original_name or "." not in original_name:
        raise ValueError("A file name with a supported extension is required")
    ext = original_name.rsplit(".", 1)[1].lower()
    if ext not in ALLOWED_UPLOAD_EXTENSIONS:
        raise ValueError("Unsupported file type")
    stored_name = f"{uuid.uuid4().hex}.{ext}"
    file.save(os.path.join(app.config["UPLOAD_FOLDER"], stored_name))
    return {
        "original_name": original_name, "stored_name": stored_name,
        "mime_type": mimetypes.guess_type(original_name)[0] or "application/octet-stream",
        "size_bytes": os.path.getsize(os.path.join(app.config["UPLOAD_FOLDER"], stored_name)),
    }


def is_image_filename(filename):
    return bool(filename and "." in filename and filename.rsplit(".", 1)[1].lower() in {"png", "jpg", "jpeg", "webp"})


def notify_faculty_of_issue(conn, student_id, student_name, issue_type):
    """Create one alert for every faculty member responsible for the student."""
    faculty = conn.execute("""
        SELECT DISTINCT c.created_by
        FROM Classrooms c
        JOIN Classroom_Students cs ON cs.classroom_id = c.id
        WHERE cs.student_id = ?
    """, (student_id,)).fetchall()
    for row in faculty:
        conn.execute(
            "INSERT INTO Notifications (user_id, message, type) VALUES (?, ?, 'alert')",
            (row["created_by"],
             f"Student {student_name} submitted an issue report: {issue_type}. Please review.")
        )

def handle_save_medical_leave(conn, student_id, issue_data):
    assignment_id = issue_data.get("task_id")
    # A chatbot leave request can be general (not tied to one task). Keep it
    # reviewable instead of silently dropping it; use the next available task
    # only to support an optional extension decision.
    if not assignment_id:
        fallback_task = conn.execute("""
            SELECT t.id FROM Tasks t JOIN Classroom_Students cs ON cs.classroom_id = t.classroom_id
            WHERE cs.student_id = ? AND (t.assigned_student_id IS NULL OR t.assigned_student_id = ?)
            ORDER BY t.due_date ASC LIMIT 1
        """, (student_id, student_id)).fetchone()
        assignment_id = fallback_task["id"] if fallback_task else None
        
    existing_pending = conn.execute("""
        SELECT 1 FROM leave_requests 
        WHERE student_id = ? AND assignment_id = ? AND status = 'Pending Faculty Review'
    """, (student_id, assignment_id)).fetchone()
    
    if not existing_pending:
        faculty_row = conn.execute("""
            SELECT c.created_by FROM Classrooms c
            JOIN Tasks t ON t.classroom_id = c.id
            WHERE t.id = ?
        """, (assignment_id,)).fetchone()
        
        faculty_id = faculty_row["created_by"] if faculty_row else None
        if not faculty_id:
            fac_row = conn.execute("""
                SELECT c.created_by FROM Classrooms c
                JOIN Classroom_Students cs ON cs.classroom_id = c.id
                WHERE cs.student_id = ? LIMIT 1
            """, (student_id,)).fetchone()
            faculty_id = fac_row["created_by"] if fac_row else 1
            
        conn.execute("""
            INSERT INTO leave_requests (
                student_id, faculty_id, assignment_id, reason, chatbot_summary, 
                ai_suggested_extension, requested_date, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'Pending Faculty Review', ?, ?)
        """, (
            student_id, faculty_id, assignment_id, 
            issue_data.get("reason"), issue_data.get("chatbot_summary"),
            issue_data.get("ai_suggested_extension"), 
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            datetime.now().strftime("%Y-%m-%d %H:%M")
        ))
        
        student_row = conn.execute("SELECT username, public_id FROM Users WHERE id = ?", (student_id,)).fetchone()
        student_name = student_row["username"] if student_row else "Student"
        student_pub_id = student_row["public_id"] if student_row else f"STU-{student_id}"
        
        task_row = conn.execute("SELECT title FROM Tasks WHERE id = ?", (assignment_id,)).fetchone()
        task_title = task_row["title"] if task_row else "General leave / illness request"
        
        classroom_row = conn.execute("""
            SELECT c.name FROM Classrooms c
            JOIN Tasks t ON t.classroom_id = c.id
            WHERE t.id = ?
        """, (assignment_id,)).fetchone()
        batch_name = classroom_row["name"] if classroom_row else "Default Batch"
        
        notification_msg = (
            f"New Medical/Leave Request:\n"
            f"- Student: {student_name} ({student_pub_id})\n"
            f"- Internship Batch: {batch_name}\n"
            f"- Date & Time: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
            f"- Reason: {issue_data.get('reason')}\n"
            f"- Summary: {issue_data.get('chatbot_summary')}\n"
            f"- Suggested Extension: {issue_data.get('ai_suggested_extension')}\n"
            f"- Priority Level: {issue_data.get('priority')}\n"
            f"- Status: Pending Faculty Review"
        )
        
        conn.execute("INSERT INTO Notifications (user_id, message, type) VALUES (?, ?, 'alert')", (faculty_id, notification_msg))
        conn.execute("INSERT INTO Notifications (user_id, message, type) VALUES (?, ?, 'alert')", (student_id, f"Leave Request Submitted for task '{task_title}'."))
        
        audit(conn, student_id, "leave_request_submitted", "leave_requests", assignment_id, f"Task: {task_title}")

# Context processor to make user and notifications available globally in templates
@app.context_processor
def inject_global_vars():
    user = get_logged_in_user()
    notifications = []
    if user:
        conn = get_db_connection()
        notifications = conn.execute(
            "SELECT * FROM Notifications WHERE user_id = ? ORDER BY created_at DESC LIMIT 5",
            (user["id"],)
        ).fetchall()
        conn.close()
    return dict(current_user=user, notifications=notifications)

# Routes

@app.route("/")
def index():
    user = get_logged_in_user()
    if user:
        if user["role"] == "student":
            return redirect(url_for("student_dashboard"))
        elif user["role"] == "faculty":
            return redirect(url_for("faculty_dashboard"))
        else:
            session.clear()
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        role = request.form.get("role")
        if role not in ("student", "faculty"):
            flash("Select Student or Faculty.", "danger")
            return render_template("login.html")
        
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM Users WHERE email = ? AND role = ?", (email, role)).fetchone()
        conn.close()
        
        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            flash(f"Welcome back, {user['username'].capitalize()}!", "success")
            
            # Create a notification on login
            conn = get_db_connection()
            conn.execute(
                "INSERT INTO Notifications (user_id, message, type) VALUES (?, ?, ?)",
                (user["id"], f"Logged in successfully at {datetime.now().strftime('%H:%M')}", "dashboard")
            )
            conn.commit()
            conn.close()
            
            if role == "student":
                return redirect(url_for("student_dashboard"))
            elif role == "faculty":
                return redirect(url_for("faculty_dashboard"))
        else:
            flash("Invalid credentials or role selection. Please try again.", "danger")
            
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username").strip().lower()
        email = request.form.get("email").strip()
        password = request.form.get("password")
        role = request.form.get("role")
        
        if not username or not email or not password or role not in ("student", "faculty"):
            flash("All fields are required.", "danger")
            return render_template("register.html")
            
        pwd_hash = generate_password_hash(password)
        
        conn = get_db_connection()
        try:
            public_id = make_public_id(role)
            while conn.execute("SELECT 1 FROM Users WHERE public_id = ?", (public_id,)).fetchone():
                public_id = make_public_id(role)
            conn.execute(
                "INSERT INTO Users (username, email, password_hash, role, public_id) VALUES (?, ?, ?, ?, ?)",
                (username, email, pwd_hash, role, public_id)
            )
            conn.commit()
            flash("Registration successful! You can now log in.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Username or Email already registered.", "danger")
        finally:
            conn.close()
            
    return render_template("register.html")

@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email")
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM Users WHERE email = ?", (email,)).fetchone()
        conn.close()
        
        if user:
            flash(f"Password reset link has been dispatched to {email} (Simulated).", "success")
        else:
            flash("Email not found in our directory.", "danger")
            
    return render_template("forgot_password.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.", "info")
    return redirect(url_for("login"))

# --- Student Dashboard ---
@app.route("/student/dashboard")
def student_dashboard():
    user = get_logged_in_user()
    if not user or user["role"] != "student":
        return redirect(url_for("login"))
        
    conn = get_db_connection()
    leave_requests = []
    
    # 1. Classrooms enrolled
    classrooms = conn.execute("""
        SELECT c.* FROM Classrooms c
        JOIN Classroom_Students cs ON c.id = cs.classroom_id
        WHERE cs.student_id = ?
    """, (user["id"],)).fetchall()
    
    classroom_ids = [c["id"] for c in classrooms]
    
    tasks = []
    submissions = []
    attendance_records = []
    risk_level = "Green"
    success_prob = 75.0
    cap_score = 75.0
    score_components = {
        "attendance": 80.0,
        "task": 75.0,
        "marks": 75.0,
        "timeliness": 100.0,
        "engagement": 50.0
    }
    
    if classroom_ids:
        # Use first classroom for detailed stats
        c_id = classroom_ids[0]
        
        # Calculate fresh Capability score
        cap_score = calculate_capability_score(user["id"], c_id)
        
        # Retrieve capability components
        cap_rec = conn.execute("SELECT * FROM CapabilityScores WHERE student_id = ? AND classroom_id = ?", (user["id"], c_id)).fetchone()
        if cap_rec:
            score_components = {
                "attendance": cap_rec["attendance_component"],
                "task": cap_rec["task_component"],
                "marks": cap_rec["marks_component"],
                "timeliness": cap_rec["timeliness_component"],
                "engagement": cap_rec["engagement_component"]
            }
            
        # 2. View Tasks
        tasks = conn.execute("""
            SELECT t.*, s.status, s.marks, s.file_name, s.submitted_at,
                   (SELECT a.stored_name FROM Attachments a WHERE a.entity_type = 'task_image' AND a.entity_id = t.task_code ORDER BY a.id DESC LIMIT 1) AS assignment_image
            FROM Tasks t
            LEFT JOIN Submissions s ON t.id = s.task_id AND s.student_id = ?
            WHERE t.classroom_id = ? AND (t.assigned_student_id IS NULL OR t.assigned_student_id = ?)
            ORDER BY t.due_date ASC
        """, (user["id"], c_id, user["id"])).fetchall()
        
        # 3. View Submissions
        submissions = conn.execute("""
            SELECT s.*, t.title as task_title FROM Submissions s
            JOIN Tasks t ON s.task_id = t.id
            WHERE s.student_id = ?
            ORDER BY s.submitted_at DESC
        """, (user["id"],)).fetchall()
        submissions = [dict(row) for row in submissions]
        for submission in submissions:
            submission["stored_file_name"] = os.path.basename(submission["file_path"] or "")
            submission["is_image"] = is_image_filename(submission["file_name"])
        
        # 4. Attendance
        attendance_records = conn.execute(
            "SELECT * FROM Attendance WHERE student_id = ? AND classroom_id = ? ORDER BY date DESC",
            (user["id"], c_id)
        ).fetchall()
        
        # 5. Risk alerts
        alert = conn.execute("SELECT risk_level FROM RiskAlerts WHERE student_id = ? AND classroom_id = ? AND status='Active'", (user["id"], c_id)).fetchone()
        if alert:
            risk_level = alert["risk_level"]
            
        # 6. Success prediction inputs
        # Attendance %
        present_count = sum(1 for r in attendance_records if r["status"] in ("Present", "Excused"))
        total_attend = len(attendance_records) if attendance_records else 1
        att_pct = (present_count / total_attend) * 100
        
        # Task completion
        all_t = len(tasks) if tasks else 1
        comp_t = sum(1 for t in tasks if t["status"] == "APPROVED")
        tc_pct = (comp_t / all_t) * 100
        
        # Avg marks
        evaluated_subs = [s["marks"] for s in submissions if s["marks"] is not None]
        avg_m = sum(evaluated_subs) / len(evaluated_subs) if evaluated_subs else 75.0
        
        # Sub delays
        delays = 0
        for s in submissions:
            # Simple simulation: 10% chance a submission was late
            if s["id"] % 7 == 0:
                delays += 1
                
        # Chatbot frequency
        chat_count = conn.execute("SELECT COUNT(*) FROM ChatbotLogs WHERE student_id = ?", (user["id"],)).fetchone()[0]
        
        # Apply rejected leave request penalties & approved leave request bonuses to avg_m
        try:
            rejected_count = conn.execute("SELECT COUNT(*) FROM leave_requests WHERE student_id = ? AND status = 'Rejected'", (user["id"],)).fetchone()[0]
            on_time_count = 0
            approved_leaves = conn.execute("""
                SELECT lr.created_at, t.due_date FROM leave_requests lr
                JOIN Tasks t ON lr.assignment_id = t.id
                WHERE lr.student_id = ? AND lr.status = 'Approved'
            """, (user["id"],)).fetchall()
            for l in approved_leaves:
                try:
                    req_dt = datetime.strptime(l["created_at"], "%Y-%m-%d %H:%M")
                    due_dt = datetime.strptime(l["due_date"], "%Y-%m-%d %H:%M")
                    if req_dt <= due_dt:
                        on_time_count += 1
                except:
                    try:
                        req_dt = datetime.fromisoformat(l["created_at"].replace("Z", "+00:00"))
                        due_dt = datetime.strptime(l["due_date"], "%Y-%m-%d %H:%M")
                        if req_dt <= due_dt:
                            on_time_count += 1
                    except:
                        on_time_count += 1
            avg_m = min(100.0, max(0.0, avg_m - (rejected_count * 5) + (on_time_count * 5)))
        except Exception:
            pass

        # Run ML Predictor!
        pred_res = predictor.predict(
            attendance=att_pct,
            task_completion=tc_pct,
            avg_marks=avg_m,
            submission_delays=delays,
            engagement=score_components["engagement"],
            chatbot_frequency=chat_count
        )
        success_prob = pred_res["success_probability"]
        risk_level = pred_res["risk_color"]
        
    try:
        leave_rows = conn.execute("""
            SELECT lr.*, COALESCE(t.title, 'General leave / illness request') as task_title,
                   t.due_date as original_due_date, u.username as faculty_name
            FROM leave_requests lr
            LEFT JOIN Tasks t ON lr.assignment_id = t.id
            JOIN Users u ON lr.faculty_id = u.id
            WHERE lr.student_id = ? ORDER BY lr.created_at DESC
        """, (user["id"],)).fetchall()
        leave_requests = [dict(row) for row in leave_rows]
    except Exception:
        pass
        
    conn.close()
    
    return render_template(
        "student_dashboard.html",
        classrooms=classrooms,
        tasks=tasks,
        submissions=submissions,
        attendance_records=attendance_records,
        risk_level=risk_level,
        success_prob=success_prob,
        cap_score=cap_score,
        score_components=score_components,
        leave_requests=leave_requests
    )

@app.route("/student/submit-task/<int:task_id>", methods=["POST"])
def submit_task(task_id):
    user = get_logged_in_user()
    if not user or user["role"] != "student":
        return redirect(url_for("login"))
        
    if "file" not in request.files:
        flash("No file was selected.", "warning")
        return redirect(url_for("student_dashboard"))
        
    file = request.files["file"]
    if file.filename == "":
        flash("Empty file name.", "warning")
        return redirect(url_for("student_dashboard"))
        
    # Check extension
    allowed_exts = ALLOWED_UPLOAD_EXTENSIONS
    ext = file.filename.rsplit(".", 1)[1].lower() if "." in file.filename else ""
    if ext not in allowed_exts:
        flash("Invalid file format. Upload PDF, Office, ZIP, images, source code, or text.", "danger")
        return redirect(url_for("student_dashboard"))
        
    filename = secure_filename(f"{user['username']}_{uuid.uuid4().hex[:6]}_{file.filename}")
    file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(file_path)
    
    conn = get_db_connection()
    # Only permit submissions for work visible to this authenticated student.
    task = conn.execute("""SELECT t.classroom_id, c.created_by FROM Tasks t
                           JOIN Classroom_Students cs ON cs.classroom_id = t.classroom_id
                           JOIN Classrooms c ON c.id = t.classroom_id
                           WHERE t.id = ? AND cs.student_id = ?
                           AND (t.assigned_student_id IS NULL OR t.assigned_student_id = ?)""",
                        (task_id, user["id"], user["id"])).fetchone()
    if not task:
        conn.close()
        flash("This assignment is not available to your account.", "danger")
        return redirect(url_for("student_dashboard"))
    # Check if submission already exists
    existing = conn.execute("SELECT id FROM Submissions WHERE student_id = ? AND task_id = ?", (user["id"], task_id)).fetchone()
    
    submitted_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    if existing:
        conn.execute("""
            UPDATE Submissions 
            SET file_name = ?, file_path = ?, submitted_at = ?, status = 'PENDING', marks = NULL, evaluator_comment = NULL
            WHERE id = ?
        """, (file.filename, file_path, submitted_at, existing["id"]))
    else:
        conn.execute("""
            INSERT INTO Submissions (task_id, student_id, file_name, file_path, submitted_at, status)
            VALUES (?, ?, ?, ?, ?, 'PENDING')
        """, (task_id, user["id"], file.filename, file_path, submitted_at))
        
    # Log notification
    conn.execute("""
        INSERT INTO Notifications (user_id, message, type)
        VALUES (?, ?, 'dashboard')
    """, (user["id"], f"Submitted assignment: {file.filename}"))
    conn.execute("INSERT INTO Notifications (user_id, message, type) VALUES (?, ?, 'alert')",
                 (task["created_by"], f"New submission from {user['public_id']} for task #{task_id}."))
    audit(conn, user["id"], "submission_created", "task", task_id, file.filename)
    
    conn.commit()
    
    # Recalculate Capability Score
    if task:
        calculate_capability_score(user["id"], task["classroom_id"])
        
    conn.close()
    flash("Task submission logged successfully. Faculty has been alerted.", "success")
    return redirect(url_for("student_dashboard"))

@app.route("/student/join-classroom", methods=["POST"])
def join_classroom():
    user = get_logged_in_user()
    if not user or user["role"] != "student":
        return redirect(url_for("login"))
        
    code = request.form.get("code").strip().upper()
    conn = get_db_connection()
    classroom = conn.execute("SELECT * FROM Classrooms WHERE code = ?", (code,)).fetchone()
    
    if classroom:
        # Check if already joined
        joined = conn.execute("""
            SELECT 1 FROM Classroom_Students WHERE classroom_id = ? AND student_id = ?
        """, (classroom["id"], user["id"])).fetchone()
        
        if joined:
            flash("You are already enrolled in this classroom.", "info")
        else:
            conn.execute("""
                INSERT INTO Classroom_Students (classroom_id, student_id)
                VALUES (?, ?)
            """, (classroom["id"], user["id"]))
            
            # Seed 5 default attendance records for this new student to calculate initial capability score
            for i in range(5):
                date_str = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
                conn.execute("""
                    INSERT INTO Attendance (classroom_id, student_id, date, status)
                    VALUES (?, ?, ?, 'Present')
                """, (classroom["id"], user["id"], date_str))
                
            conn.commit()
            
            # Calculate initial capability
            calculate_capability_score(user["id"], classroom["id"])
            flash(f"Enrolled in {classroom['name']} successfully!", "success")
    else:
        flash("Classroom code not found. Please verify code with Faculty.", "danger")
        
    conn.close()
    return redirect(url_for("student_dashboard"))

# ---------------------------------------------------------------------------
# --- Authenticated chatbot API ---
# ---------------------------------------------------------------------------

@app.route("/api/chat", methods=["POST"])
def api_chat():
    """
    Primary chatbot endpoint called by the React frontend.
    Accepts: { messages: [{role, content}], student_id (optional) }
    Returns: { reply, mode, step, action, issue_data (optional) }
    """
    data = request.get_json(force=True) or {}
    messages = data.get("messages", [])
    user = get_logged_in_user()
    if not user or user["role"] != "student":
        return jsonify({"error": "Student authentication required"}), 401
    student_id = user["id"]
    student_name = user["public_id"]
    student_roll_number = data.get("student_roll_number", "")

    if not isinstance(messages, list) or not messages:
        return jsonify({"error": "messages must contain a user message"}), 400

    # Last user message is what we process
    msg_text = ""
    if messages:
        last = messages[-1]
        if isinstance(last, dict):
            msg_text = last.get("content", "")
        else:
            msg_text = str(last)

    # Context comes only from the authenticated student's records.
    student_context = {}
    conn = get_db_connection()
    if student_id:
        try:
            student = conn.execute("SELECT public_id FROM Users WHERE id = ?", (student_id,)).fetchone()
            if student:
                student_name = student["public_id"]
            student_roll_number = student_roll_number or student_name
            classrooms = conn.execute(
                "SELECT classroom_id FROM Classroom_Students WHERE student_id = ?",
                (student_id,)
            ).fetchall()
            if classrooms:
                c_id = classrooms[0]["classroom_id"]
                overdue = conn.execute("""
                    SELECT COUNT(*) FROM Tasks t
                    LEFT JOIN Submissions s ON t.id = s.task_id AND s.student_id = ?
                    WHERE t.classroom_id = ? AND t.due_date < datetime('now') AND s.id IS NULL
                """, (student_id, c_id)).fetchone()[0]
                student_context["has_overdue_tasks"] = overdue > 0
                last_sub = conn.execute("""
                    SELECT marks FROM Submissions WHERE student_id = ? AND marks IS NOT NULL
                    ORDER BY submitted_at DESC LIMIT 1
                """, (student_id,)).fetchone()
                if last_sub:
                    student_context["last_marks"] = last_sub["marks"]
                    
                try:
                    active_tasks_rows = conn.execute("""
                        SELECT t.id, t.title, t.due_date FROM Tasks t
                        JOIN Classroom_Students cs ON t.classroom_id = cs.classroom_id
                        LEFT JOIN Submissions s ON t.id = s.task_id AND s.student_id = cs.student_id
                        WHERE cs.student_id = ? AND (t.assigned_student_id IS NULL OR t.assigned_student_id = ?)
                        AND (s.status IS NULL OR s.status != 'APPROVED')
                    """, (student_id, student_id)).fetchall()
                    student_context["active_tasks"] = [{"id": r["id"], "title": r["title"], "due_date": r["due_date"]} for r in active_tasks_rows]
                except Exception:
                    pass
        except Exception:
            pass

    # Run hybrid engine
    try:
        bot_res = chatbot_engine.process_message(
            msg_text,
            student_context=student_context,
            student_id=student_id,
            student_name=student_name,
            student_roll_number=student_roll_number
        )
    except Exception as e:
        conn.close()
        return jsonify({"reply": f"I encountered an internal error: {str(e)}", "mode": "normal"}), 200

    reply = bot_res.get("reply", "Sorry, I didn't understand that.")
    action = bot_res.get("action")
    mode = bot_res.get("mode", "normal")
    step = bot_res.get("step", 0)
    issue_data = bot_res.get("issue_data")

    # Log the chat exchange
    try:
        if student_id:
            conn.execute(
                "INSERT INTO ChatbotLogs (student_id, message, reply) VALUES (?, ?, ?)",
                (student_id, msg_text, reply)
            )
    except Exception:
        pass

    # Handle SAVE_STUDENT_ISSUE action
    if action == "SAVE_STUDENT_ISSUE" and issue_data and student_id:
        try:
            conn.execute("""
                INSERT INTO StudentIssues
                    (student_id, student_name, roll_number, issue_type, subject, date_of_incident, description, details, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Pending')
            """, (
                student_id,
                issue_data.get("student_name", student_name),
                issue_data.get("roll_number", student_roll_number),
                issue_data.get("issue_type", "Other"),
                issue_data.get("subject", ""),
                issue_data.get("date_of_incident", ""),
                issue_data.get("description", ""),
                issue_data.get("details", "")
            ))
            # Notify student
            conn.execute(
                "INSERT INTO Notifications (user_id, message, type) VALUES (?, ?, 'alert')",
                (student_id, "Your issue report has been submitted and is pending faculty review.")
            )
            faculty_id = (issue_data.get("faculty_id") or "").upper()
            faculty = conn.execute("SELECT id FROM Users WHERE public_id = ? AND role = 'faculty'", (faculty_id,)).fetchone()
            if faculty:
                leave_id = make_entity_id("LEAVE")
                conn.execute("""INSERT INTO LeaveRequests
                    (request_id, student_id, faculty_id, request_type, incident_date, description)
                    VALUES (?, ?, ?, ?, ?, ?)""", (leave_id, student_id, faculty["id"], issue_data.get("issue_type", "Leave / Illness"), issue_data.get("date_of_incident", ""), issue_data.get("description", "")))
                conn.execute("INSERT INTO Notifications (user_id, message, type) VALUES (?, ?, 'alert')", (faculty["id"], f"New chatbot leave request {leave_id} from {student_name}"))
                audit(conn, student_id, "leave_request_created", "leave_request", leave_id, f"Created by chatbot for {faculty_id}")
            else:
                # Keep the existing classroom faculty notification behavior if
                # the student entered an invalid ID, without losing the report.
                notify_faculty_of_issue(conn, student_id, student_name, issue_data.get("issue_type", "Other"))
            # Clear issue state after saving
            chatbot_engine.clear_state(student_id)
        except Exception as e:
            pass  # Don't crash on DB errors

    elif action == "SAVE_MEDICAL_LEAVE" and issue_data and student_id:
        try:
            handle_save_medical_leave(conn, student_id, issue_data)
        except Exception:
            pass

    elif action == "CREATE_EXTENSION_REQUEST" and student_id:
        try:
            conn.execute(
                "INSERT INTO Notifications (user_id, message, type) VALUES (?, ?, 'alert')",
                (student_id, "Extension request logged.")
            )
        except Exception:
            pass

    conn.commit()
    conn.close()

    return jsonify({
        "reply": reply,
        "mode": mode,
        "step": step,
        "action": action,
        "issue_data": issue_data
    })


# --- Legacy route kept for Flask-session based access (HTML templates) ---
@app.route("/api/chatbot/message", methods=["POST"])
def chatbot_message():
    user = get_logged_in_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(force=True) or {}
    msg_text = data.get("message", "")

    conn = get_db_connection()
    student_context = {}
    classrooms = conn.execute(
        "SELECT classroom_id FROM Classroom_Students WHERE student_id = ?", (user["id"],)
    ).fetchall()
    if classrooms:
        c_id = classrooms[0]["classroom_id"]
        overdue = conn.execute("""
            SELECT COUNT(*) FROM Tasks t
            LEFT JOIN Submissions s ON t.id = s.task_id AND s.student_id = ?
            WHERE t.classroom_id = ? AND t.due_date < datetime('now') AND s.id IS NULL
        """, (user["id"], c_id)).fetchone()[0]
        student_context["has_overdue_tasks"] = overdue > 0
        last_sub = conn.execute("""
            SELECT marks FROM Submissions WHERE student_id = ? AND marks IS NOT NULL
            ORDER BY submitted_at DESC LIMIT 1
        """, (user["id"],)).fetchone()
        if last_sub:
            student_context["last_marks"] = last_sub["marks"]
            
        try:
            active_tasks_rows = conn.execute("""
                SELECT t.id, t.title, t.due_date FROM Tasks t
                JOIN Classroom_Students cs ON t.classroom_id = cs.classroom_id
                LEFT JOIN Submissions s ON t.id = s.task_id AND s.student_id = cs.student_id
                WHERE cs.student_id = ? AND (t.assigned_student_id IS NULL OR t.assigned_student_id = ?)
                AND (s.status IS NULL OR s.status != 'APPROVED')
            """, (user["id"], user["id"])).fetchall()
            student_context["active_tasks"] = [{"id": r["id"], "title": r["title"], "due_date": r["due_date"]} for r in active_tasks_rows]
        except Exception:
            pass

    bot_res = chatbot_engine.process_message(
        msg_text, student_context, student_id=user["id"], student_name=user["username"]
    )
    reply = bot_res.get("reply", "")
    action = bot_res.get("action")

    conn.execute(
        "INSERT INTO ChatbotLogs (student_id, message, reply) VALUES (?, ?, ?)",
        (user["id"], msg_text, reply)
    )
    # The template dashboard uses this legacy endpoint.  Persist its confirmed
    # reports too, rather than making issue reporting a React-only feature.
    issue_data = bot_res.get("issue_data")
    if action == "SAVE_STUDENT_ISSUE" and issue_data:
        conn.execute("""
            INSERT INTO StudentIssues
                (student_id, student_name, roll_number, issue_type, subject, date_of_incident, description, details, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Pending')
        """, (
            user["id"], user["username"], issue_data.get("roll_number", f"Student-{user['id']}"),
            issue_data.get("issue_type", "Other"), issue_data.get("subject", ""),
            issue_data.get("date_of_incident", ""), issue_data.get("description", ""),
            issue_data.get("details", "")
        ))
        conn.execute(
            "INSERT INTO Notifications (user_id, message, type) VALUES (?, ?, 'alert')",
            (user["id"], "Your issue report has been submitted and is pending faculty review.")
        )
        notify_faculty_of_issue(conn, user["id"], user["username"], issue_data.get("issue_type", "Other"))
        chatbot_engine.clear_state(user["id"])
    elif action == "SAVE_MEDICAL_LEAVE" and issue_data:
        try:
            handle_save_medical_leave(conn, user["id"], issue_data)
        except Exception:
            pass
    conn.commit()
    conn.close()
    return jsonify({"reply": reply, "action": action})

@app.route("/api/chatbot/history")
def chatbot_history():
    user = get_logged_in_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
        
    conn = get_db_connection()
    logs = conn.execute("""
        SELECT message, reply, timestamp FROM ChatbotLogs 
        WHERE student_id = ? ORDER BY timestamp ASC LIMIT 50
    """, (user["id"],)).fetchall()
    conn.close()
    
    return jsonify([dict(l) for l in logs])


# ---------------------------------------------------------------------------
# --- Student Issue Report API ---
# ---------------------------------------------------------------------------

@app.route("/api/student-issues", methods=["POST"])
def create_student_issue():
    """Direct REST endpoint to save an issue (used by React as backup)."""
    data = request.get_json(force=True) or {}
    student_id = data.get("student_id")
    if not student_id:
        return jsonify({"error": "student_id required"}), 400

    conn = get_db_connection()
    try:
        conn.execute("""
            INSERT INTO StudentIssues
                (student_id, student_name, roll_number, issue_type, subject, date_of_incident, description, details, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Pending')
        """, (
            student_id,
            data.get("student_name", "Student"),
            data.get("roll_number") or f"Student-{student_id}",
            data.get("issue_type", "Other"),
            data.get("subject", ""),
            data.get("date_of_incident", ""),
            data.get("description", ""),
            data.get("details", "")
        ))
        issue_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            "INSERT INTO Notifications (user_id, message, type) VALUES (?, ?, 'alert')",
            (student_id, "Your issue report has been submitted and is pending faculty review.")
        )
        notify_faculty_of_issue(conn, student_id, data.get("student_name", "Student"), data.get("issue_type", "Other"))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "issue_id": issue_id})
    except Exception as e:
        conn.close()
        return jsonify({"error": str(e)}), 500


@app.route("/api/student-issues/<int:student_id>", methods=["GET"])
def get_student_issues(student_id):
    """Returns all issue reports for a specific student (so they can see faculty replies)."""
    conn = get_db_connection()
    issues = conn.execute(
        "SELECT * FROM StudentIssues WHERE student_id = ? ORDER BY created_at DESC",
        (student_id,)
    ).fetchall()
    conn.close()
    return jsonify([dict(i) for i in issues])


# ---------------------------------------------------------------------------
# --- Faculty Issue Management API ---
# ---------------------------------------------------------------------------

@app.route("/api/faculty/student-issues", methods=["GET"])
def faculty_get_student_issues():
    """Faculty fetches all student issue reports."""
    conn = get_db_connection()
    issues = conn.execute("""
        SELECT si.*, u.email as student_email
        FROM StudentIssues si
        JOIN Users u ON si.student_id = u.id
        ORDER BY si.created_at DESC
    """).fetchall()
    conn.close()
    return jsonify([dict(i) for i in issues])


@app.route("/api/faculty/student-issues/<int:issue_id>", methods=["PUT"])
def faculty_update_student_issue(issue_id):
    """Faculty updates status and optionally adds a reply."""
    data = request.get_json(force=True) or {}
    new_status = data.get("status")  # Accepted | Rejected | Resolved
    faculty_reply = data.get("faculty_reply", "")

    if new_status not in ("Accepted", "Rejected", "Resolved", "Pending"):
        return jsonify({"error": "Invalid status"}), 400

    conn = get_db_connection()
    issue = conn.execute("SELECT * FROM StudentIssues WHERE id = ?", (issue_id,)).fetchone()
    if not issue:
        conn.close()
        return jsonify({"error": "Issue not found"}), 404

    conn.execute("""
        UPDATE StudentIssues SET status = ?, faculty_reply = ? WHERE id = ?
    """, (new_status, faculty_reply, issue_id))

    # Notify the student
    status_label = {"Accepted": "accepted", "Rejected": "rejected", "Resolved": "resolved"}.get(new_status, new_status.lower())
    msg = f"Your issue report ('{issue['issue_type']}') has been {status_label} by faculty."
    if faculty_reply:
        msg += f" Faculty note: {faculty_reply}"
    conn.execute(
        "INSERT INTO Notifications (user_id, message, type) VALUES (?, ?, 'alert')",
        (issue["student_id"], msg)
    )
    conn.commit()
    updated = conn.execute("SELECT * FROM StudentIssues WHERE id = ?", (issue_id,)).fetchone()
    conn.close()
    return jsonify(dict(updated))


@app.route("/api/faculty/issues-count", methods=["GET"])
def faculty_issues_count():
    """Returns count of Pending issues — used for the notification badge."""
    conn = get_db_connection()
    count = conn.execute(
        "SELECT COUNT(*) FROM StudentIssues WHERE status = 'Pending'"
    ).fetchone()[0]
    conn.close()
    return jsonify({"pending_count": count})


# --- Production LMS APIs: permanent IDs, requests, files and audit trail ---
@app.route("/api/me", methods=["GET"])
@api_role_required("student", "faculty")
def api_me(user):
    return jsonify({"id": user["id"], "public_id": user["public_id"], "name": user["username"], "role": user["role"]})


@app.route("/api/faculty/assignments", methods=["POST"])
@api_role_required("faculty")
def create_assignment_by_student_id(user):
    data = request.form if request.form else (request.get_json(silent=True) or {})
    student_public_id = (data.get("student_id") or "").strip().upper()
    title = (data.get("title") or "").strip()
    due_date = (data.get("due_date") or "").strip()
    if not student_public_id or not title or not due_date:
        return jsonify({"error": "student_id, title and due_date are required"}), 400
    conn = get_db_connection()
    student = conn.execute("SELECT id, public_id FROM Users WHERE public_id = ? AND role = 'student'", (student_public_id,)).fetchone()
    if not student:
        conn.close(); return jsonify({"error": "Student ID not found"}), 404
    enrolled = conn.execute("""SELECT cs.classroom_id FROM Classroom_Students cs
                               JOIN Classrooms c ON c.id = cs.classroom_id
                               WHERE cs.student_id = ? AND c.created_by = ? LIMIT 1""", (student["id"], user["id"])).fetchone()
    if not enrolled:
        conn.close(); return jsonify({"error": "Student is not in one of your classrooms"}), 403
    task_code = make_entity_id("TSK")
    conn.execute("""INSERT INTO Tasks (classroom_id, title, description, due_date, task_code, assigned_student_id, created_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""", (enrolled["classroom_id"], title, data.get("description", ""), due_date, task_code, student["id"], user["id"]))
    task_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    attachment = save_attachment(request.files.get("file"), user["id"], "task", task_code)
    if attachment:
        conn.execute("""INSERT INTO Attachments (owner_id, entity_type, entity_id, original_name, stored_name, mime_type, size_bytes)
                        VALUES (?, 'task', ?, ?, ?, ?, ?)""", (user["id"], task_code, *attachment.values()))
    conn.execute("INSERT INTO Notifications (user_id, message, type) VALUES (?, ?, 'assignment')", (student["id"], f"New assignment {task_code}: {title}"))
    audit(conn, user["id"], "assignment_created", "task", task_code, f"Assigned to {student_public_id}")
    conn.commit(); conn.close()
    return jsonify({"success": True, "task_id": task_code, "database_id": task_id}), 201


@app.route("/api/leave-requests", methods=["POST"])
@api_role_required("student")
def create_leave_request(user):
    data = request.form if request.form else (request.get_json(silent=True) or {})
    faculty_public_id = (data.get("faculty_id") or "").strip().upper()
    description = (data.get("description") or "").strip()
    if not faculty_public_id or not description:
        return jsonify({"error": "faculty_id and description are required"}), 400
    conn = get_db_connection()
    faculty = conn.execute("SELECT id, public_id FROM Users WHERE public_id = ? AND role = 'faculty'", (faculty_public_id,)).fetchone()
    if not faculty:
        conn.close(); return jsonify({"error": "Faculty ID not found"}), 404
    request_id = make_entity_id("LEAVE")
    conn.execute("""INSERT INTO LeaveRequests (request_id, student_id, faculty_id, request_type, incident_date, description)
                    VALUES (?, ?, ?, ?, ?, ?)""", (request_id, user["id"], faculty["id"], data.get("request_type", "Leave / Illness"), data.get("incident_date", ""), description))
    attachment = save_attachment(request.files.get("proof"), user["id"], "leave_request", request_id)
    if attachment:
        conn.execute("""INSERT INTO Attachments (owner_id, entity_type, entity_id, original_name, stored_name, mime_type, size_bytes)
                        VALUES (?, 'leave_request', ?, ?, ?, ?, ?)""", (user["id"], request_id, *attachment.values()))
    conn.execute("INSERT INTO Notifications (user_id, message, type) VALUES (?, ?, 'alert')", (faculty["id"], f"New leave request {request_id} from {user['public_id']}"))
    audit(conn, user["id"], "leave_request_created", "leave_request", request_id, f"Faculty {faculty_public_id}")
    conn.commit(); conn.close()
    return jsonify({"success": True, "request_id": request_id}), 201


@app.route("/api/faculty/request-center", methods=["GET"])
@api_role_required("faculty")
def faculty_request_center(user):
    conn = get_db_connection()
    rows = conn.execute("""SELECT lr.*, u.username AS student_name, u.public_id AS student_public_id
                           FROM LeaveRequests lr JOIN Users u ON u.id = lr.student_id
                           WHERE lr.faculty_id = ? ORDER BY lr.created_at DESC""", (user["id"],)).fetchall()
    conn.close(); return jsonify([dict(row) for row in rows])


@app.route("/api/faculty/leave-requests/<request_id>", methods=["PUT"])
@api_role_required("faculty")
def decide_leave_request(user, request_id):
    data = request.get_json(silent=True) or {}
    status = data.get("status")
    if status not in ("Approved", "Rejected", "Resolved"):
        return jsonify({"error": "Invalid status"}), 400
    conn = get_db_connection()
    leave = conn.execute("SELECT * FROM LeaveRequests WHERE request_id = ? AND faculty_id = ?", (request_id, user["id"])).fetchone()
    if not leave:
        conn.close(); return jsonify({"error": "Request not found"}), 404
    reply = (data.get("faculty_reply") or "").strip()
    conn.execute("UPDATE LeaveRequests SET status = ?, faculty_reply = ?, updated_at = CURRENT_TIMESTAMP WHERE request_id = ?", (status, reply, request_id))
    # Release this transaction before recalculation opens its own SQLite connection.
    conn.commit()
    if status == "Approved":
        classrooms = conn.execute("SELECT classroom_id FROM Classroom_Students WHERE student_id = ?", (leave["student_id"],)).fetchall()
        for classroom in classrooms:
            conn.execute("INSERT INTO Attendance (classroom_id, student_id, date, status) VALUES (?, ?, ?, 'Excused')", (classroom["classroom_id"], leave["student_id"], leave["incident_date"] or datetime.now().strftime("%Y-%m-%d")))
        # calculate_capability_score uses its own connection, so persist the
        # attendance updates before it runs.
        conn.commit()
        for classroom in classrooms:
            calculate_capability_score(leave["student_id"], classroom["classroom_id"])
    conn.execute("INSERT INTO Notifications (user_id, message, type) VALUES (?, ?, 'alert')", (leave["student_id"], f"Leave request {request_id} was {status.lower()}. {reply}"))
    audit(conn, user["id"], "leave_request_updated", "leave_request", request_id, status)
    conn.commit(); conn.close(); return jsonify({"success": True})


@app.route("/api/students/<student_public_id>/timeline", methods=["GET"])
@api_role_required("student", "faculty")
def student_timeline(user, student_public_id):
    conn = get_db_connection()
    student = conn.execute("SELECT id, public_id FROM Users WHERE public_id = ? AND role = 'student'", (student_public_id.upper(),)).fetchone()
    if not student:
        conn.close(); return jsonify({"error": "Student not found"}), 404
    if user["role"] == "student" and user["id"] != student["id"]:
        conn.close(); return jsonify({"error": "Not permitted"}), 403
    events = []
    for row in conn.execute("SELECT submitted_at AS occurred_at, file_name AS title, status, 'submission' AS type FROM Submissions WHERE student_id = ?", (student["id"],)).fetchall():
        events.append(dict(row))
    for row in conn.execute("SELECT created_at AS occurred_at, request_id AS title, status, 'leave_request' AS type FROM LeaveRequests WHERE student_id = ?", (student["id"],)).fetchall():
        events.append(dict(row))
    for row in conn.execute("SELECT awarded_at AS occurred_at, title, 'Awarded' AS status, 'badge' AS type FROM StudentBadges WHERE student_id = ?", (student["id"],)).fetchall():
        events.append(dict(row))
    conn.close(); return jsonify(sorted(events, key=lambda event: event["occurred_at"] or "", reverse=True))


@app.route("/api/faculty/assignment-analytics", methods=["GET"])
@api_role_required("faculty")
def faculty_assignment_analytics(user):
    conn = get_db_connection()
    rows = conn.execute("""SELECT t.task_code, t.title, t.due_date, u.public_id AS student_id,
        u.username AS student_name, s.status AS submission_status, s.marks, s.submitted_at
        FROM Tasks t JOIN Users u ON u.id = t.assigned_student_id
        LEFT JOIN Submissions s ON s.task_id = t.id AND s.student_id = u.id
        WHERE t.created_by = ? ORDER BY t.due_date DESC""", (user["id"],)).fetchall()
    conn.close()
    items = [dict(row) for row in rows]
    approved = sum(1 for item in items if item["submission_status"] == "APPROVED")
    submitted = sum(1 for item in items if item["submission_status"])
    return jsonify({"assignments": items, "total": len(items), "submitted": submitted, "approved": approved, "completion_rate": round((approved / len(items) * 100), 1) if items else 0})


# ---------------------------------------------------------------------------
# --- React Frontend Compatibility Routes ---
# These are needed because the React frontend (StudentDashboard, FacultyDashboard)
# call /api/deliverables, /api/tasks, /api/submissions, /api/recommendations.
# The old server.ts used to handle these but now everything routes through Flask.
# ---------------------------------------------------------------------------

# In-memory stores for React-only demo data (not in SQLite, since these
# are the kanban-style UI objects the React frontend manages)
import random

_deliverables = [
    {"id": "del-1", "title": "Mid-Term Performance Review", "info": "Due in 2 days • Neural-Ops Systems", "completed": True, "type": "report"},
    {"id": "del-2", "title": "API Refactor Module", "info": "Due in 4 days • Backend", "completed": False, "type": "code"},
    {"id": "del-3", "title": "Final Reflection Report", "info": "Due in 10 days • Capstone", "completed": False, "type": "report"},
]

_submissions = [
    {"id": "sub-1", "fileName": "Liam_Midterm_Review.pdf", "date": "Jul 10", "size": "2.1 MB", "status": "APPROVED", "type": "pdf", "feedback": "Excellent critical self-evaluation. APPROVED"},
    {"id": "sub-2", "fileName": "API_Refactor_Draft.pdf", "date": "Jul 12", "size": "1.8 MB", "status": "PENDING", "type": "pdf"},
]

_tasks = [
    {"id": "task-1", "studentName": "Liam Chen", "taskName": "API Refactor", "course": "Backend", "submittedAt": "Jul 10", "status": "review", "avatar": "https://lh3.googleusercontent.com/aida-public/AB6AXuD-Edn1Vbn_t7WARRjiMX98R8xIPOv2urtGIlLiUCTmQGit1SRSBpVoIPNkpz7Wou6hRCEselbqjBZvdorIskPdoR6DDKILfXNbRqHfDKbNOpC0ZxXsXYqW2CNGHoVX2rkc5poOsMtnsZXngLbFaTP3eT13CsrOGkzNysmhyorxF-ZFYJhIocRzaeoDLt5btMY8th_HYdtnjGy2W0WKVDc6wOmnoYEkHhuT9QMQllPnJobhMu5ge7TE0vAUxxYxntBGmN6Z9p3NYuE"},
    {"id": "task-2", "studentName": "Sarah Lin", "taskName": "Security Audit", "course": "Security", "submittedAt": "Jul 11", "status": "progress", "avatar": "https://lh3.googleusercontent.com/aida-public/AB6AXuD-Edn1Vbn_t7WARRjiMX98R8xIPOv2urtGIlLiUCTmQGit1SRSBpVoIPNkpz7Wou6hRCEselbqjBZvdorIskPdoR6DDKILfXNbRqHfDKbNOpC0ZxXsXYqW2CNGHoVX2rkc5poOsMtnsZXngLbFaTP3eT13CsrOGkzNysmhyorxF-ZFYJhIocRzaeoDLt5btMY8th_HYdtnjGy2W0WKVDc6wOmnoYEkHhuT9QMQllPnJobhMu5ge7TE0vAUxxYxntBGmN6Z9p3NYuE"},
    {"id": "task-3", "studentName": "Marcus Ray", "taskName": "Data Pipeline", "course": "Data Sci", "submittedAt": "Jul 12", "status": "completed", "avatar": "https://lh3.googleusercontent.com/aida-public/AB6AXuD-Edn1Vbn_t7WARRjiMX98R8xIPOv2urtGIlLiUCTmQGit1SRSBpVoIPNkpz7Wou6hRCEselbqjBZvdorIskPdoR6DDKILfXNbRqHfDKbNOpC0ZxXsXYqW2CNGHoVX2rkc5poOsMtnsZXngLbFaTP3eT13CsrOGkzNysmhyorxF-ZFYJhIocRzaeoDLt5btMY8th_HYdtnjGy2W0WKVDc6wOmnoYEkHhuT9QMQllPnJobhMu5ge7TE0vAUxxYxntBGmN6Z9p3NYuE"},
]

@app.route("/api/deliverables", methods=["GET"])
def get_deliverables():
    return jsonify(_deliverables)

@app.route("/api/deliverables", methods=["POST"])
def add_deliverable():
    data = request.get_json(force=True) or {}
    new_del = {
        "id": f"del-{uuid.uuid4().hex[:6]}",
        "title": data.get("title", "New Deliverable"),
        "info": data.get("info", "Self Assigned"),
        "completed": False,
        "type": "task"
    }
    _deliverables.append(new_del)
    return jsonify(new_del), 201

@app.route("/api/deliverables/<del_id>", methods=["PUT"])
def update_deliverable(del_id):
    data = request.get_json(force=True) or {}
    for d in _deliverables:
        if d["id"] == del_id:
            d["completed"] = data.get("completed", d["completed"])
            return jsonify(d)
    return jsonify({"error": "Not found"}), 404

@app.route("/api/submissions", methods=["GET"])
def get_submissions_react():
    return jsonify(_submissions)

@app.route("/api/submissions", methods=["POST"])
def add_submission_react():
    data = request.get_json(force=True) or {}
    file_name = data.get("fileName", "report.pdf")
    content = data.get("content", "")
    # Run AI grading
    grade_res = {"status": "APPROVED", "feedback": ""}
    try:
        grade_res = ai_engine.handle_grade({"fileName": file_name, "content": content})
    except Exception:
        pass
    new_sub = {
        "id": f"sub-{uuid.uuid4().hex[:6]}",
        "fileName": file_name,
        "date": datetime.now().strftime("%b %d"),
        "size": data.get("size", "2.0 MB"),
        "status": grade_res.get("status", "PENDING"),
        "type": "pdf",
        "feedback": grade_res.get("feedback", "")
    }
    _submissions.insert(0, new_sub)
    return jsonify(new_sub), 201

@app.route("/api/tasks", methods=["GET"])
def get_tasks_react():
    return jsonify(_tasks)

@app.route("/api/tasks", methods=["POST"])
def add_task_react():
    data = request.get_json(force=True) or {}
    new_task = {
        "id": f"task-{uuid.uuid4().hex[:6]}",
        "studentName": data.get("studentName", "Student"),
        "taskName": data.get("taskName", "New Task"),
        "course": data.get("course", "General"),
        "submittedAt": datetime.now().strftime("%b %d"),
        "status": "review",
        "avatar": "https://lh3.googleusercontent.com/aida-public/AB6AXuD-Edn1Vbn_t7WARRjiMX98R8xIPOv2urtGIlLiUCTmQGit1SRSBpVoIPNkpz7Wou6hRCEselbqjBZvdorIskPdoR6DDKILfXNbRqHfDKbNOpC0ZxXsXYqW2CNGHoVX2rkc5poOsMtnsZXngLbFaTP3eT13CsrOGkzNysmhyorxF-ZFYJhIocRzaeoDLt5btMY8th_HYdtnjGy2W0WKVDc6wOmnoYEkHhuT9QMQllPnJobhMu5ge7TE0vAUxxYxntBGmN6Z9p3NYuE"
    }
    _tasks.append(new_task)
    return jsonify(new_task), 201

@app.route("/api/tasks/<task_id>", methods=["PUT"])
def update_task_react(task_id):
    data = request.get_json(force=True) or {}
    for t in _tasks:
        if t["id"] == task_id:
            t["status"] = data.get("status", t["status"])
            return jsonify(t)
    return jsonify({"error": "Not found"}), 404

@app.route("/api/tasks/<task_id>", methods=["DELETE"])
def delete_task_react(task_id):
    global _tasks
    _tasks = [t for t in _tasks if t["id"] != task_id]
    return jsonify({"success": True})

@app.route("/api/recommendations", methods=["GET"])
def get_recommendations():
    active = sum(1 for t in _tasks if t["status"] == "review")
    pending = sum(1 for t in _tasks if t["status"] == "progress")
    completed = sum(1 for t in _tasks if t["status"] == "completed")
    remaining = ", ".join(t["taskName"] for t in _tasks if t["status"] != "completed")[:60]
    try:
        res = ai_engine.handle_recommend({
            "activeCount": active, "pendingCount": pending,
            "completedCount": completed, "remainingDeliverables": remaining
        })
        return jsonify(res)
    except Exception:
        return jsonify({"recommendation": f"Review {pending} pending submissions — {remaining or 'all tasks on track'}."})

# --- Faculty / Admin Dashboard ---
@app.route("/api/faculty/presentation-evaluations/validate-student", methods=["POST"])
@api_role_required("faculty")
def validate_presentation_student(user):
    data = request.get_json(silent=True) or {}
    student_public_id = str(data.get("student_id", "")).strip().upper()
    if not student_public_id:
        return jsonify({"error": "Student ID is required"}), 400
    conn = get_db_connection()
    student = faculty_can_evaluate_student(conn, user["id"], student_public_id)
    conn.close()
    if not student:
        return jsonify({"error": "Student ID is invalid or is not in one of your classrooms."}), 404
    return jsonify({"student_id": student["public_id"], "student_name": student["username"]})


@app.route("/faculty/presentation-evaluations", methods=["GET", "POST"])
def presentation_evaluations():
    user = get_logged_in_user()
    if not user or user["role"] != "faculty":
        return redirect(url_for("login"))
    if request.method == "POST":
        student_public_id = (request.form.get("student_id") or "").strip().upper()
        improvement_note = (request.form.get("improvement_note") or "").strip()
        criteria = request.form.getlist("criterion[]")
        marks = request.form.getlist("marks[]")
        reasons = request.form.getlist("marks_reason[]")
        if not student_public_id or not improvement_note or not criteria or len(criteria) != len(marks) or len(criteria) != len(reasons):
            flash("Student ID, at least one complete criterion, and an improvement note are required.", "danger")
            return redirect(url_for("presentation_evaluations"))
        if len(criteria) > 20:
            flash("A presentation can contain up to 20 criteria.", "danger")
            return redirect(url_for("presentation_evaluations"))
        cleaned = []
        try:
            for criterion, mark, reason in zip(criteria, marks, reasons):
                criterion, reason = criterion.strip(), reason.strip()
                score = float(mark)
                if not criterion or not reason or not 0 <= score <= 100:
                    raise ValueError
                cleaned.append((criterion[:120], score, reason[:1500]))
        except (ValueError, TypeError):
            flash("Each criterion needs a reason and a mark from 0 to 100.", "danger")
            return redirect(url_for("presentation_evaluations"))

        conn = get_db_connection()
        try:
            student = faculty_can_evaluate_student(conn, user["id"], student_public_id)
            if not student:
                flash("Student ID is invalid or is not assigned to your classroom.", "danger")
                return redirect(url_for("presentation_evaluations"))
            evaluation_ref = make_entity_id("PRE")
            while conn.execute("SELECT 1 FROM PresentationEvaluation WHERE evaluation_id = ?", (evaluation_ref,)).fetchone():
                evaluation_ref = make_entity_id("PRE")
            average = round(sum(item[1] for item in cleaned) / len(cleaned), 2)
            show_marks = 1 if request.form.get("show_marks") == "on" else 0
            conn.execute("BEGIN")
            cur = conn.execute("""
                INSERT INTO PresentationEvaluation (evaluation_id, student_id, faculty_id, evaluated_at, improvement_note, show_marks, status, presentation_average)
                VALUES (?, ?, ?, ?, ?, ?, 'SUBMITTED', ?)
            """, (evaluation_ref, student["id"], user["id"], datetime.now().strftime("%Y-%m-%d %H:%M:%S"), improvement_note[:4000], show_marks, average))
            evaluation_db_id = cur.lastrowid
            for position, (criterion, score, reason) in enumerate(cleaned, start=1):
                conn.execute("""INSERT INTO PresentationEvaluationCriteria
                    (evaluation_id, criterion, marks, marks_reason, position) VALUES (?, ?, ?, ?, ?)""",
                    (evaluation_db_id, criterion, score, reason, position))
            prediction = save_presentation_prediction(conn, evaluation_db_id, student["id"])
            audit(conn, user["id"], "presentation_evaluation_submitted", "presentation_evaluation", evaluation_ref,
                  f"student={student['public_id']}; criteria={len(cleaned)}; marks_visible={bool(show_marks)}")
            conn.execute("INSERT INTO Notifications (user_id, message, type) VALUES (?, ?, 'dashboard')",
                (student["id"], "New presentation feedback is available. Your performance profile has been refreshed."))
            conn.commit()
            calculate_capability_score(student["id"], conn.execute("""SELECT c.id FROM Classrooms c JOIN Classroom_Students cs ON cs.classroom_id = c.id
                WHERE c.created_by = ? AND cs.student_id = ? LIMIT 1""", (user["id"], student["id"])).fetchone()["id"])
            flash("Presentation evaluation submitted. Prediction profile and student notification updated.", "success")
        except sqlite3.Error:
            conn.rollback()
            app.logger.exception("Unable to save presentation evaluation")
            flash("The evaluation could not be saved. Please try again.", "danger")
        finally:
            conn.close()
        return redirect(url_for("presentation_evaluations"))

    student_filter = (request.args.get("student_id") or "").strip().upper()
    status_filter = (request.args.get("status") or "").strip().upper()
    date_filter = (request.args.get("date") or "").strip()
    conn = get_db_connection()
    query = """SELECT e.evaluation_id, e.evaluated_at, e.show_marks, e.status, e.presentation_average,
                      u.public_id AS student_public_id, u.username AS student_name
               FROM PresentationEvaluation e JOIN Users u ON u.id = e.student_id WHERE e.faculty_id = ?"""
    params = [user["id"]]
    if student_filter:
        query += " AND u.public_id = ?"
        params.append(student_filter)
    if status_filter in ("DRAFT", "SUBMITTED"):
        query += " AND e.status = ?"
        params.append(status_filter)
    if date_filter:
        query += " AND date(e.evaluated_at) = date(?)"
        params.append(date_filter)
    history = conn.execute(query + " ORDER BY e.evaluated_at DESC", params).fetchall()
    conn.close()
    return render_template("presentation_evaluations.html", history=history, filters={"student_id": student_filter, "status": status_filter, "date": date_filter})


@app.route("/student/presentation-feedback")
def presentation_feedback():
    user = get_logged_in_user()
    if not user or user["role"] != "student":
        return redirect(url_for("login"))
    conn = get_db_connection()
    evaluations = conn.execute("""
        SELECT e.evaluation_id, e.evaluated_at, e.improvement_note, e.show_marks, e.status, u.username AS faculty_name
        FROM PresentationEvaluation e JOIN Users u ON u.id = e.faculty_id
        WHERE e.student_id = ? AND e.status = 'SUBMITTED' ORDER BY e.evaluated_at DESC
    """, (user["id"],)).fetchall()
    feedback = []
    for evaluation in evaluations:
        item = dict(evaluation)
        criteria = conn.execute("""SELECT criterion, marks_reason, marks FROM PresentationEvaluationCriteria
            WHERE evaluation_id = (SELECT id FROM PresentationEvaluation WHERE evaluation_id = ? AND student_id = ?)
            ORDER BY position""", (evaluation["evaluation_id"], user["id"])).fetchall()
        item["criteria"] = [dict(row) for row in criteria]
        feedback.append(item)
    conn.close()
    return render_template("presentation_feedback.html", feedback=feedback)

@app.route("/faculty/dashboard")
def faculty_dashboard():
    user = get_logged_in_user()
    if not user or user["role"] != "faculty":
        return redirect(url_for("login"))
        
    conn = get_db_connection()
    
    # Get classrooms managed by faculty
    classrooms = conn.execute("SELECT * FROM Classrooms WHERE created_by = ?", (user["id"],)).fetchall()
    
    selected_classroom_id = request.args.get("classroom_id")
    if not selected_classroom_id and classrooms:
        selected_classroom_id = classrooms[0]["id"]
        
    students = []
    submissions = []
    tasks = []
    alerts = []
    risk_stats = {"Low": 0, "Medium": 0, "High": 0}
    
    if selected_classroom_id:
        # Fetch enrolled students with capability scores
        students = conn.execute("""
            SELECT u.id, u.public_id, u.username, u.email, cs.score as capability_score, cs.attendance_component, cs.task_component, cs.marks_component, cs.timeliness_component
            FROM Users u
            JOIN Classroom_Students c_s ON u.id = c_s.student_id
            LEFT JOIN CapabilityScores cs ON u.id = cs.student_id AND cs.classroom_id = ?
            WHERE c_s.classroom_id = ?
        """, (selected_classroom_id, selected_classroom_id)).fetchall()
        
        # Calculate/recalculate for everyone to make sure metrics are current
        student_list = []
        for s in students:
            # Re-fetch capability score
            score = calculate_capability_score(s["id"], selected_classroom_id)
            
            # Fetch latest prediction
            # Count late submissions
            s_subs = conn.execute("SELECT marks, id FROM Submissions WHERE student_id = ?", (s["id"],)).fetchall()
            avg_m = sum(r["marks"] for r in s_subs if r["marks"] is not None) / len([r for r in s_subs if r["marks"] is not None]) if [r for r in s_subs if r["marks"] is not None] else 75.0
            
            try:
                rejected_count = conn.execute("SELECT COUNT(*) FROM leave_requests WHERE student_id = ? AND status = 'Rejected'", (s["id"],)).fetchone()[0]
                on_time_count = 0
                approved_leaves = conn.execute("""
                    SELECT lr.created_at, t.due_date FROM leave_requests lr
                    JOIN Tasks t ON lr.assignment_id = t.id
                    WHERE lr.student_id = ? AND lr.status = 'Approved'
                """, (s["id"],)).fetchall()
                for l in approved_leaves:
                    try:
                        req_dt = datetime.strptime(l["created_at"], "%Y-%m-%d %H:%M")
                        due_dt = datetime.strptime(l["due_date"], "%Y-%m-%d %H:%M")
                        if req_dt <= due_dt:
                            on_time_count += 1
                    except:
                        try:
                            req_dt = datetime.fromisoformat(l["created_at"].replace("Z", "+00:00"))
                            due_dt = datetime.strptime(l["due_date"], "%Y-%m-%d %H:%M")
                            if req_dt <= due_dt:
                                on_time_count += 1
                        except:
                            on_time_count += 1
                avg_m = min(100.0, max(0.0, avg_m - (rejected_count * 5) + (on_time_count * 5)))
            except Exception:
                pass

            chat_count = conn.execute("SELECT COUNT(*) FROM ChatbotLogs WHERE student_id = ?", (s["id"],)).fetchone()[0]
            
            pred = predictor.predict(
                attendance=s["attendance_component"] or 80.0,
                task_completion=s["task_component"] or 75.0,
                avg_marks=avg_m,
                submission_delays=0,
                engagement=60.0,
                chatbot_frequency=chat_count
            )
            
            student_list.append({
                "id": s["id"],
                "public_id": s["public_id"],
                "username": s["username"],
                "email": s["email"],
                "capability_score": score,
                "attendance": s["attendance_component"] or 80.0,
                "success_probability": pred["success_probability"],
                "risk_level": pred["risk_level"],
                "risk_color": pred["risk_color"]
            })
            
            # Accumulate risk stats
            risk_cat = "Low" if pred["risk_level"] == "Low Risk" else ("Medium" if pred["risk_level"] == "Medium Risk" else "High")
            risk_stats[risk_cat] += 1
            
        students = student_list
        
        # Fetch tasks
        tasks = conn.execute("SELECT * FROM Tasks WHERE classroom_id = ? ORDER BY due_date ASC", (selected_classroom_id,)).fetchall()
        
        # Fetch submissions
        submissions = conn.execute("""
            SELECT s.*, u.username as student_username, t.title as task_title 
            FROM Submissions s
            JOIN Users u ON s.student_id = u.id
            JOIN Tasks t ON s.task_id = t.id
            WHERE t.classroom_id = ?
            ORDER BY s.submitted_at DESC
        """, (selected_classroom_id,)).fetchall()
        submissions = [dict(row) for row in submissions]
        for submission in submissions:
            submission["stored_file_name"] = os.path.basename(submission["file_path"] or "")
            submission["is_image"] = is_image_filename(submission["file_name"])
        
        # Fetch Risk Alerts
        alerts = conn.execute("""
            SELECT r.*, u.username as student_username 
            FROM RiskAlerts r
            JOIN Users u ON r.student_id = u.id
            WHERE r.classroom_id = ? AND r.status = 'Active'
            ORDER BY r.created_at DESC
        """, (selected_classroom_id,)).fetchall()
        
    leave_requests = []
    try:
        leave_rows = conn.execute("""
            SELECT lr.*, u.username as student_name, u.public_id as student_public_id,
                   COALESCE(t.title, 'General leave / illness request') as task_title, t.due_date as original_due_date
            FROM leave_requests lr
            JOIN Users u ON lr.student_id = u.id
            LEFT JOIN Tasks t ON lr.assignment_id = t.id
            WHERE lr.faculty_id = ? ORDER BY lr.created_at DESC
        """, (user["id"],)).fetchall()
        leave_requests = [dict(row) for row in leave_rows]
    except Exception:
        pass
        
    conn.close()
    
    return render_template(
        "faculty_dashboard.html",
        classrooms=classrooms,
        selected_classroom_id=selected_classroom_id,
        students=students,
        tasks=tasks,
        submissions=submissions,
        alerts=alerts,
        risk_stats=risk_stats,
        leave_requests=leave_requests
    )

@app.route("/faculty/create-classroom", methods=["POST"])
def create_classroom():
    user = get_logged_in_user()
    if not user or user["role"] != "faculty":
        return redirect(url_for("login"))
        
    name = request.form.get("name").strip()
    if not name:
        flash("Classroom name cannot be empty.", "warning")
        return redirect(url_for("faculty_dashboard"))
        
    code = f"LAB{uuid.uuid4().hex[:5].upper()}"
    
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO Classrooms (name, code, created_by) VALUES (?, ?, ?)",
        (name, code, user["id"])
    )
    conn.commit()
    conn.close()
    
    flash(f"Classroom '{name}' created successfully with code: {code}", "success")
    return redirect(url_for("faculty_dashboard"))

@app.route("/faculty/create-task", methods=["POST"])
def create_task():
    user = get_logged_in_user()
    if not user or user["role"] != "faculty":
        return redirect(url_for("login"))
        
    classroom_id = request.form.get("classroom_id")
    title = request.form.get("title").strip()
    description = request.form.get("description").strip()
    due_date = request.form.get("due_date") # Format: YYYY-MM-DDTHH:MM -> replace with space
    
    if due_date:
        due_date = due_date.replace("T", " ")
        
    if not title or not due_date:
        flash("Title and Due Date are mandatory parameters.", "warning")
        return redirect(url_for("faculty_dashboard", classroom_id=classroom_id))
        
    assignment_photo = request.files.get("assignment_photo")
    if assignment_photo and assignment_photo.filename and not is_image_filename(assignment_photo.filename):
        flash("Assignment photo must be a PNG, JPG, JPEG, or WEBP image.", "danger")
        return redirect(url_for("faculty_dashboard", classroom_id=classroom_id))
    conn = get_db_connection()
    student_public_id = (request.form.get("student_id") or "").strip().upper()
    assigned_student_id = None
    if student_public_id:
        student = conn.execute("""SELECT u.id FROM Users u JOIN Classroom_Students cs ON cs.student_id = u.id
                                  WHERE u.public_id = ? AND u.role = 'student' AND cs.classroom_id = ?""",
                               (student_public_id, classroom_id)).fetchone()
        if not student:
            conn.close()
            flash("Student ID is not enrolled in this classroom.", "danger")
            return redirect(url_for("faculty_dashboard", classroom_id=classroom_id))
        assigned_student_id = student["id"]
    task_code = make_entity_id("TSK")
    conn.execute("""
        INSERT INTO Tasks (classroom_id, title, description, due_date, task_code, assigned_student_id, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (classroom_id, title, description, due_date, task_code, assigned_student_id, user["id"]))
    if assignment_photo and assignment_photo.filename:
        image = save_attachment(assignment_photo, user["id"], "task_image", task_code)
        conn.execute("""INSERT INTO Attachments (owner_id, entity_type, entity_id, original_name, stored_name, mime_type, size_bytes)
                     VALUES (?, ?, ?, ?, ?, ?, ?)""",
                     (user["id"], "task_image", task_code, image["original_name"], image["stored_name"], image["mime_type"], image["size_bytes"]))
    
    # Broadcast notification to enrolled students
    students = conn.execute("SELECT student_id FROM Classroom_Students WHERE classroom_id = ?" + (" AND student_id = ?" if assigned_student_id else ""),
                            (classroom_id, assigned_student_id) if assigned_student_id else (classroom_id,)).fetchall()
    for s in students:
        conn.execute("""
            INSERT INTO Notifications (user_id, message, type)
            VALUES (?, ?, 'dashboard')
        """, (s["student_id"], f"New assignment {task_code}: {title}. Due: {due_date}"))
    audit(conn, user["id"], "assignment_created", "task", task_code, f"Assigned to {student_public_id or 'classroom'}")
        
    conn.commit()
    conn.close()
    
    flash(f"Assignment '{title}' has been dispatched to classroom students.", "success")
    return redirect(url_for("faculty_dashboard", classroom_id=classroom_id))

@app.route("/faculty/assign-student", methods=["POST"])
def assign_student():
    user = get_logged_in_user()
    if not user or user["role"] != "faculty":
        return redirect(url_for("login"))
        
    classroom_id = request.form.get("classroom_id")
    student_public_id = request.form.get("student_id", "").strip().upper()
    
    conn = get_db_connection()
    student = conn.execute("SELECT * FROM Users WHERE public_id = ? AND role = 'student'", (student_public_id,)).fetchone()
    
    if student:
        # Check if already joined
        exists = conn.execute("""
            SELECT 1 FROM Classroom_Students WHERE classroom_id = ? AND student_id = ?
        """, (classroom_id, student["id"])).fetchone()
        
        if exists:
            flash("Student is already enrolled.", "info")
        else:
            conn.execute("""
                INSERT INTO Classroom_Students (classroom_id, student_id)
                VALUES (?, ?)
            """, (classroom_id, student["id"]))
            
            # Create some seed attendance
            for i in range(5):
                date_str = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
                conn.execute("""
                    INSERT INTO Attendance (classroom_id, student_id, date, status)
                    VALUES (?, ?, ?, 'Present')
                """, (classroom_id, student["id"], date_str))
                
            conn.commit()
            calculate_capability_score(student["id"], classroom_id)
            flash(f"Enrolled {student['username'].capitalize()} to classroom.", "success")
    else:
        flash("No registered student found with that Student ID.", "danger")
        
    conn.close()
    return redirect(url_for("faculty_dashboard", classroom_id=classroom_id))

@app.route("/faculty/generate-report/<int:classroom_id>")
def generate_report(classroom_id):
    user = get_logged_in_user()
    if not user or user["role"] != "faculty":
        return redirect(url_for("login"))
        
    conn = get_db_connection()
    classroom = conn.execute("SELECT * FROM Classrooms WHERE id = ?", (classroom_id,)).fetchone()
    
    if not classroom:
        conn.close()
        flash("Classroom not found.", "danger")
        return redirect(url_for("faculty_dashboard"))
        
    students = conn.execute("""
        SELECT u.username, u.email, cs.score as capability_score, cs.attendance_component, cs.task_component, cs.marks_component, cs.timeliness_component, cs.engagement_component
        FROM Users u
        JOIN Classroom_Students cs_s ON u.id = cs_s.student_id
        LEFT JOIN CapabilityScores cs ON u.id = cs.student_id AND cs.classroom_id = ?
        WHERE cs_s.classroom_id = ?
    """, (classroom_id, classroom_id)).fetchall()
    
    # Calculate success probabilities dynamically for print layout
    student_report = []
    for s in students:
        pred = predictor.predict(
            attendance=s["attendance_component"] or 80.0,
            task_completion=s["task_component"] or 75.0,
            avg_marks=s["marks_component"] or 75.0,
            submission_delays=0,
            engagement=s["engagement_component"] or 50.0,
            chatbot_frequency=5
        )
        student_report.append({
            "username": s["username"],
            "email": s["email"],
            "capability_score": s["capability_score"] or 70.0,
            "attendance": s["attendance_component"] or 80.0,
            "success_probability": pred["success_probability"],
            "risk_level": pred["risk_level"]
        })
        
    conn.close()
    
    # Print-friendly layout
    return render_template(
        "report_print.html",
        classroom=classroom,
        students=student_report,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M")
    )

# Legacy evaluator URLs are retained as redirects so old bookmarks do not 404;
# evaluation authority now belongs exclusively to Faculty.
@app.route("/evaluator/dashboard")
def evaluator_dashboard():
    return redirect(url_for("faculty_dashboard"))

@app.route("/faculty/grade/<int:submission_id>", methods=["POST"])
@app.route("/evaluator/grade/<int:submission_id>", methods=["POST"])
def grade_submission(submission_id):
    user = get_logged_in_user()
    if not user or user["role"] != "faculty":
        return redirect(url_for("login"))
        
    marks = int(request.form.get("marks", 0))
    comment = request.form.get("comment", "").strip()
    status = request.form.get("status", "APPROVED")
    
    conn = get_db_connection()
    submission = conn.execute("""
        SELECT s.*, t.classroom_id, t.title as task_title, c.created_by FROM Submissions s
        JOIN Tasks t ON s.task_id = t.id
        JOIN Classrooms c ON c.id = t.classroom_id
        WHERE s.id = ?
    """, (submission_id,)).fetchone()
    
    if submission and submission["created_by"] == user["id"]:
        conn.execute("""
            UPDATE Submissions 
            SET marks = ?, evaluator_comment = ?, status = ?
            WHERE id = ?
        """, (marks, comment, status, submission_id))
        
        # Dispatch notification to student
        msg = f"Your assignment '{submission['task_title']}' has been graded. Marks: {marks}/100."
        conn.execute("""
            INSERT INTO Notifications (user_id, message, type)
            VALUES (?, ?, 'alert')
        """, (submission["student_id"], msg))
        audit(conn, user["id"], "submission_reviewed", "submission", submission_id, f"{status}; marks={marks}")
        
        conn.commit()
        
        # Recompute student capability score in this classroom!
        calculate_capability_score(submission["student_id"], submission["classroom_id"])
        
        flash("Faculty review saved, student analytics and ML risk profile updated.", "success")
    else:
        flash("Submission record not found.", "danger")
        
    conn.close()
    return redirect(url_for("faculty_dashboard", classroom_id=submission["classroom_id"] if submission else None))

@app.route("/uploads/<filename>")
def download_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename, as_attachment=True)


@app.route("/files/submissions/<filename>")
def secure_submission_file(filename):
    """Serve a student submission only to its owner or the responsible faculty."""
    user = get_logged_in_user()
    filename = secure_filename(filename)
    if not user or not filename:
        return redirect(url_for("login"))
    conn = get_db_connection()
    submission = conn.execute("""
        SELECT s.student_id, c.created_by FROM Submissions s
        JOIN Tasks t ON t.id = s.task_id JOIN Classrooms c ON c.id = t.classroom_id
        WHERE s.file_path LIKE '%' || ?
    """, (filename,)).fetchone()
    conn.close()
    if not submission or (user["role"] == "student" and submission["student_id"] != user["id"]) or (user["role"] == "faculty" and submission["created_by"] != user["id"]):
        return "Not found", 404
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename, as_attachment=not is_image_filename(filename))


@app.route("/files/task-images/<task_code>/<filename>")
def secure_task_image(task_code, filename):
    """Serve assignment images only to the owning faculty or eligible students."""
    user = get_logged_in_user()
    filename = secure_filename(filename)
    if not user or not filename:
        return redirect(url_for("login"))
    conn = get_db_connection()
    task = conn.execute("""
        SELECT t.assigned_student_id, c.created_by,
               EXISTS(SELECT 1 FROM Classroom_Students cs WHERE cs.classroom_id = t.classroom_id AND cs.student_id = ?) AS enrolled
        FROM Tasks t JOIN Classrooms c ON c.id = t.classroom_id
        JOIN Attachments a ON a.entity_type = 'task_image' AND a.entity_id = t.task_code AND a.stored_name = ?
        WHERE t.task_code = ?
    """, (user["id"], filename, task_code)).fetchone()
    conn.close()
    allowed = task and ((user["role"] == "faculty" and task["created_by"] == user["id"]) or
                        (user["role"] == "student" and task["enrolled"] and (task["assigned_student_id"] is None or task["assigned_student_id"] == user["id"])))
    if not allowed:
        return "Not found", 404
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

@app.route("/api/student/leave-requests", methods=["GET"])
def get_student_leave_requests_api():
    user = get_logged_in_user()
    if not user or user["role"] != "student":
        return jsonify({"error": "Unauthorized"}), 401
    conn = get_db_connection()
    try:
        rows = conn.execute("""
            SELECT lr.*, COALESCE(t.title, 'General leave / illness request') as task_title, t.due_date as original_due_date, u.username as faculty_name
            FROM leave_requests lr
            LEFT JOIN Tasks t ON lr.assignment_id = t.id
            JOIN Users u ON lr.faculty_id = u.id
            WHERE lr.student_id = ? ORDER BY lr.created_at DESC
        """, (user["id"],)).fetchall()
        conn.close()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        conn.close()
        return jsonify({"error": str(e)}), 500

@app.route("/api/student/leave-requests/<int:req_id>/upload-proof", methods=["POST"])
def upload_leave_proof(req_id):
    user = get_logged_in_user()
    if not user or user["role"] != "student":
        return jsonify({"error": "Unauthorized"}), 401
    if "proof" not in request.files:
        flash("No file was uploaded.", "danger")
        return redirect(url_for("student_dashboard"))
    file = request.files["proof"]
    if file.filename == "":
        flash("Empty file uploaded.", "danger")
        return redirect(url_for("student_dashboard"))
        
    conn = get_db_connection()
    try:
        req_row = conn.execute("SELECT * FROM leave_requests WHERE request_id = ? AND student_id = ?", (req_id, user["id"])).fetchone()
        if not req_row:
            conn.close()
            flash("Leave request not found.", "danger")
            return redirect(url_for("student_dashboard"))
            
        attachment = save_attachment(file, user["id"], "leave_requests", req_id)
        if attachment:
            filename = attachment["stored_name"]
            conn.execute("""
                UPDATE leave_requests 
                SET proof_file = ?, updated_at = ?
                WHERE request_id = ?
            """, (filename, datetime.now().strftime("%Y-%m-%d %H:%M"), req_id))
            
            audit(conn, user["id"], "leave_proof_uploaded", "leave_requests", req_id, file.filename)
            conn.commit()
            conn.close()
            flash("Proof document uploaded successfully.", "success")
            return redirect(url_for("student_dashboard"))
        else:
            conn.close()
            flash("Failed to save upload.", "danger")
            return redirect(url_for("student_dashboard"))
    except Exception as e:
        conn.close()
        flash(f"Upload error: {str(e)}", "danger")
        return redirect(url_for("student_dashboard"))

@app.route("/api/faculty/leave-requests/<int:req_id>", methods=["PUT", "POST"])
def decide_leave_request_new(req_id):
    user = get_logged_in_user()
    if not user or user["role"] != "faculty":
        return jsonify({"error": "Unauthorized"}), 401
        
    if request.is_json:
        data = request.get_json() or {}
    else:
        data = request.form or {}
        
    status = data.get("status")
    remarks = data.get("faculty_remark", "").strip()
    new_due_date = data.get("updated_due_date", "").strip()
    if new_due_date:
        new_due_date = new_due_date.replace("T", " ")
        
    if status not in ("Approved", "Rejected"):
        return jsonify({"error": f"Invalid status: {status}"}), 400
        
    conn = get_db_connection()
    try:
        leave = conn.execute("SELECT * FROM leave_requests WHERE request_id = ? AND faculty_id = ?", (req_id, user["id"])).fetchone()
        if not leave:
            conn.close()
            return jsonify({"error": "Leave request not found or not assigned to you"}), 404
            
        conn.execute("""
            UPDATE leave_requests 
            SET status = ?, faculty_remark = ?, updated_due_date = ?, updated_at = ?
            WHERE request_id = ?
        """, (status, remarks, new_due_date if status == "Approved" else leave["updated_due_date"], datetime.now().strftime("%Y-%m-%d %H:%M"), req_id))
        
        task_row = conn.execute("SELECT title, due_date FROM Tasks WHERE id = ?", (leave["assignment_id"],)).fetchone()
        original_due_date = task_row["due_date"] if task_row else "N/A"
        task_title = task_row["title"] if task_row else "Assignment"
        
        if status == "Approved":
            if new_due_date:
                conn.execute("UPDATE Tasks SET due_date = ? WHERE id = ?", (new_due_date, leave["assignment_id"]))
                
            msg = f"Your leave request for '{task_title}' has been approved. New due date: {new_due_date or original_due_date}. Remarks: {remarks}"
            conn.execute("INSERT INTO Notifications (user_id, message, type) VALUES (?, ?, 'alert')", (leave["student_id"], msg))
            conn.execute("INSERT INTO Notifications (user_id, message, type) VALUES (?, ?, 'alert')", (leave["student_id"], f"Due Date Updated for task '{task_title}'."))
            
            audit(conn, user["id"], "leave_request_approved", "leave_requests", req_id, f"Task {leave['assignment_id']} extended to {new_due_date}")
        else:
            msg = f"Your leave request for '{task_title}' has been rejected. Original due date remains unchanged: {original_due_date}. Remarks: {remarks}"
            conn.execute("INSERT INTO Notifications (user_id, message, type) VALUES (?, ?, 'alert')", (leave["student_id"], msg))
            
            audit(conn, user["id"], "leave_request_rejected", "leave_requests", req_id, f"Remarks: {remarks}")
            
        conn.commit()
        
        classrooms = conn.execute("SELECT classroom_id FROM Classroom_Students WHERE student_id = ?", (leave["student_id"],)).fetchall()
        for cr in classrooms:
            calculate_capability_score(leave["student_id"], cr["classroom_id"])
            
        conn.close()
        
        if request.is_json:
            return jsonify({"success": True})
        else:
            flash(f"Leave request has been {status.lower()}.", "success")
            return redirect(url_for("faculty_dashboard"))
    except Exception as e:
        conn.close()
        if request.is_json:
            return jsonify({"error": str(e)}), 500
        else:
            flash(f"Error deciding leave request: {str(e)}", "danger")
            return redirect(url_for("faculty_dashboard"))

@app.route("/api/faculty/leave-requests", methods=["GET"])
def get_faculty_leave_requests_api():
    user = get_logged_in_user()
    if not user or user["role"] != "faculty":
        return jsonify({"error": "Unauthorized"}), 401
    conn = get_db_connection()
    try:
        rows = conn.execute("""
            SELECT lr.*, u.username as student_name, u.public_id as student_public_id, COALESCE(t.title, 'General leave / illness request') as task_title, t.due_date as original_due_date
            FROM leave_requests lr
            JOIN Users u ON lr.student_id = u.id
            LEFT JOIN Tasks t ON lr.assignment_id = t.id
            WHERE lr.faculty_id = ? ORDER BY lr.created_at DESC
        """, (user["id"],)).fetchall()
        conn.close()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        conn.close()
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
