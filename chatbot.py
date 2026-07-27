"""
InternLens Hybrid Chatbot Engine
---------------------------------
Handles two modes:
  1. NORMAL MODE  — delegates to the Gemini AI engine for study/career queries
  2. ISSUE MODE   — rule-based multi-step workflow for absence/emergency reports

Conversation state is stored per-student in memory (student_id -> state dict).
"""
import re
import ai_engine
from datetime import datetime

# ---------------------------------------------------------------------------
# Keyword triggers that switch the bot into Issue/Rule-Based mode
# ---------------------------------------------------------------------------
ISSUE_KEYWORDS = re.compile(
    r"\b("
    r"leave|absent|absence|"
    r"sick|illness|ill|fever|hospital|"
    r"medical|medicine|doctor|"
    r"emergency|urgent|"
    r"family|relative|death|funeral|"
    r"accident|injury|injured|hurt|"
    r"internet|connectivity|connection|network outage|"
    r"power|electricity|outage|blackout|"
    r"could not submit|unable to submit|couldn't submit|"
    r"could not attend|unable to attend|couldn't attend|"
    r"missed class|missed internship|miss the|missing the|"
    r"couldn't make it|could not make it"
    r")\b",
    re.IGNORECASE
)

MEDICAL_LEAVE_KEYWORDS = re.compile(
    r"\b("
    r"leave|absent|absence|missed|missing|miss the|miss class|miss internship|"
    r"sick|illness|ill|fever|hospital|hospitalization|medical|medicine|doctor|patient|"
    r"emergency|urgent|"
    r"family|relative|death|funeral|"
    r"accident|injury|injured|hurt|"
    r"internet|connectivity|connection|network outage|power|electricity|outage|blackout|"
    r"could not attend|unable to attend|couldn't attend|couldn't make it|could not make it"
    r")\b",
    re.IGNORECASE
)

# Issue type classifier (for DB label)
def classify_issue_type(text: str) -> str:
    t = text.lower()
    if any(k in t for k in ["absent", "absence", "miss"]):
        return "Absence"
    if any(k in t for k in ["sick", "illness", "ill", "fever", "hospital", "medical", "doctor"]):
        return "Medical Emergency"
    if any(k in t for k in ["family", "relative", "death", "funeral", "emergency"]):
        return "Family Emergency"
    if any(k in t for k in ["accident", "injury", "injured", "hurt"]):
        return "Accident / Injury"
    if any(k in t for k in ["internet", "connectivity", "network", "connection"]):
        return "Internet / Connectivity Issue"
    if any(k in t for k in ["power", "electricity", "outage", "blackout"]):
        return "Power Outage"
    if any(k in t for k in ["submit", "assignment", "task"]):
        return "Unable to Submit Assignment"
    if any(k in t for k in ["attend", "internship"]):
        return "Unable to Attend Internship"
    return "Other"


# ---------------------------------------------------------------------------
# Conversation state keys
# Issue flow steps:
#   0 = triggered, asking "what happened"
#   1 = collected description, asking subject/internship
#   2 = collected subject, asking date
#   3 = collected date, asking supporting details
#   4 = collected details, showing summary + asking to notify faculty
#   5 = submitted / complete
# ---------------------------------------------------------------------------
class HybridChatbotEngine:
    def __init__(self):
        # In-memory conversation state per student_id
        # Structure: { student_id: { "mode": "issue"|"normal", "step": int, "data": {...} } }
        self._states: dict = {}

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------
    def process_message(self, message_text: str, student_context: dict = None,
                        student_id: int = None, student_name: str = "Student",
                        student_roll_number: str = "") -> dict:
        """
        Returns:
            reply       – text to display in chat
            action      – optional DB action string
            mode        – "normal" | "issue"
            step        – current issue-flow step (only in issue mode)
            issue_data  – collected issue data (only when step==4, ready to confirm)
        """
        text = message_text.strip()
        lower = text.lower()
        sid = student_id  # may be None in legacy calls

        # ---- Check if student is currently in an issue flow ----------------
        state = self._states.get(sid) if sid else None

        if state and state.get("mode") == "medical_leave":
            return self._handle_medical_leave_step(text, lower, state, sid, student_name, student_context)

        if state and state.get("mode") == "issue":
            return self._handle_issue_step(text, lower, state, sid, student_name)

        # ---- Check if message triggers medical leave flow ------------------
        is_preset_leave = text in ("Start leave request", "Request extension")
        is_keyword_leave = MEDICAL_LEAVE_KEYWORDS.search(text)
        
        if is_preset_leave or is_keyword_leave:
            # Check if there are overdue tasks to pre-select
            overdue_task = None
            active_tasks = student_context.get("active_tasks", []) if student_context else []
            if active_tasks:
                for t in active_tasks:
                    try:
                        due_dt = datetime.strptime(t["due_date"], "%Y-%m-%d %H:%M")
                        if due_dt < datetime.now():
                            overdue_task = t
                            break
                    except:
                        pass
                        
            new_state = {
                "mode": "medical_leave",
                "step": 1,
                "data": {
                    "reason": "",
                    "duration": "",
                    "return_date": "",
                    "proof_available": "",
                    "comments": "",
                    "task_id": overdue_task["id"] if overdue_task else None,
                    "task_title": overdue_task["title"] if overdue_task else "",
                    "chatbot_summary": "",
                    "ai_suggested_extension": "",
                    "priority": "Medium",
                    "student_name": student_name
                }
            }
            if sid:
                self._states[sid] = new_state
                
            reply = (
                "I hope you are doing okay. Let's gather the details of your leave or absence request so I can escalate this to your faculty.\n\n"
                "**Step 1/6 — What is the reason for your absence?** (e.g., illness, family emergency, power/connectivity outage, etc.)"
            )
            if overdue_task:
                reply = (
                    f"I see you have an overdue assignment: **{overdue_task['title']}** (due: {overdue_task['due_date']}).\n"
                    "Let's gather the details of your absence so I can escalate an extension request to your faculty.\n\n"
                    "**Step 1/6 — What is the reason for your absence?** (e.g., illness, family emergency, power/connectivity outage, etc.)"
                )
                
            return {
                "reply": reply,
                "mode": "medical_leave",
                "step": 1,
                "action": None
            }

        # ---- Check if message triggers issue mode --------------------------
        if ISSUE_KEYWORDS.search(text):
            issue_type = classify_issue_type(text)
            new_state = {
                "mode": "issue",
                "step": 1,
                "data": {
                    "issue_type": issue_type,
                    "initial_message": text,
                    "description": "",
                    "subject": "",
                    "date_of_incident": "",
                    "details": "",
                    "faculty_id": "",
                    "student_name": student_name,
                    "roll_number": student_roll_number or f"Student-{sid or 'Unknown'}",
                }
            }
            if sid:
                self._states[sid] = new_state

            return {
                "reply": (
                    f"I understand you're facing a **{issue_type}** situation. "
                    "I'm here to help you report this to your faculty. Let me gather the details.\n\n"
                    "**Step 1/4 — What exactly happened?** Please describe the situation briefly."
                ),
                "mode": "issue",
                "step": 1,
                "action": None
            }

        # ---- Normal mode: delegate to AI -----------------------------------
        return self._handle_normal(text, lower, message_text, student_context, student_name)

    # ------------------------------------------------------------------
    # Issue flow state machine
    # ------------------------------------------------------------------
    def _handle_issue_step(self, text: str, lower: str, state: dict,
                            sid, student_name: str) -> dict:
        step = state["step"]
        data = state["data"]

        # Allow cancelling at any step
        if lower in ("cancel", "stop", "exit", "quit", "no thanks"):
            if sid:
                del self._states[sid]
            return {
                "reply": "Okay, I've cancelled the report. If you need help with anything else, just ask!",
                "mode": "normal",
                "step": 0,
                "action": None
            }

        if step == 1:
            # Collected description
            data["description"] = text
            state["step"] = 2
            return {
                "reply": (
                    "Got it. **Step 2/4 — Which subject or internship** was affected?\n"
                    "(e.g., *Python Lab, Neural-Ops Systems internship, Database module…*)"
                ),
                "mode": "issue",
                "step": 2,
                "action": None
            }

        elif step == 2:
            # Collected subject
            data["subject"] = text
            state["step"] = 3
            return {
                "reply": (
                    "Noted. **Step 3/4 — What is the date of the incident?**\n"
                    "(e.g., *14 July 2026* or *today*)"
                ),
                "mode": "issue",
                "step": 3,
                "action": None
            }

        elif step == 3:
            # Collected date
            data["date_of_incident"] = text
            state["step"] = 4
            return {
                "reply": (
                    "Thank you. **Step 4/4 — Any supporting details?**\n"
                    "(e.g., doctor's note reference, proof link, or type *none* to skip)"
                ),
                "mode": "issue",
                "step": 4,
                "action": None
            }

        elif step == 4:
            # Collected details → show confirmation summary
            data["details"] = text if lower != "none" else "No additional details provided."
            state["step"] = 5
            return {
                "reply": "Please enter the Faculty ID to notify (for example, FAC-XXXXXX).",
                "mode": "issue", "step": 5, "action": None
            }

        elif step == 5:
            data["faculty_id"] = text.upper().strip()
            state["step"] = 6  # Waiting for YES / NO
            summary = (
                "Here is the **Issue Report Summary**:\n\n"
                f"📋 **Type:** {data['issue_type']}\n"
                f"📝 **Description:** {data['description']}\n"
                f"📚 **Subject/Internship:** {data['subject']}\n"
                f"📅 **Date:** {data['date_of_incident']}\n"
                f"🔍 **Details:** {data['details']}\n\n"
                f"**Faculty ID:** {data['faculty_id']}\n\n"
                "**Would you like me to notify your faculty about this?**\n"
                "Reply **YES** to submit the report or **NO** to cancel."
            )
            return {
                "reply": summary,
                "mode": "issue",
                "step": 6,
                "issue_data": dict(data),
                "action": None
            }

        elif step == 6:
            # Student replied YES or NO to "notify faculty?"
            if lower in ("yes", "y", "yeah", "yep", "sure", "ok", "okay", "submit", "confirm"):
                state["step"] = 6
                return {
                    "reply": (
                        "✅ **Report submitted successfully!** Your faculty has been notified.\n\n"
                        "The issue has been logged as **Pending** and will be reviewed shortly. "
                        "You can check the faculty's response here in the chatbot once they respond."
                    ),
                    # Persistence happens in the API before this response is
                    # returned, so the UI can exit the issue workflow now.
                    "mode": "normal",
                    "step": 0,
                    "issue_data": dict(data),
                    "action": "SAVE_STUDENT_ISSUE"
                }
            else:
                # NO / any other answer — cancel
                if sid and sid in self._states:
                    del self._states[sid]
                return {
                    "reply": "Understood. The report has been **cancelled** and nothing was submitted to faculty. Let me know if you need anything else!",
                    "mode": "normal",
                    "step": 0,
                    "action": None
                }

        elif step == 6:
            # After submission, go back to normal mode
            if sid and sid in self._states:
                del self._states[sid]
            return self._handle_normal(text, lower, text, None, student_name)

        # Fallback
        return {"reply": "I'm not sure what step we're on. Let's start over — type your message again.", "mode": "normal", "action": None}

    def _handle_medical_leave_step(self, text: str, lower: str, state: dict,
                                   sid, student_name: str, student_context: dict) -> dict:
        step = state["step"]
        data = state["data"]

        # Allow cancelling at any step
        if lower in ("cancel", "stop", "exit", "quit", "no thanks"):
            if sid:
                self._states.pop(sid, None)
            return {
                "reply": "Okay, I've cancelled the leave request. If you need help with anything else, just ask!",
                "mode": "normal",
                "step": 0,
                "action": None
            }

        if step == 1:
            data["reason"] = text
            state["step"] = 2
            return {
                "reply": "Got it. **Step 2/6 — What is the expected duration of your absence?** (e.g., 2 days, 1 week, today only)",
                "mode": "medical_leave",
                "step": 2,
                "action": None
            }

        elif step == 2:
            data["duration"] = text
            state["step"] = 3
            return {
                "reply": "Thank you. **Step 3/6 — What is your expected return date?** (e.g., 20 July 2026, tomorrow)",
                "mode": "medical_leave",
                "step": 3,
                "action": None
            }

        elif step == 3:
            data["return_date"] = text
            state["step"] = 4
            return {
                "reply": "**Step 4/6 — Is medical or supporting proof available?** (e.g., doctor's note, outage report, screenshot)\n\nPlease reply **YES** or **NO**.",
                "mode": "medical_leave",
                "step": 4,
                "action": None
            }

        elif step == 4:
            if lower in ("yes", "y", "yeah", "yep", "sure", "ok", "okay"):
                data["proof_available"] = "Yes"
            else:
                data["proof_available"] = "No"
            state["step"] = 5
            return {
                "reply": "**Step 5/6 — Do you have any additional comments?** (Type **none** or **no** to skip)",
                "mode": "medical_leave",
                "step": 5,
                "action": None
            }

        elif step == 5:
            data["comments"] = text if lower not in ("none", "no") else "No additional comments."
            
            # If task was already pre-selected (overdue task), we can skip asking and go to summary!
            active_tasks = student_context.get("active_tasks", []) if student_context else []
            if data["task_id"] and any(t["id"] == data["task_id"] for t in active_tasks):
                return self._transition_to_leave_summary(state, sid, active_tasks)
            
            state["step"] = 6
            task_list_str = ""
            if active_tasks:
                task_list_str = "\n".join([f"- **{t['title']}** (ID: {t['id']})" for t in active_tasks])
                reply = (
                    "Got it. **Step 6/6 — Which assignment/task is this request for?**\n\n"
                    f"Here are your active assignments:\n{task_list_str}\n\n"
                    "Please type the **Assignment Title** or **ID** to select it."
                )
            else:
                reply = (
                    "Got it. **Step 6/6 — Which assignment/task is this request for?**\n\n"
                    "Please type the **Assignment Title** to select it."
                )
            return {
                "reply": reply,
                "mode": "medical_leave",
                "step": 6,
                "action": None
            }

        elif step == 6:
            active_tasks = student_context.get("active_tasks", []) if student_context else []
            selected_task = None
            for t in active_tasks:
                if str(t["id"]) == text or t["title"].lower() in lower or lower in t["title"].lower():
                    selected_task = t
                    break
            if selected_task:
                data["task_id"] = selected_task["id"]
                data["task_title"] = selected_task["title"]
            else:
                data["task_id"] = None
                data["task_title"] = text
                
            return self._transition_to_leave_summary(state, sid, active_tasks)

        elif step == 7:
            if lower in ("yes", "y", "yeah", "yep", "sure", "ok", "okay", "submit", "confirm"):
                if sid in self._states:
                    self._states.pop(sid, None)
                return {
                    "reply": (
                        "✅ **Medical/Leave request submitted successfully!**\n\n"
                        "Your faculty has been notified and the request is set to **Pending Faculty Review**. "
                        "You can monitor the status on your student dashboard under the 'Leave Request Status' card. "
                        "If you marked that proof is available, please upload it on the dashboard card."
                    ),
                    "mode": "normal",
                    "step": 0,
                    "issue_data": dict(data),
                    "action": "SAVE_MEDICAL_LEAVE"
                }
            else:
                if sid in self._states:
                    self._states.pop(sid, None)
                return {
                    "reply": "Understood. The leave request has been **cancelled** and nothing was submitted to faculty.",
                    "mode": "normal",
                    "step": 0,
                    "action": None
                }

        return {"reply": "I'm not sure what step we're on. Let's start over.", "mode": "normal", "action": None}

    def _transition_to_leave_summary(self, state: dict, sid, active_tasks: list) -> dict:
        data = state["data"]
        state["step"] = 7
        
        try:
            import ai_engine
            analysis = ai_engine.handle_medical_leave_analysis({
                "reason": data["reason"],
                "comments": data["comments"],
                "duration": data["duration"]
            })
        except Exception:
            analysis = {}
            
        data["chatbot_summary"] = analysis.get("summary", f"Absence requested for {data['reason']} lasting {data['duration']}.")
        data["ai_suggested_extension"] = analysis.get("suggested_extension", "3 days")
        data["priority"] = analysis.get("priority", "Medium")
        
        summary_text = (
            "Please review the **Absence Request Summary**:\n\n"
            f"📋 **Reason:** {data['reason']}\n"
            f"⏱️ **Duration:** {data['duration']}\n"
            f"📅 **Expected Return:** {data['return_date']}\n"
            f"📎 **Proof Available:** {data['proof_available']}\n"
            f"💬 **Comments:** {data['comments']}\n"
            f"📚 **Target Task:** {data['task_title']} (ID: {data['task_id'] or 'General'})\n"
            f"🤖 **AI Recommended Extension:** {data['ai_suggested_extension']}\n"
            f"⚠️ **Priority Level:** {data['priority']}\n\n"
            "**Would you like me to submit this request to your faculty?**\n"
            "Reply **YES** to confirm or **NO** to cancel."
        )
        return {
            "reply": summary_text,
            "mode": "medical_leave",
            "step": 7,
            "action": None
        }

    # ------------------------------------------------------------------
    # Normal / AI mode
    # ------------------------------------------------------------------
    def _handle_normal(self, text: str, lower: str, original: str,
                       student_context: dict = None, student_name: str = "Student") -> dict:
        """Try AI first; fall back to rule-based FAQ on failure."""

        # The dashboard's menu uses these deterministic rules first.  This
        # prevents an unavailable/generic AI response from hiding the useful
        # leave, deadline and greeting behaviour.
        if re.fullmatch(r"(hi|hello|hey|good morning|good afternoon|good evening)[!. ]*", lower):
            return {"reply": "Hello! Choose an option below, or ask me about deadlines, performance, extensions, or leave.", "action": None, "mode": "normal", "step": 0}

        if re.search(r"\b(deadline|due date|upcoming task|upcoming tasks|deliverable)\b", lower):
            return {"reply": "Check the Assigned Lab Work section above for active deadlines. If you may miss one, choose Extension or Leave / illness below.", "action": None, "mode": "normal", "step": 0}

        if re.search(r"\b(performance|progress|score)\b", lower):
            return {"reply": "Your dashboard shows attendance, task completion, marks, timeliness and engagement. These combine into your capability score and success prediction.", "action": None, "mode": "normal", "step": 0}

        # --- Rule: extension request (keep existing feature) ---------------
        if re.search(r"\b(extend|extension|more time|delay|postpone)\b", lower):
            return {
                "reply": "I understand you need more time. Please provide your reason and I'll log an extension request to the faculty for review.",
                "action": "CREATE_EXTENSION_REQUEST",
                "mode": "normal",
                "step": 0
            }

        # --- Context-aware rules (from DB) ---------------------------------
        if student_context:
            if student_context.get("has_overdue_tasks"):
                return {
                    "reply": "⚠️ **Heads up!** You have overdue tasks. Please submit them immediately to avoid capability score penalties.",
                    "action": "SEND_OVERDUE_REMINDER",
                    "mode": "normal",
                    "step": 0
                }
            if student_context.get("last_marks", 100) < 50:
                return {
                    "reply": "📉 **Improvement tip:** Your last submission scored below 50. Review the evaluator's comments and consult your faculty for guidance.",
                    "action": "SEND_IMPROVEMENT_SUGGESTION",
                    "mode": "normal",
                    "step": 0
                }

        # --- Try Gemini AI --------------------------------------------------
        try:
            # Build message list for AI engine
            messages = [{"role": "user", "content": original}]
            ai_res = ai_engine.handle_chat({"messages": messages})
            reply = ai_res.get("reply", "")
            if reply:
                return {"reply": reply, "mode": "normal", "step": 0, "action": None}
        except Exception:
            pass  # Fall through to rule-based FAQ

        # --- Rule-based FAQ fallback ----------------------------------------
        faq = {
            "hello": "Hello! I'm your InternLens Virtual Career Assistant. How can I help you today?",
            "hi": "Hi there! Welcome back to InternLens. Ask me anything about your internship, tasks, or performance.",
            "how are you": "Running at full efficiency! I'm monitoring your capability scores and upcoming deliverables.",
            "capability score": "Your Capability Score = 30% Attendance + 25% Task Completion + 25% Evaluation Marks + 10% Timeliness + 10% Engagement.",
            "attendance": "Attendance contributes 30% to your Capability Score. Below 60% triggers a high-risk faculty alert.",
            "marks": "Evaluation marks make up 25% of your capability score on a 0-100 scale.",
            "classrooms": "Classrooms group students with faculty. Join via a classroom code to receive tasks and track progress.",
            "success prediction": "Our Random Forest model predicts your success using attendance, submissions, marks, engagement, and chatbot activity.",
            "who are you": "I'm InternLens AI — your virtual career assistant for guidance, issue reporting, and internship support.",
            "help": "Ask me about your 'capability score', 'attendance', 'marks', report an issue, or request a deadline 'extension'.",
        }

        for kw, resp in faq.items():
            if kw in lower:
                return {"reply": resp, "mode": "normal", "step": 0, "action": None}

        return {
            "reply": "I'm here to help! You can ask me about your internship progress, capability score, upcoming tasks — or type a personal issue and I'll help you report it to faculty.",
            "mode": "normal",
            "step": 0,
            "action": None
        }

    # ------------------------------------------------------------------
    # Clear state (called after issue is saved to DB)
    # ------------------------------------------------------------------
    def clear_state(self, student_id: int):
        self._states.pop(student_id, None)


# Singleton instance
chatbot_engine = HybridChatbotEngine()
