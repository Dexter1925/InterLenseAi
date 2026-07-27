import sqlite3
import os
import secrets
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta

DB_FILE = "internlens.db"

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def make_public_id(role: str) -> str:
    """Stable, non-sequential IDs used in UI and cross-role communication."""
    prefix = {"student": "STU", "faculty": "FAC"}.get(role, "USR")
    return f"{prefix}-{secrets.token_hex(3).upper()}"


def make_entity_id(prefix: str) -> str:
    return f"{prefix}-{secrets.token_hex(4).upper()}"

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Users Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('student', 'faculty', 'evaluator')),
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # 2. Classrooms Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Classrooms (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        code TEXT UNIQUE NOT NULL,
        created_by INTEGER NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (created_by) REFERENCES Users(id)
    )
    """)
    
    # 3. Classroom_Students Table (Join Table)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Classroom_Students (
        classroom_id INTEGER,
        student_id INTEGER,
        PRIMARY KEY (classroom_id, student_id),
        FOREIGN KEY (classroom_id) REFERENCES Classrooms(id),
        FOREIGN KEY (student_id) REFERENCES Users(id)
    )
    """)
    
    # 4. Tasks Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        classroom_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        description TEXT,
        due_date TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (classroom_id) REFERENCES Classrooms(id)
    )
    """)
    
    # 5. Submissions Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Submissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id INTEGER NOT NULL,
        student_id INTEGER NOT NULL,
        file_name TEXT NOT NULL,
        file_path TEXT,
        submitted_at TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'PENDING' CHECK(status IN ('PENDING', 'APPROVED', 'REJECTED')),
        marks INTEGER, -- Faculty score (0-100)
        evaluator_comment TEXT, -- Kept for backwards compatibility; contains faculty feedback.
        size TEXT NOT NULL DEFAULT '1.5 MB',
        FOREIGN KEY (task_id) REFERENCES Tasks(id),
        FOREIGN KEY (student_id) REFERENCES Users(id)
    )
    """)
    
    # 6. Attendance Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        classroom_id INTEGER NOT NULL,
        student_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('Present', 'Absent', 'Excused')),
        FOREIGN KEY (classroom_id) REFERENCES Classrooms(id),
        FOREIGN KEY (student_id) REFERENCES Users(id)
    )
    """)
    
    # 7. CapabilityScores Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS CapabilityScores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        classroom_id INTEGER NOT NULL,
        score REAL DEFAULT 0.0,
        attendance_component REAL DEFAULT 0.0,
        task_component REAL DEFAULT 0.0,
        marks_component REAL DEFAULT 0.0,
        timeliness_component REAL DEFAULT 0.0,
        engagement_component REAL DEFAULT 0.0,
        last_calculated TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (student_id) REFERENCES Users(id),
        FOREIGN KEY (classroom_id) REFERENCES Classrooms(id)
    )
    """)
    
    # 8. RiskAlerts Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS RiskAlerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        classroom_id INTEGER NOT NULL,
        risk_level TEXT NOT NULL CHECK(risk_level IN ('Green', 'Yellow', 'Red')),
        reason TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        status TEXT NOT NULL DEFAULT 'Active',
        FOREIGN KEY (student_id) REFERENCES Users(id),
        FOREIGN KEY (classroom_id) REFERENCES Classrooms(id)
    )
    """)
    
    # 9. ChatbotLogs Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ChatbotLogs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        message TEXT NOT NULL,
        reply TEXT NOT NULL,
        timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (student_id) REFERENCES Users(id)
    )
    """)
    
    # 10. Notifications Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        message TEXT NOT NULL,
        is_read INTEGER DEFAULT 0, -- 0 for false, 1 for true
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        type TEXT DEFAULT 'dashboard',
        FOREIGN KEY (user_id) REFERENCES Users(id)
    )
    """)

    # 11. StudentIssues Table — for hybrid chatbot issue reporting
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS StudentIssues (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        student_name TEXT NOT NULL,
        issue_type TEXT NOT NULL,
        subject TEXT,
        date_of_incident TEXT,
        description TEXT,
        details TEXT,
        status TEXT NOT NULL DEFAULT 'Pending'
            CHECK(status IN ('Pending', 'Accepted', 'Rejected', 'Resolved')),
        faculty_reply TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (student_id) REFERENCES Users(id)
    )
    """)

    # Production LMS extensions. These tables are additive and preserve all
    # original dashboard and chatbot records.
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS LeaveRequests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        request_id TEXT UNIQUE NOT NULL,
        student_id INTEGER NOT NULL,
        faculty_id INTEGER NOT NULL,
        request_type TEXT NOT NULL,
        incident_date TEXT,
        description TEXT NOT NULL,
        proof_path TEXT,
        status TEXT NOT NULL DEFAULT 'Pending'
            CHECK(status IN ('Pending', 'Approved', 'Rejected', 'Resolved')),
        faculty_reply TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(student_id) REFERENCES Users(id),
        FOREIGN KEY(faculty_id) REFERENCES Users(id)
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS AuditLogs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        actor_id INTEGER,
        action TEXT NOT NULL,
        entity_type TEXT NOT NULL,
        entity_id TEXT,
        details TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(actor_id) REFERENCES Users(id)
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Attachments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_id INTEGER NOT NULL,
        entity_type TEXT NOT NULL,
        entity_id TEXT NOT NULL,
        original_name TEXT NOT NULL,
        stored_name TEXT NOT NULL,
        mime_type TEXT,
        size_bytes INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(owner_id) REFERENCES Users(id)
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS StudentBadges (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        badge_key TEXT NOT NULL,
        title TEXT NOT NULL,
        awarded_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(student_id, badge_key),
        FOREIGN KEY(student_id) REFERENCES Users(id)
    )
    """)
    # Presentation evaluations are additive. Public evaluation references are
    # intentionally separate from the internal SQLite primary key so neither
    # student nor faculty URLs expose sequential database identifiers.
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS PresentationEvaluation (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        evaluation_id TEXT UNIQUE NOT NULL,
        student_id INTEGER NOT NULL,
        faculty_id INTEGER NOT NULL,
        evaluated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        improvement_note TEXT NOT NULL,
        show_marks INTEGER NOT NULL DEFAULT 0 CHECK(show_marks IN (0, 1)),
        status TEXT NOT NULL DEFAULT 'SUBMITTED' CHECK(status IN ('DRAFT', 'SUBMITTED')),
        presentation_average REAL NOT NULL DEFAULT 0,
        FOREIGN KEY(student_id) REFERENCES Users(id),
        FOREIGN KEY(faculty_id) REFERENCES Users(id)
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS PresentationEvaluationCriteria (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        evaluation_id INTEGER NOT NULL,
        criterion TEXT NOT NULL,
        marks REAL NOT NULL CHECK(marks >= 0 AND marks <= 100),
        marks_reason TEXT NOT NULL,
        position INTEGER NOT NULL,
        FOREIGN KEY(evaluation_id) REFERENCES PresentationEvaluation(id) ON DELETE CASCADE
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS PresentationPredictions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        evaluation_id INTEGER NOT NULL UNIQUE,
        student_id INTEGER NOT NULL,
        academic_success_probability REAL NOT NULL,
        placement_probability REAL NOT NULL,
        performance_rating TEXT NOT NULL,
        risk_score REAL NOT NULL,
        presentation_average REAL NOT NULL,
        presentation_trend REAL NOT NULL,
        presentation_count INTEGER NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(evaluation_id) REFERENCES PresentationEvaluation(id),
        FOREIGN KEY(student_id) REFERENCES Users(id)
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS leave_requests (
        request_id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        faculty_id INTEGER NOT NULL,
        assignment_id INTEGER,
        reason TEXT,
        chatbot_summary TEXT,
        proof_file TEXT,
        ai_suggested_extension TEXT,
        requested_date TEXT,
        updated_due_date TEXT,
        faculty_remark TEXT,
        status TEXT DEFAULT 'Pending Faculty Review',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (student_id) REFERENCES Users(id),
        FOREIGN KEY (faculty_id) REFERENCES Users(id),
        FOREIGN KEY (assignment_id) REFERENCES Tasks(id)
    )
    """)

    # CREATE TABLE IF NOT EXISTS does not evolve existing installations.
    issue_columns = {row[1] for row in cursor.execute("PRAGMA table_info(StudentIssues)")}
    if "roll_number" not in issue_columns:
        cursor.execute("ALTER TABLE StudentIssues ADD COLUMN roll_number TEXT")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_student_issues_student_created ON StudentIssues(student_id, created_at DESC)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_student_issues_status ON StudentIssues(status)")
    user_columns = {row[1] for row in cursor.execute("PRAGMA table_info(Users)")}
    if "public_id" not in user_columns:
        cursor.execute("ALTER TABLE Users ADD COLUMN public_id TEXT")
    for user in cursor.execute("SELECT id, role FROM Users WHERE public_id IS NULL OR public_id = ''").fetchall():
        public_id = make_public_id(user["role"])
        while cursor.execute("SELECT 1 FROM Users WHERE public_id = ?", (public_id,)).fetchone():
            public_id = make_public_id(user["role"])
        cursor.execute("UPDATE Users SET public_id = ? WHERE id = ?", (public_id, user["id"]))
    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_public_id ON Users(public_id)")
    task_columns = {row[1] for row in cursor.execute("PRAGMA table_info(Tasks)")}
    if "task_code" not in task_columns:
        cursor.execute("ALTER TABLE Tasks ADD COLUMN task_code TEXT")
    if "assigned_student_id" not in task_columns:
        cursor.execute("ALTER TABLE Tasks ADD COLUMN assigned_student_id INTEGER")
    if "created_by" not in task_columns:
        cursor.execute("ALTER TABLE Tasks ADD COLUMN created_by INTEGER")
    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_tasks_task_code ON Tasks(task_code)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_student_due ON Tasks(assigned_student_id, due_date)")
    for task in cursor.execute("SELECT id FROM Tasks WHERE task_code IS NULL OR task_code = ''").fetchall():
        task_code = make_entity_id("TSK")
        while cursor.execute("SELECT 1 FROM Tasks WHERE task_code = ?", (task_code,)).fetchone():
            task_code = make_entity_id("TSK")
        cursor.execute("UPDATE Tasks SET task_code = ? WHERE id = ?", (task_code, task["id"]))
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_leave_requests_faculty_status ON LeaveRequests(faculty_id, status, created_at DESC)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_presentation_evaluations_student_time ON PresentationEvaluation(student_id, evaluated_at DESC)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_presentation_evaluations_faculty_time ON PresentationEvaluation(faculty_id, evaluated_at DESC)")
    
    # Seed Initial Users if table is empty
    cursor.execute("SELECT COUNT(*) FROM Users")
    if cursor.fetchone()[0] == 0:
        # Passwords: 'password123'
        pwd_hash = generate_password_hash("password123")
        
        # Insert Students
        cursor.execute("INSERT INTO Users (username, email, password_hash, role) VALUES (?, ?, ?, ?)",
                       ("liam", "liam@internlens.com", pwd_hash, "student"))
        cursor.execute("INSERT INTO Users (username, email, password_hash, role) VALUES (?, ?, ?, ?)",
                       ("sarah", "sarah@internlens.com", pwd_hash, "student"))
        cursor.execute("INSERT INTO Users (username, email, password_hash, role) VALUES (?, ?, ?, ?)",
                       ("marcus", "marcus@internlens.com", pwd_hash, "student"))
        
        # Insert Faculty
        cursor.execute("INSERT INTO Users (username, email, password_hash, role) VALUES (?, ?, ?, ?)",
                       ("aris", "aris@internlens.com", pwd_hash, "faculty"))
        
        conn.commit()
        
        # Fetch seeded IDs
        cursor.execute("SELECT id, role, username FROM Users")
        users = cursor.fetchall()
        user_map = {u["username"]: u["id"] for u in users}
        
        # Create Classrooms
        cursor.execute("INSERT INTO Classrooms (name, code, created_by) VALUES (?, ?, ?)",
                       ("Neural-Ops Systems Lab 1", "NEURAL101", user_map["aris"]))
        classroom_id = cursor.lastrowid
        
        # Enroll Students
        for s in ["liam", "sarah", "marcus"]:
            cursor.execute("INSERT INTO Classroom_Students (classroom_id, student_id) VALUES (?, ?)",
                           (classroom_id, user_map[s]))
            
        # Create Tasks
        due_date_1 = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d %H:%M")
        due_date_2 = (datetime.now() + timedelta(days=4)).strftime("%Y-%m-%d %H:%M")
        due_date_3 = (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d %H:%M")
        
        cursor.execute("INSERT INTO Tasks (classroom_id, title, description, due_date) VALUES (?, ?, ?, ?)",
                       (classroom_id, "Mid-Term Performance Review", "Reflective report of the first half of the internship.", due_date_1))
        task_1 = cursor.lastrowid
        
        cursor.execute("INSERT INTO Tasks (classroom_id, title, description, due_date) VALUES (?, ?, ?, ?)",
                       (classroom_id, "API Refactor", "Optimizing backend endpoints and query latencies.", due_date_2))
        task_2 = cursor.lastrowid

        cursor.execute("INSERT INTO Tasks (classroom_id, title, description, due_date) VALUES (?, ?, ?, ?)",
                       (classroom_id, "Final Reflection Report", "Complete summary of internship achievements and deliverables.", due_date_3))
        task_3 = cursor.lastrowid
        
        # Submit Tasks
        # Liam submitted Task 1
        cursor.execute("INSERT INTO Submissions (task_id, student_id, file_name, submitted_at, status, marks, evaluator_comment) VALUES (?, ?, ?, ?, ?, ?, ?)",
                       (task_1, user_map["liam"], "Liam_Midterm_Review.pdf", due_date_1, "APPROVED", 85, "Excellent critical self-evaluation."))
        
        # Sarah submitted Task 1 (needs grading)
        cursor.execute("INSERT INTO Submissions (task_id, student_id, file_name, submitted_at, status) VALUES (?, ?, ?, ?, ?)",
                       (task_1, user_map["sarah"], "Sarah_Midterm_Review.docx", due_date_1, "PENDING"))
                       
        # Marcus missed Task 1 (No submission)
        
        # Seed Attendance Records (Last 10 days)
        for s_username in ["liam", "sarah", "marcus"]:
            s_id = user_map[s_username]
            # Liam has 90% attendance, Sarah 80%, Marcus 50%
            attend_prob = 0.9 if s_username == "liam" else (0.8 if s_username == "sarah" else 0.5)
            for i in range(10):
                date_str = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
                status = "Present" if (i % 10 < attend_prob * 10) else "Absent"
                cursor.execute("INSERT INTO Attendance (classroom_id, student_id, date, status) VALUES (?, ?, ?, ?)",
                               (classroom_id, s_id, date_str, status))
        
        conn.commit()

    # Seeded users are inserted after the migration block on a brand-new DB.
    # Assign their public IDs here as well.
    for user in cursor.execute("SELECT id, role FROM Users WHERE public_id IS NULL OR public_id = ''").fetchall():
        public_id = make_public_id(user["role"])
        while cursor.execute("SELECT 1 FROM Users WHERE public_id = ?", (public_id,)).fetchone():
            public_id = make_public_id(user["role"])
        cursor.execute("UPDATE Users SET public_id = ? WHERE id = ?", (public_id, user["id"]))
    # Evaluator is no longer a platform role. Existing evaluator accounts are
    # retired during migration; submissions and historical grades remain intact.
    cursor.execute("DELETE FROM Users WHERE role = 'evaluator'")
    conn.commit()

    # Ensure presentation demo accounts exist
    pwd_hash = generate_password_hash("password123")
    
    # 1. Faculty demo account
    fac = cursor.execute("SELECT id FROM Users WHERE username = 'demofaculty'").fetchone()
    if not fac:
        cursor.execute("INSERT INTO Users (username, email, password_hash, role) VALUES (?, ?, ?, ?)",
                       ("demofaculty", "demofaculty@internlens.com", pwd_hash, "faculty"))
        fac_id = cursor.lastrowid
        fac_pub_id = make_public_id("faculty")
        cursor.execute("UPDATE Users SET public_id = ? WHERE id = ?", (fac_pub_id, fac_id))
    else:
        fac_id = fac["id"]
        
    # 2. Student demo account
    stu = cursor.execute("SELECT id FROM Users WHERE username = 'demostudent'").fetchone()
    if not stu:
        cursor.execute("INSERT INTO Users (username, email, password_hash, role) VALUES (?, ?, ?, ?)",
                       ("demostudent", "demostudent@internlens.com", pwd_hash, "student"))
        stu_id = cursor.lastrowid
        stu_pub_id = make_public_id("student")
        cursor.execute("UPDATE Users SET public_id = ? WHERE id = ?", (stu_pub_id, stu_id))
    else:
        stu_id = stu["id"]
        
    # 3. Create Demo Classroom owned by demofaculty
    class_row = cursor.execute("SELECT id FROM Classrooms WHERE created_by = ?", (fac_id,)).fetchone()
    if not class_row:
        cursor.execute("INSERT INTO Classrooms (name, code, created_by) VALUES (?, ?, ?)",
                       ("Presentation Systems Lab", "PRES101", fac_id))
        classroom_id = cursor.lastrowid
    else:
        classroom_id = class_row["id"]
        
    # 4. Enroll demostudent in this classroom
    enroll_row = cursor.execute("SELECT 1 FROM Classroom_Students WHERE classroom_id = ? AND student_id = ?", (classroom_id, stu_id)).fetchone()
    if not enroll_row:
        cursor.execute("INSERT INTO Classroom_Students (classroom_id, student_id) VALUES (?, ?)", (classroom_id, stu_id))
        
    # 5. Populate Tasks (including one overdue and one upcoming)
    task_count = cursor.execute("SELECT COUNT(*) FROM Tasks WHERE classroom_id = ?", (classroom_id,)).fetchone()[0]
    if task_count == 0:
        due_date_1 = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d %H:%M")
        due_date_2 = (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%d %H:%M")
        cursor.execute("INSERT INTO Tasks (classroom_id, title, description, due_date) VALUES (?, ?, ?, ?)",
                       (classroom_id, "Overdue API Integration", "Complete the REST endpoints.", due_date_1))
        cursor.execute("INSERT INTO Tasks (classroom_id, title, description, due_date) VALUES (?, ?, ?, ?)",
                       (classroom_id, "Upcoming Final Report", "Write the report.", due_date_2))
                       
    conn.commit()
    conn.close()

def calculate_capability_score(student_id, classroom_id):
    """
    30% Attendance + 25% Task Completion + 25% Evaluation Marks + 10% Submission Timeliness + 10% Classroom Engagement
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Attendance Score (30%)
    cursor.execute("SELECT status FROM Attendance WHERE student_id = ? AND classroom_id = ?", (student_id, classroom_id))
    attend_records = cursor.fetchall()
    if attend_records:
        present_count = sum(1 for r in attend_records if r["status"] in ("Present", "Excused"))
        attendance_percentage = (present_count / len(attend_records)) * 100
    else:
        attendance_percentage = 80.0 # Default
        
    # 2. Task Completion (25%)
    # Total tasks in classroom
    cursor.execute("SELECT id, due_date FROM Tasks WHERE classroom_id = ?", (classroom_id,))
    all_tasks = cursor.fetchall()
    
    cursor.execute("SELECT task_id, status, submitted_at FROM Submissions WHERE student_id = ? AND status='APPROVED'", (student_id,))
    completed_submissions = {r["task_id"]: r for r in cursor.fetchall()}
    
    if all_tasks:
        task_completion_percentage = (len(completed_submissions) / len(all_tasks)) * 100
    else:
        task_completion_percentage = 100.0
        
    # 3. Evaluation Marks (25%)
    cursor.execute("SELECT marks FROM Submissions WHERE student_id = ? AND marks IS NOT NULL", (student_id,))
    marks_records = cursor.fetchall()
    if marks_records:
        avg_marks = sum(r["marks"] for r in marks_records) / len(marks_records)
    else:
        avg_marks = 75.0 # Default

    # Presentation performance is an additional academic signal. It is blended
    # with, never substituted for, the existing submission-mark metric.
    presentation_records = cursor.execute("""
        SELECT presentation_average FROM PresentationEvaluation
        WHERE student_id = ? AND status = 'SUBMITTED'
    """, (student_id,)).fetchall()
    if presentation_records:
        presentation_average = sum(r["presentation_average"] for r in presentation_records) / len(presentation_records)
        avg_marks = (avg_marks * 0.75) + (presentation_average * 0.25)

    # Apply penalty for rejected excuses and bonus for approved on-time excuses
    try:
        rejected_count = cursor.execute("SELECT COUNT(*) FROM leave_requests WHERE student_id = ? AND status = 'Rejected'", (student_id,)).fetchone()[0]
        on_time_count = 0
        approved_leaves = cursor.execute("""
            SELECT lr.created_at, t.due_date FROM leave_requests lr
            JOIN Tasks t ON lr.assignment_id = t.id
            WHERE lr.student_id = ? AND lr.status = 'Approved'
        """, (student_id,)).fetchall()
        for l in approved_leaves:
            try:
                # Parse leave request creation date and task due date
                # Format: YYYY-MM-DD HH:MM
                req_dt = datetime.strptime(l["created_at"], "%Y-%m-%d %H:%M")
                due_dt = datetime.strptime(l["due_date"], "%Y-%m-%d %H:%M")
                if req_dt <= due_dt:
                    on_time_count += 1
            except:
                try:
                    # ISO format fallback
                    req_dt = datetime.fromisoformat(l["created_at"].replace("Z", "+00:00"))
                    due_dt = datetime.strptime(l["due_date"], "%Y-%m-%d %H:%M")
                    if req_dt <= due_dt:
                        on_time_count += 1
                except:
                    on_time_count += 1 # Default to on-time if parsing fails
        avg_marks = min(100.0, max(0.0, avg_marks - (rejected_count * 5) + (on_time_count * 5)))
    except Exception as e:
        # Fallback if leave_requests table is not yet created in session
        pass
        
    # 4. Submission Timeliness (10%)
    cursor.execute("""
        SELECT s.submitted_at, t.due_date 
        FROM Submissions s 
        JOIN Tasks t ON s.task_id = t.id 
        WHERE s.student_id = ? AND t.classroom_id = ?
    """, (student_id, classroom_id))
    submission_times = cursor.fetchall()
    
    if submission_times:
        on_time = 0
        for s in submission_times:
            try:
                # Parse times
                sub_dt = datetime.strptime(s["submitted_at"], "%Y-%m-%d %H:%M")
                due_dt = datetime.strptime(s["due_date"], "%Y-%m-%d %H:%M")
                if sub_dt <= due_dt:
                    on_time += 1
            except:
                on_time += 1 # Fallback
        timeliness_percentage = (on_time / len(submission_times)) * 100
    else:
        timeliness_percentage = 100.0
        
    # 5. Classroom Engagement (10%)
    # Chatbot interaction counts + any active submissions
    cursor.execute("SELECT COUNT(*) FROM ChatbotLogs WHERE student_id = ?", (student_id,))
    chat_count = cursor.fetchone()[0]
    engagement_val = min(100, (chat_count * 10) + (len(submission_times) * 20) + 20)
    
    # Calculate overall Capability Score
    cap_score = (
        0.30 * attendance_percentage +
        0.25 * task_completion_percentage +
        0.25 * avg_marks +
        0.10 * timeliness_percentage +
        0.10 * engagement_val
    )
    cap_score = round(min(100.0, max(0.0, cap_score)), 2)

    # Lightweight achievement layer used by the student timeline/dashboard.
    if attendance_percentage >= 90:
        cursor.execute("INSERT OR IGNORE INTO StudentBadges (student_id, badge_key, title) VALUES (?, 'attendance_champion', 'Attendance Champion')", (student_id,))
    if task_completion_percentage >= 100:
        cursor.execute("INSERT OR IGNORE INTO StudentBadges (student_id, badge_key, title) VALUES (?, 'task_finisher', 'Task Finisher')", (student_id,))
    if cap_score >= 85:
        cursor.execute("INSERT OR IGNORE INTO StudentBadges (student_id, badge_key, title) VALUES (?, 'high_achiever', 'High Achiever')", (student_id,))
    
    # Update or insert into CapabilityScores
    cursor.execute("""
        SELECT id FROM CapabilityScores WHERE student_id = ? AND classroom_id = ?
    """, (student_id, classroom_id))
    existing = cursor.fetchone()
    
    if existing:
        cursor.execute("""
            UPDATE CapabilityScores 
            SET score = ?, attendance_component = ?, task_component = ?, marks_component = ?, timeliness_component = ?, engagement_component = ?, last_calculated = CURRENT_TIMESTAMP
            WHERE student_id = ? AND classroom_id = ?
        """, (cap_score, attendance_percentage, task_completion_percentage, avg_marks, timeliness_percentage, engagement_val, student_id, classroom_id))
    else:
        cursor.execute("""
            INSERT INTO CapabilityScores (student_id, classroom_id, score, attendance_component, task_component, marks_component, timeliness_component, engagement_component)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (student_id, classroom_id, cap_score, attendance_percentage, task_completion_percentage, avg_marks, timeliness_percentage, engagement_val))
        
    # Trigger Automated Risk Alerts based on system thresholds:
    # Attendance < 60% OR Average Marks < 50 OR missed tasks > 3 OR Capability Score < 40%
    missed_count = len(all_tasks) - len(submission_times)
    
    risk_level = "Green"
    risk_reasons = []
    
    if attendance_percentage < 60:
        risk_level = "Red"
        risk_reasons.append(f"Low Attendance ({round(attendance_percentage,1)}%)")
    if avg_marks < 50:
        risk_level = "Red"
        risk_reasons.append(f"Low Average Marks ({round(avg_marks,1)})")
    if missed_count >= 3:
        risk_level = "Red"
        risk_reasons.append(f"Missed {missed_count} assignments")
    if cap_score < 40:
        risk_level = "Red" if risk_level != "Red" else "Red"
        risk_reasons.append(f"Critical Capability Score ({cap_score}%)")
        
    if not risk_reasons:
        # Check Medium Risk triggers
        if attendance_percentage < 75:
            risk_level = "Yellow"
            risk_reasons.append("Moderate Attendance drop")
        elif avg_marks < 65:
            risk_level = "Yellow"
            risk_reasons.append("Below-average test grades")
            
    if risk_reasons:
        reason_str = ", ".join(risk_reasons)
        # Create alert if not already exists with same severity
        cursor.execute("""
            SELECT id FROM RiskAlerts WHERE student_id = ? AND classroom_id = ? AND status='Active'
        """, (student_id, classroom_id))
        active_alert = cursor.fetchone()
        
        if active_alert:
            cursor.execute("""
                UPDATE RiskAlerts SET risk_level = ?, reason = ? WHERE id = ?
            """, (risk_level, reason_str, active_alert["id"]))
        else:
            cursor.execute("""
                INSERT INTO RiskAlerts (student_id, classroom_id, risk_level, reason)
                VALUES (?, ?, ?, ?)
            """, (student_id, classroom_id, risk_level, reason_str))
    else:
        # Resolve any active risk alert if student recovered
        cursor.execute("""
            UPDATE RiskAlerts SET status = 'Resolved' WHERE student_id = ? AND classroom_id = ? AND status='Active'
        """, (student_id, classroom_id))
        
    conn.commit()
    conn.close()
    return cap_score

# Execute initialization on load
init_db()
