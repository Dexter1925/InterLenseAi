import React, { useState, useEffect, useCallback } from "react";
import {
  FileText,
  Mail,
  Plus,
  RotateCw,
  Share2,
  TrendingUp,
  AlertTriangle,
  Award,
  Users,
  CheckCircle2,
  Bot,
  Sparkles,
  ChevronRight,
  Trash2,
  X,
  Bell,
  MessageSquare,
  CheckCheck,
  XCircle,
  Clock,
  RefreshCw
} from "lucide-react";
import { Task, StudentIssue } from "../types";

export default function FacultyDashboard() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [aiRecommendation, setAiRecommendation] = useState("");
  const [loadingAi, setLoadingAi] = useState(false);

  // Form states for adding new student task card
  const [showAddForm, setShowAddForm] = useState(false);
  const [formStudentName, setFormStudentName] = useState("");
  const [formTaskName, setFormTaskName] = useState("");
  const [formCourse, setFormCourse] = useState("");

  // Quick feedback states
  const [notificationSent, setNotificationSent] = useState(false);
  const [reportExported, setReportExported] = useState(false);

  // Course filter state
  const [courseFilter, setCourseFilter] = useState("All");

  // Student Issues state
  const [activeTab, setActiveTab] = useState<"board" | "issues" | "leave_requests">("board");
  const [studentIssues, setStudentIssues] = useState<StudentIssue[]>([]);
  const [loadingIssues, setLoadingIssues] = useState(false);
  const [pendingIssueCount, setPendingIssueCount] = useState(0);
  const [replyDraft, setReplyDraft] = useState<Record<number, string>>({});
  const [processingIssueId, setProcessingIssueId] = useState<number | null>(null);

  // Leave requests state
  const [leaveRequests, setLeaveRequests] = useState<any[]>([]);
  const [loadingLeaves, setLoadingLeaves] = useState(false);
  const [selectedLeave, setSelectedLeave] = useState<any | null>(null);
  const [modalFacultyRemark, setModalFacultyRemark] = useState("");
  const [modalUpdatedDueDate, setModalUpdatedDueDate] = useState("");
  const [leaveSearchQuery, setLeaveSearchQuery] = useState("");

  // Fetch data
  const fetchData = async () => {
    try {
      const res = await fetch("/api/tasks");
      if (res.ok) {
        setTasks(await res.json());
      }
    } catch (e) {
      console.error("Error fetching tasks:", e);
    } finally {
      setLoading(false);
    }
  };

  // Fetch AI recommendations
  const fetchAiRecommendation = async () => {
    setLoadingAi(true);
    try {
      const res = await fetch("/api/recommendations");
      if (res.ok) {
        const data = await res.json();
        setAiRecommendation(data.recommendation);
      }
    } catch (e) {
      console.error("Error fetching recommendations:", e);
    } finally {
      setLoadingAi(false);
    }
  };

  // Fetch student issues
  const fetchStudentIssues = useCallback(async () => {
    setLoadingIssues(true);
    try {
      const res = await fetch("/api/faculty/student-issues");
      if (res.ok) {
        const data: StudentIssue[] = await res.json();
        setStudentIssues(data);
        setPendingIssueCount(data.filter((i) => i.status === "Pending").length);
      }
    } catch (e) {
      console.error("Error fetching student issues:", e);
    } finally {
      setLoadingIssues(false);
    }
  }, []);

  const fetchLeaveRequests = useCallback(async () => {
    setLoadingLeaves(true);
    try {
      const res = await fetch("/api/faculty/leave-requests");
      if (res.ok) {
        setLeaveRequests(await res.json());
      }
    } catch (e) {
      console.error("Error fetching leave requests:", e);
    } finally {
      setLoadingLeaves(false);
    }
  }, []);

  const handleDecideLeave = async (reqId: number, status: "Approved" | "Rejected") => {
    try {
      const res = await fetch(`/api/faculty/leave-requests/${reqId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          status,
          faculty_remark: modalFacultyRemark,
          updated_due_date: modalUpdatedDueDate,
        }),
      });
      if (res.ok) {
        alert(`Leave request has been ${status.toLowerCase()} successfully.`);
        setSelectedLeave(null);
        fetchLeaveRequests();
      } else {
        alert("Failed to update leave request.");
      }
    } catch (e) {
      console.error("Error deciding leave request:", e);
    }
  };

  // Update issue status
  const handleUpdateIssue = async (issueId: number, status: string) => {
    setProcessingIssueId(issueId);
    try {
      const reply = replyDraft[issueId] || "";
      const res = await fetch(`/api/faculty/student-issues/${issueId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status, faculty_reply: reply }),
      });
      if (res.ok) {
        const updated: StudentIssue = await res.json();
        setStudentIssues((prev) =>
          prev.map((i) => (i.id === issueId ? updated : i))
        );
        setPendingIssueCount((c) => Math.max(0, c - (status !== "Pending" ? 1 : 0)));
        setReplyDraft((d) => { const n = { ...d }; delete n[issueId]; return n; });
      }
    } catch (e) {
      console.error("Error updating issue:", e);
    } finally {
      setProcessingIssueId(null);
    }
  };

  useEffect(() => {
    fetchData();
    fetchAiRecommendation();
    fetchStudentIssues();
    fetchLeaveRequests();
    // Keep the alert badge current while the faculty board is open.
    const interval = setInterval(() => {
      fetch("/api/faculty/issues-count")
        .then((r) => r.json())
        .then((d) => setPendingIssueCount(d.pending_count || 0))
        .catch(() => {});
    }, 10000);
    return () => clearInterval(interval);
  }, [fetchStudentIssues, fetchLeaveRequests]);

  // Move task to a new column/status
  const handleMoveTask = async (id: string, newStatus: "review" | "progress" | "completed") => {
    try {
      const res = await fetch(`/api/tasks/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: newStatus }),
      });
      if (res.ok) {
        const updated = await res.json();
        setTasks(tasks.map((t) => (t.id === id ? updated : t)));
        // Refresh recommendation dynamically
        fetchAiRecommendation();
      }
    } catch (e) {
      console.error("Error moving task:", e);
    }
  };

  // Delete task
  const handleDeleteTask = async (id: string) => {
    try {
      const res = await fetch(`/api/tasks/${id}`, { method: "DELETE" });
      if (res.ok) {
        setTasks(tasks.filter((t) => t.id !== id));
        fetchAiRecommendation();
      }
    } catch (e) {
      console.error("Error deleting task:", e);
    }
  };

  // Add new card
  const handleAddTask = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formStudentName.trim() || !formTaskName.trim() || !formCourse.trim()) return;

    try {
      const res = await fetch("/api/tasks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          studentName: formStudentName,
          taskName: formTaskName,
          course: formCourse,
        }),
      });
      if (res.ok) {
        const added = await res.json();
        setTasks([...tasks, added]);
        // Reset and hide form
        setFormStudentName("");
        setFormTaskName("");
        setFormCourse("");
        setShowAddForm(false);
        fetchAiRecommendation();
      }
    } catch (e) {
      console.error("Error adding task:", e);
    }
  };

  // Notify students
  const handleNotifyAll = () => {
    setNotificationSent(true);
    setTimeout(() => setNotificationSent(false), 3000);
  };

  // Export report
  const handleExportReport = () => {
    setReportExported(true);
    setTimeout(() => setReportExported(false), 3000);
  };

  // Unique courses for filter
  const courses = ["All", "Backend", "Design", "Security", "Data Sci"];

  // Filtered tasks
  const filteredTasks = tasks.filter((t) => {
    if (courseFilter === "All") return true;
    return t.course.toLowerCase() === courseFilter.toLowerCase();
  });

  const toReviewTasks = filteredTasks.filter((t) => t.status === "review");
  const inProgressTasks = filteredTasks.filter((t) => t.status === "progress");
  const completedTasks = filteredTasks.filter((t) => t.status === "completed");

  // Status badge colors for student issues
  const issueStatusStyle: Record<string, string> = {
    Pending: "bg-amber-500/10 text-amber-400 border-amber-500/30",
    Accepted: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
    Rejected: "bg-rose-500/10 text-rose-400 border-rose-500/30",
    Resolved: "bg-blue-500/10 text-blue-400 border-blue-500/30",
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[500px]">
        <div className="w-12 h-12 border-4 border-brand-primary border-t-transparent rounded-full animate-spin"></div>
        <p className="mt-4 text-on-surface-variant text-sm font-display tracking-wider">Syncing Faculty Dashboard...</p>
      </div>
    );
  }

  return (
    <div className="space-y-8 animate-fade-in">
      {/* Top Banner Overview */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 pb-4 border-b border-zinc-800">
        <div>
          <span className="text-brand-primary text-xs font-black uppercase tracking-[0.3em] block mb-1">FACULTY CO-PILOT SYSTEM</span>
          <h2 className="text-4xl sm:text-5xl font-black font-display tracking-tighter text-white uppercase leading-[0.9]">Welcome back, Dr. Aris</h2>
          <span className="text-zinc-400 text-xs mt-2 block font-mono uppercase tracking-wider">
            Faculty Overview Dashboard & Co-pilot active
          </span>
        </div>

        <div className="flex items-center gap-4">
          <div className="flex items-center bg-zinc-950 border border-zinc-800 p-1 rounded-none text-xs font-medium">
            <button className="px-4 py-1.5 font-black uppercase text-[10px] bg-brand-primary text-black">Faculty</button>
            <button className="px-4 py-1.5 text-[10px] uppercase font-bold text-zinc-500 hover:text-white transition-all">Admin</button>
          </div>
          <button
            onClick={() => setShowAddForm(!showAddForm)}
            className="bg-brand-primary text-black font-black uppercase text-xs tracking-wider px-4.5 py-3 border-2 border-brand-primary hover:bg-white hover:border-white transition-all flex items-center gap-2"
          >
            <Plus className="w-4 h-4" />
            <span>Assign Task</span>
          </button>
        </div>
      </div>

      {/* Grid: Stat cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="glass-panel p-5 rounded-none border border-zinc-800 relative overflow-hidden group">
          <div className="flex justify-between items-start">
            <Users className="w-5 h-5 text-brand-primary" />
            <span className="text-[9px] text-brand-primary font-mono bg-brand-primary/10 px-2 py-0.5 rounded-none border border-brand-primary/20 font-black uppercase tracking-wider">+12% VS LAST MO</span>
          </div>
          <p className="text-zinc-500 font-mono text-[9px] uppercase tracking-[0.15em] mt-4 font-black">Active Internships</p>
          <h3 className="text-4xl font-black font-display text-white mt-1 tracking-tighter">42</h3>
        </div>

        <div className="glass-panel p-5 rounded-none border border-zinc-800 relative overflow-hidden group">
          <div className="flex justify-between items-start">
            <FileText className="w-5 h-5 text-brand-primary" />
            <span className="text-[9px] text-brand-primary font-mono bg-brand-primary/10 px-2 py-0.5 rounded-none border border-brand-primary/20 font-black uppercase tracking-wider">8 NEW TODAY</span>
          </div>
          <p className="text-zinc-500 font-mono text-[9px] uppercase tracking-[0.15em] mt-4 font-black">Pending Approvals</p>
          <h3 className="text-4xl font-black font-display text-white mt-1 tracking-tighter">{toReviewTasks.length + 13}</h3>
        </div>

        <div className="glass-panel p-5 rounded-none border border-zinc-800 relative overflow-hidden group">
          <div className="flex justify-between items-start">
            <Award className="w-5 h-5 text-brand-primary" />
            <span className="text-[9px] text-brand-primary font-mono bg-brand-primary/10 px-2 py-0.5 rounded-none border border-brand-primary/20 font-black uppercase tracking-wider">TOP 5% TIER</span>
          </div>
          <p className="text-zinc-500 font-mono text-[9px] uppercase tracking-[0.15em] mt-4 font-black">Student Performance</p>
          <h3 className="text-4xl font-black font-display text-white mt-1 tracking-tighter">88%</h3>
        </div>

        <div className="glass-panel p-5 rounded-none border border-zinc-800 relative overflow-hidden group">
          <div className="flex justify-between items-start">
            <AlertTriangle className="w-5 h-5 text-brand-primary" />
            <span className="text-[9px] text-brand-primary font-mono bg-brand-primary/10 px-2 py-0.5 rounded-none border border-brand-primary/20 font-black uppercase tracking-wider">URGENT</span>
          </div>
          <p className="text-zinc-500 font-mono text-[9px] uppercase tracking-[0.15em] mt-4 font-black">Upcoming Deadlines</p>
          <h3 className="text-4xl font-black font-display text-white mt-1 tracking-tighter">04</h3>
        </div>
      </div>

      {/* Slide down quick add task assignment form */}
      {showAddForm && (
        <form onSubmit={handleAddTask} className="glass-panel p-6 rounded-none border border-zinc-800 space-y-4 animate-slide-down relative bg-zinc-950">
          <div className="absolute top-4 right-4">
            <button 
              type="button" 
              onClick={() => setShowAddForm(false)}
              className="text-zinc-500 hover:text-white"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
          <h3 className="text-xs font-black uppercase tracking-[0.2em] text-white flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-brand-primary" />
            Assign New Internship Project Card
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-[9px] text-zinc-500 uppercase tracking-[0.15em] mb-1 font-black">Student Name</label>
              <input
                type="text"
                required
                placeholder="e.g., Liam Chen"
                value={formStudentName}
                onChange={(e) => setFormStudentName(e.target.value)}
                className="w-full bg-zinc-950 border border-zinc-850 rounded-none px-3.5 py-2.5 text-xs text-white focus:border-brand-primary focus:outline-none uppercase placeholder:text-zinc-600"
              />
            </div>
            <div>
              <label className="block text-[9px] text-zinc-500 uppercase tracking-[0.15em] mb-1 font-black">Project/Task Name</label>
              <input
                type="text"
                required
                placeholder="e.g., Auth Module refactor"
                value={formTaskName}
                onChange={(e) => setFormTaskName(e.target.value)}
                className="w-full bg-zinc-950 border border-zinc-850 rounded-none px-3.5 py-2.5 text-xs text-white focus:border-brand-primary focus:outline-none uppercase placeholder:text-zinc-600"
              />
            </div>
            <div>
              <label className="block text-[9px] text-zinc-500 uppercase tracking-[0.15em] mb-1 font-black">Department / Course</label>
              <select
                required
                value={formCourse}
                onChange={(e) => setFormCourse(e.target.value)}
                className="w-full bg-zinc-950 border border-zinc-850 rounded-none px-3.5 py-2.5 text-xs text-white focus:border-brand-primary focus:outline-none uppercase"
              >
                <option value="">Select course...</option>
                <option value="Backend">Backend</option>
                <option value="Design">Design</option>
                <option value="Security">Security</option>
                <option value="Data Sci">Data Sci</option>
              </select>
            </div>
          </div>
          <div className="flex justify-end gap-3 mt-2">
            <button
              type="button"
              onClick={() => setShowAddForm(false)}
              className="text-zinc-400 hover:text-white px-4 py-2 rounded-none text-xs font-black uppercase tracking-wider"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="bg-brand-primary text-black font-black px-6 py-2 rounded-none text-xs hover:bg-white hover:text-black border-2 border-brand-primary hover:border-white transition-all uppercase tracking-wider"
            >
              Create Card
            </button>
          </div>
        </form>
      )}

      {/* Main Grid: Student Progress Board (Kanban) & Right Sidebar */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        
        {/* Kanban progress board (8 cols) */}
        <div className="lg:col-span-8 space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <h4 className="font-display font-black text-xs uppercase tracking-[0.25em] text-white">Student Progress Board</h4>
            
            {/* Filter buttons */}
            <div className="flex items-center gap-1 bg-zinc-950 border border-zinc-800 p-1 rounded-none">
              {courses.map((course) => (
                <button
                  key={course}
                  onClick={() => setCourseFilter(course)}
                  className={`px-3 py-1.5 rounded-none text-[10px] font-black uppercase tracking-wider transition-all ${
                    courseFilter === course 
                      ? "bg-brand-primary text-black font-black" 
                      : "text-zinc-500 hover:text-white"
                  }`}
                >
                  {course}
                </button>
              ))}
            </div>
          </div>

          {/* Kanban columns */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            
            {/* Column: To Review */}
            <div className="space-y-4">
              <div className="flex items-center justify-between px-2 pb-2 border-b border-zinc-800">
                <span className="text-[10px] text-zinc-400 flex items-center gap-1.5 font-black uppercase tracking-widest">
                  <span className="w-2 h-2 bg-rose-500"></span>
                  To Review
                </span>
                <span className="bg-zinc-950 border border-zinc-800 text-rose-400 px-2.5 py-0.5 rounded-none text-[10px] font-black font-mono">
                  {toReviewTasks.length}
                </span>
              </div>

              <div className="space-y-3 min-h-[220px]">
                {toReviewTasks.length === 0 ? (
                  <div className="text-center py-8 bg-zinc-950/20 border border-dashed border-zinc-800 rounded-none">
                    <p className="text-[10px] text-zinc-600 uppercase tracking-wider font-mono italic">No tasks pending review</p>
                  </div>
                ) : (
                  toReviewTasks.map((t) => (
                    <div 
                      key={t.id}
                      className="glass-panel p-4 rounded-none border border-zinc-850 space-y-3 group hover:border-brand-primary transition-all shadow"
                    >
                      <div className="flex justify-between items-center">
                        <span className="bg-brand-primary/10 border border-brand-primary/20 text-brand-primary text-[9px] font-mono font-black px-2 py-0.5 rounded-none uppercase tracking-wider">
                          {t.course}
                        </span>
                        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                          <button 
                            onClick={() => handleMoveTask(t.id, "progress")}
                            title="Move to In Progress"
                            className="text-zinc-500 hover:text-brand-primary p-1"
                          >
                            <ChevronRight className="w-3.5 h-3.5" />
                          </button>
                          <button 
                            onClick={() => handleDeleteTask(t.id)}
                            title="Delete task card"
                            className="text-zinc-500 hover:text-rose-500 p-1"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>
                      <p className="text-white font-black text-xs uppercase tracking-wide leading-snug">{t.studentName} - {t.taskName}</p>
                      
                      <div className="flex items-center justify-between pt-1">
                        <div className="flex items-center gap-2">
                          <img className="w-6 h-6 rounded-none border border-zinc-800 object-cover" src={t.avatar} alt={t.studentName} />
                          <span className="text-[9px] text-zinc-500 font-mono uppercase">{t.submittedAt}</span>
                        </div>
                        <button 
                          onClick={() => handleMoveTask(t.id, "completed")}
                          className="bg-brand-primary text-black font-black text-[9px] px-2.5 py-1 rounded-none tracking-widest hover:bg-white hover:text-black border border-brand-primary hover:border-white transition-all uppercase"
                        >
                          APPROVE
                        </button>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* Column: In Progress */}
            <div className="space-y-4">
              <div className="flex items-center justify-between px-2 pb-2 border-b border-zinc-800">
                <span className="text-[10px] text-zinc-400 flex items-center gap-1.5 font-black uppercase tracking-widest">
                  <span className="w-2 h-2 bg-brand-primary"></span>
                  In Progress
                </span>
                <span className="bg-zinc-950 border border-zinc-800 text-brand-primary px-2.5 py-0.5 rounded-none text-[10px] font-black font-mono">
                  {inProgressTasks.length}
                </span>
              </div>

              <div className="space-y-3 min-h-[220px]">
                {inProgressTasks.length === 0 ? (
                  <div className="text-center py-8 bg-zinc-950/20 border border-dashed border-zinc-800 rounded-none">
                    <p className="text-[10px] text-zinc-600 uppercase tracking-wider font-mono italic">No tasks in progress</p>
                  </div>
                ) : (
                  inProgressTasks.map((t) => (
                    <div 
                      key={t.id}
                      className="glass-panel p-4 rounded-none border border-zinc-850 space-y-3 group hover:border-brand-primary transition-all shadow"
                    >
                      <div className="flex justify-between items-center">
                        <span className="bg-brand-primary/10 border border-brand-primary/20 text-brand-primary text-[9px] font-mono font-black px-2 py-0.5 rounded-none uppercase tracking-wider">
                          {t.course}
                        </span>
                        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                          <button 
                            onClick={() => handleMoveTask(t.id, "completed")}
                            title="Complete task"
                            className="text-zinc-500 hover:text-emerald-500 p-1"
                          >
                            <CheckCircle2 className="w-3.5 h-3.5" />
                          </button>
                          <button 
                            onClick={() => handleMoveTask(t.id, "review")}
                            title="Send back to Review"
                            className="text-zinc-500 hover:text-rose-500 p-1"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>
                      <p className="text-white font-black text-xs uppercase tracking-wide leading-snug">{t.studentName} - {t.taskName}</p>
                      
                      {/* Fake progress tracker */}
                      <div className="space-y-1.5">
                        <div className="flex justify-between text-[9px] text-zinc-500 font-mono uppercase">
                          <span>Milestone completion</span>
                          <span className="font-bold text-white">65%</span>
                        </div>
                        <div className="w-full bg-zinc-950 h-1 rounded-none overflow-hidden border border-zinc-850">
                          <div className="bg-brand-primary h-full w-[65%] rounded-none drop-shadow-[0_0_4px_rgba(242,125,38,0.4)]"></div>
                        </div>
                      </div>

                      <div className="flex items-center gap-2 pt-2 border-t border-zinc-850">
                        <img className="w-5 h-5 rounded-none border border-zinc-800 object-cover" src={t.avatar} alt={t.studentName} />
                        <span className="text-[9px] text-zinc-500 font-mono uppercase">Active sprint</span>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* Column: Completed */}
            <div className="space-y-4">
              <div className="flex items-center justify-between px-2 pb-2 border-b border-zinc-800">
                <span className="text-[10px] text-zinc-400 flex items-center gap-1.5 font-black uppercase tracking-widest">
                  <span className="w-2 h-2 bg-emerald-500"></span>
                  Completed
                </span>
                <span className="bg-zinc-950 border border-zinc-800 text-emerald-400 px-2.5 py-0.5 rounded-none text-[10px] font-black font-mono">
                  {completedTasks.length}
                </span>
              </div>

              <div className="space-y-3 min-h-[220px]">
                {completedTasks.length === 0 ? (
                  <div className="text-center py-8 bg-zinc-950/20 border border-dashed border-zinc-800 rounded-none">
                    <p className="text-[10px] text-zinc-600 uppercase tracking-wider font-mono italic">No tasks completed yet</p>
                  </div>
                ) : (
                  completedTasks.map((t) => (
                    <div 
                      key={t.id}
                      className="glass-panel p-4 rounded-none border border-zinc-850 space-y-3 opacity-60 hover:opacity-100 transition-opacity"
                    >
                      <div className="flex justify-between items-center">
                        <span className="bg-zinc-900 border border-zinc-800 text-zinc-400 text-[9px] font-mono font-black px-2 py-0.5 rounded-none uppercase">
                          {t.course}
                        </span>
                        <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                      </div>
                      <p className="text-zinc-500 font-bold text-xs line-through uppercase tracking-wide leading-snug">
                        {t.studentName} - {t.taskName}
                      </p>
                      
                      <div className="flex items-center gap-2 pt-1">
                        <img className="w-5 h-5 rounded-none border border-zinc-850 object-cover" src={t.avatar} alt={t.studentName} />
                        <span className="text-[9px] text-emerald-400 font-mono uppercase tracking-wider">Grade: Pass</span>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>

          </div>
        </div>

        {/* Right Sidebar actions & AI Widget (4 cols) */}
        <div className="lg:col-span-4 space-y-6">
          
          {/* AI recommendations widget */}
          <div className="glass-panel p-6 rounded-none border border-zinc-800 relative overflow-hidden group">
            <div className="absolute -right-4 -top-4 w-28 h-28 bg-brand-primary/5 blur-[40px] rounded-none group-hover:bg-brand-primary/10 transition-all"></div>
            
            <div className="flex justify-between items-center mb-4">
              <div className="flex items-center gap-2">
                <Bot className="w-5 h-5 text-brand-primary animate-pulse" />
                <h5 className="font-display font-black text-xs uppercase tracking-[0.2em] text-brand-primary">AI Recommendation</h5>
              </div>
              <button 
                onClick={fetchAiRecommendation}
                disabled={loadingAi}
                className="text-zinc-500 hover:text-white p-1"
                title="Recalculate AI Recommendation"
              >
                <RotateCw className={`w-3.5 h-3.5 ${loadingAi ? "animate-spin text-brand-primary" : ""}`} />
              </button>
            </div>

            {loadingAi ? (
              <div className="space-y-2 py-2">
                <div className="h-3 bg-zinc-900 animate-pulse w-full"></div>
                <div className="h-3 bg-zinc-900 animate-pulse w-5/6"></div>
                <div className="h-3 bg-zinc-900 animate-pulse w-4/5"></div>
              </div>
            ) : (
              <p className="text-white text-xs leading-relaxed font-sans font-medium">
                {aiRecommendation || "Cohort tracking normal. Check Liam Chen's Backend API Refactor report submission next."}
              </p>
            )}

            <button 
              onClick={() => handleNotifyAll()}
              className="mt-5 w-full py-3 bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 rounded-none text-xs font-black uppercase tracking-wider transition-all flex items-center justify-center gap-2 text-brand-primary"
            >
              <span>Open Profile Analytics</span>
              <ChevronRight className="w-3.5 h-3.5" />
            </button>
          </div>

          {/* SVG line chart: Engagement Trend */}
          <div className="glass-panel p-6 rounded-none border border-zinc-800 space-y-4">
            <div className="flex justify-between items-end">
              <div>
                <p className="text-[10px] text-zinc-500 font-mono uppercase tracking-[0.15em] mb-1 font-black">Engagement Trend</p>
                <h4 className="text-xl font-black text-white tracking-tighter flex items-baseline gap-1.5 font-display uppercase">
                  4.8k 
                  <span className="text-xs text-brand-primary font-black font-mono">+5.4%</span>
                </h4>
              </div>
              <TrendingUp className="w-5 h-5 text-brand-primary" />
            </div>

            {/* Customized neon SVG line graph */}
            <div className="h-32 w-full relative">
              <svg className="w-full h-full" viewBox="0 0 300 120">
                <defs>
                  {/* Grid layout lines */}
                  <linearGradient id="chartGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#F27D26" stopOpacity="0.25" />
                    <stop offset="100%" stopColor="#F27D26" stopOpacity="0" />
                  </linearGradient>
                </defs>
                
                {/* Concentric grid guide lines */}
                <line x1="0" y1="30" x2="300" y2="30" stroke="rgba(255, 255, 255, 0.03)" strokeWidth="0.5" />
                <line x1="0" y1="60" x2="300" y2="60" stroke="rgba(255, 255, 255, 0.03)" strokeWidth="0.5" />
                <line x1="0" y1="90" x2="300" y2="90" stroke="rgba(255, 255, 255, 0.03)" strokeWidth="0.5" />

                {/* Gradient area underneath */}
                <path
                  d="M 0 100 Q 40 120 70 80 T 130 90 T 200 40 T 260 70 T 300 30 L 300 120 L 0 120 Z"
                  fill="url(#chartGradient)"
                />

                {/* Main Glowing Path Line */}
                <path
                  d="M 0 100 Q 40 120 70 80 T 130 90 T 200 40 T 260 70 T 300 30"
                  fill="none"
                  stroke="#F27D26"
                  strokeWidth="2.5"
                  className="drop-shadow-[0_0_8px_rgba(242,125,38,0.5)]"
                />

                {/* Glowing indicators dots */}
                <circle cx="200" cy="40" r="4.5" fill="#F27D26" stroke="#05050a" strokeWidth="1.5" />
                <circle cx="300" cy="30" r="4.5" fill="#FFFFFF" stroke="#F27D26" strokeWidth="1.5" />
              </svg>
              <div className="absolute bottom-0 inset-x-0 flex justify-between text-[8px] text-zinc-600 font-mono tracking-widest px-1 uppercase font-bold">
                <span>Mon</span>
                <span>Wed</span>
                <span>Fri</span>
                <span>Sun</span>
              </div>
            </div>
          </div>

          {/* Quick Actions Grid */}
          <div className="glass-panel p-4 rounded-none border border-zinc-800 grid grid-cols-2 gap-3 relative overflow-hidden bg-zinc-950">
            <button 
              onClick={handleNotifyAll}
              className="flex flex-col items-center justify-center p-4 rounded-none hover:bg-zinc-900 hover:border-zinc-850 border border-transparent transition-all space-y-2 relative bg-zinc-900/50"
            >
              <Mail className="w-5 h-5 text-brand-primary" />
              <span className="text-[9px] uppercase font-mono tracking-widest font-black text-zinc-400">Notify All</span>
              {notificationSent && (
                <span className="absolute inset-0 bg-zinc-950 border border-brand-primary/30 rounded-none flex items-center justify-center text-[9px] font-black text-brand-primary animate-fade-in uppercase tracking-wider">
                  Students Notified!
                </span>
              )}
            </button>

            <button 
              onClick={handleExportReport}
              className="flex flex-col items-center justify-center p-4 rounded-none hover:bg-zinc-900 hover:border-zinc-850 border border-transparent transition-all space-y-2 relative bg-zinc-900/50"
            >
              <Share2 className="w-5 h-5 text-brand-primary" />
              <span className="text-[9px] uppercase font-mono tracking-widest font-black text-zinc-400">Export Report</span>
              {reportExported && (
                <span className="absolute inset-0 bg-zinc-950 border border-brand-primary/30 rounded-none flex items-center justify-center text-[9px] font-black text-brand-primary animate-fade-in uppercase tracking-wider">
                  PDF Exported!
                </span>
              )}
            </button>
          </div>

        </div>

      </div>

      {/* ── Tab Navigation: Progress Board | Student Issues ── */}
      <div className="border-t border-zinc-800 pt-8">
        <div className="flex items-center gap-1 bg-zinc-950 border border-zinc-800 p-1 rounded-none mb-6 w-fit">
          <button
            onClick={() => setActiveTab("board")}
            className={`px-5 py-2 text-xs font-black uppercase tracking-wider transition-all ${
              activeTab === "board" ? "bg-brand-primary text-black" : "text-zinc-400 hover:text-white"
            }`}
          >
            Progress Board
          </button>
          <button
            onClick={() => { setActiveTab("issues"); fetchStudentIssues(); }}
            className={`px-5 py-2 text-xs font-black uppercase tracking-wider transition-all flex items-center gap-2 ${
              activeTab === "issues" ? "bg-brand-primary text-black" : "text-zinc-400 hover:text-white"
            }`}
          >
            Student Issues
            {pendingIssueCount > 0 && (
              <span className={`w-5 h-5 rounded-full text-[10px] font-black flex items-center justify-center ${
                activeTab === "issues" ? "bg-black text-brand-primary" : "bg-rose-500 text-white"
              }`}>
                {pendingIssueCount}
              </span>
            )}
          </button>
          <button
            onClick={() => { setActiveTab("leave_requests"); fetchLeaveRequests(); }}
            className={`px-5 py-2 text-xs font-black uppercase tracking-wider transition-all flex items-center gap-2 ${
              activeTab === "leave_requests" ? "bg-brand-primary text-black" : "text-zinc-400 hover:text-white"
            }`}
          >
            Leave Requests
          </button>
        </div>

        {/* ── Student Issues Panel ── */}
        {activeTab === "issues" && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-black uppercase tracking-wider text-white flex items-center gap-2">
                  <Bell className="w-4 h-4 text-brand-primary" />
                  Student Issue Reports
                </h3>
                <p className="text-[10px] text-zinc-500 font-mono uppercase tracking-wider mt-1">
                  {pendingIssueCount} pending • {studentIssues.length} total
                </p>
              </div>
              <button
                onClick={fetchStudentIssues}
                disabled={loadingIssues}
                className="text-zinc-500 hover:text-white p-2 transition-colors"
                title="Refresh"
              >
                <RefreshCw className={`w-4 h-4 ${loadingIssues ? "animate-spin text-brand-primary" : ""}`} />
              </button>
            </div>

            {loadingIssues && studentIssues.length === 0 ? (
              <div className="text-center py-16 text-zinc-600">
                <RefreshCw className="w-8 h-8 animate-spin mx-auto mb-3 text-brand-primary" />
                <p className="text-xs font-mono uppercase tracking-wider">Loading issues...</p>
              </div>
            ) : studentIssues.length === 0 ? (
              <div className="text-center py-16 bg-zinc-950/30 border border-dashed border-zinc-800 rounded-none">
                <Bell className="w-10 h-10 text-zinc-700 mx-auto mb-3" />
                <p className="text-xs font-mono uppercase tracking-wider text-zinc-600">No student issue reports yet</p>
                <p className="text-[10px] text-zinc-700 mt-1">Reports submitted via the student chatbot will appear here</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {studentIssues.map((issue) => (
                  <div
                    key={issue.id}
                    className={`glass-panel p-5 rounded-none border transition-all ${
                      issue.status === "Pending"
                        ? "border-amber-500/30 bg-amber-500/5"
                        : issue.status === "Accepted"
                        ? "border-emerald-500/20"
                        : issue.status === "Rejected"
                        ? "border-rose-500/20"
                        : "border-zinc-800"
                    }`}
                  >
                    {/* Issue Header */}
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className={`text-[9px] font-black uppercase tracking-wider px-2 py-0.5 border rounded-none ${
                            issueStatusStyle[issue.status || "Pending"]
                          }`}>
                            {issue.status}
                          </span>
                          <span className="text-[9px] font-mono text-zinc-500 uppercase tracking-wider">
                            {issue.created_at ? new Date(issue.created_at).toLocaleDateString() : ""}
                          </span>
                        </div>
                        <h4 className="text-sm font-black text-white uppercase tracking-wider mt-1.5">
                          {issue.issue_type}
                        </h4>
                        <p className="text-[10px] text-brand-primary font-mono uppercase tracking-wider">
                          {issue.student_name} {issue.student_email ? `• ${issue.student_email}` : ""}
                        </p>
                      </div>
                    </div>

                    {/* Issue Details */}
                    <div className="space-y-1.5 text-xs border-t border-zinc-800 pt-3 mb-3">
                      {issue.description && (
                        <div className="flex gap-2">
                          <span className="text-zinc-500 w-20 shrink-0 text-[10px] uppercase font-bold">What</span>
                          <span className="text-zinc-300">{issue.description}</span>
                        </div>
                      )}
                      {issue.subject && (
                        <div className="flex gap-2">
                          <span className="text-zinc-500 w-20 shrink-0 text-[10px] uppercase font-bold">Subject</span>
                          <span className="text-zinc-300">{issue.subject}</span>
                        </div>
                      )}
                      {issue.date_of_incident && (
                        <div className="flex gap-2">
                          <span className="text-zinc-500 w-20 shrink-0 text-[10px] uppercase font-bold">Date</span>
                          <span className="text-zinc-300">{issue.date_of_incident}</span>
                        </div>
                      )}
                      {issue.details && issue.details !== "No additional details provided." && (
                        <div className="flex gap-2">
                          <span className="text-zinc-500 w-20 shrink-0 text-[10px] uppercase font-bold">Details</span>
                          <span className="text-zinc-300">{issue.details}</span>
                        </div>
                      )}
                    </div>

                    {/* Faculty Reply Box */}
                    {issue.status === "Pending" && (
                      <div className="space-y-2">
                        <textarea
                          rows={2}
                          value={replyDraft[issue.id!] || ""}
                          onChange={(e) =>
                            setReplyDraft((d) => ({ ...d, [issue.id!]: e.target.value }))
                          }
                          placeholder="Optional reply to student..."
                          className="w-full bg-zinc-950 border border-zinc-800 focus:border-brand-primary rounded-none px-3 py-2 text-xs text-white focus:outline-none resize-none placeholder:text-zinc-600"
                        />
                        <div className="flex gap-2">
                          <button
                            onClick={() => handleUpdateIssue(issue.id!, "Accepted")}
                            disabled={processingIssueId === issue.id}
                            className="flex-1 bg-emerald-500/10 hover:bg-emerald-500/20 border border-emerald-500/30 text-emerald-400 font-black text-[10px] uppercase tracking-wider py-2 rounded-none transition-all disabled:opacity-50 flex items-center justify-center gap-1"
                          >
                            <CheckCheck className="w-3.5 h-3.5" /> Accept
                          </button>
                          <button
                            onClick={() => handleUpdateIssue(issue.id!, "Rejected")}
                            disabled={processingIssueId === issue.id}
                            className="flex-1 bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/30 text-rose-400 font-black text-[10px] uppercase tracking-wider py-2 rounded-none transition-all disabled:opacity-50 flex items-center justify-center gap-1"
                          >
                            <XCircle className="w-3.5 h-3.5" /> Reject
                          </button>
                          <button
                            onClick={() => handleUpdateIssue(issue.id!, "Resolved")}
                            disabled={processingIssueId === issue.id}
                            className="flex-1 bg-blue-500/10 hover:bg-blue-500/20 border border-blue-500/30 text-blue-400 font-black text-[10px] uppercase tracking-wider py-2 rounded-none transition-all disabled:opacity-50 flex items-center justify-center gap-1"
                          >
                            <Clock className="w-3.5 h-3.5" /> Resolve
                          </button>
                        </div>
                      </div>
                    )}

                    {/* Show existing faculty reply */}
                    {issue.faculty_reply && (
                      <div className="mt-2 pt-2 border-t border-zinc-800">
                        <p className="text-[10px] text-zinc-500 uppercase font-black tracking-wider mb-1 flex items-center gap-1">
                          <MessageSquare className="w-3 h-3" /> Faculty Reply
                        </p>
                        <p className="text-xs text-zinc-300 italic">"{issue.faculty_reply}"</p>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* ── Leave Requests Panel ── */}
        {activeTab === "leave_requests" && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-black uppercase tracking-wider text-white flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-brand-primary" />
                  Student Medical & Leave Requests
                </h3>
                <p className="text-[10px] text-zinc-500 font-mono uppercase tracking-wider mt-1">
                  {leaveRequests.filter((r) => r.status === "Pending Faculty Review").length} pending • {leaveRequests.length} total
                </p>
              </div>
              <div className="flex items-center gap-4">
                <input
                  type="text"
                  placeholder="Search student ID..."
                  value={leaveSearchQuery}
                  onChange={(e) => setLeaveSearchQuery(e.target.value)}
                  className="bg-zinc-950 border border-zinc-800 focus:border-brand-primary rounded-none px-3 py-1.5 text-xs text-white focus:outline-none placeholder:text-zinc-700"
                />
                <button
                  onClick={fetchLeaveRequests}
                  disabled={loadingLeaves}
                  className="text-zinc-500 hover:text-white p-2 transition-colors"
                  title="Refresh"
                >
                  <RefreshCw className={`w-4 h-4 ${loadingLeaves ? "animate-spin text-brand-primary" : ""}`} />
                </button>
              </div>
            </div>

            {loadingLeaves && leaveRequests.length === 0 ? (
              <div className="text-center py-16 text-zinc-600">
                <RefreshCw className="w-8 h-8 animate-spin mx-auto mb-3 text-brand-primary" />
                <p className="text-xs font-mono uppercase tracking-wider">Loading requests...</p>
              </div>
            ) : leaveRequests.length === 0 ? (
              <div className="text-center py-16 bg-zinc-950/30 border border-dashed border-zinc-800 rounded-none">
                <AlertTriangle className="w-10 h-10 text-zinc-700 mx-auto mb-3" />
                <p className="text-xs font-mono uppercase tracking-wider text-zinc-600">No leave requests found</p>
              </div>
            ) : (
              <div className="overflow-x-auto no-scrollbar glass-panel p-4 rounded-none border border-zinc-800">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="text-zinc-500 text-[10px] uppercase tracking-[0.2em] border-b border-zinc-850">
                      <th className="pb-3 font-black">Student ID</th>
                      <th className="pb-3 font-black">Name</th>
                      <th className="pb-3 font-black">Task</th>
                      <th className="pb-3 font-black">Reason</th>
                      <th className="pb-3 font-black">Priority</th>
                      <th className="pb-3 font-black">Status</th>
                      <th className="pb-3 font-black text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-850">
                    {leaveRequests
                      .filter((lr) => {
                        return !leaveSearchQuery || lr.student_public_id?.toLowerCase().includes(leaveSearchQuery.toLowerCase());
                      })
                      .map((lr) => (
                        <tr key={lr.request_id} className="hover:bg-zinc-900/30">
                          <td className="py-3 font-bold text-white font-mono uppercase">{lr.student_public_id}</td>
                          <td className="py-3 text-zinc-300 font-bold">{lr.student_name}</td>
                          <td className="py-3 text-zinc-400">{lr.task_title}</td>
                          <td className="py-3 text-zinc-300 max-w-xs truncate">{lr.reason}</td>
                          <td className="py-3">
                            <span className={`px-2 py-0.5 rounded-none text-[9px] font-black tracking-wider ${lr.priority === "High" ? "bg-rose-500/10 text-rose-400 border border-rose-500/20" : lr.priority === "Medium" ? "bg-amber-500/10 text-amber-400 border border-amber-500/20" : "bg-info/10 text-info border border-info/20"}`}>
                              {lr.priority}
                            </span>
                          </td>
                          <td className="py-3">
                            <span className={`px-2 py-0.5 rounded-none text-[9px] font-black tracking-wider ${lr.status === "Approved" ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20" : lr.status === "Rejected" ? "bg-rose-500/10 text-rose-400 border border-rose-500/20" : "bg-amber-500/10 text-amber-400 border border-amber-500/20"}`}>
                              {lr.status}
                            </span>
                          </td>
                          <td className="py-3 text-right">
                            <button
                              onClick={() => {
                                setSelectedLeave(lr);
                                setModalFacultyRemark(lr.faculty_remark || "");
                                setModalUpdatedDueDate((lr.updated_due_date || lr.original_due_date || "").replace(" ", "T"));
                              }}
                              className="bg-brand-primary text-black font-black text-[10px] uppercase tracking-wider px-3 py-1 hover:brightness-110"
                            >
                              Review
                            </button>
                          </td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── Leave Review Dialog Overlay ── */}
      {selectedLeave && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 animate-fade-in p-4">
          <div className="w-full max-w-2xl bg-zinc-950 border border-zinc-800 p-6 space-y-6 animate-scale-up max-h-[90vh] overflow-y-auto no-scrollbar">
            <div className="flex justify-between items-center border-b border-zinc-850 pb-4">
              <h3 className="text-sm font-black uppercase tracking-wider text-brand-primary flex items-center gap-2">
                <FileText className="w-5 h-5" /> Review Absence Excuse
              </h3>
              <button onClick={() => setSelectedLeave(null)} className="text-zinc-500 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 text-xs">
              <div className="space-y-4 border-r border-zinc-900 pr-0 md:pr-6">
                <h4 className="font-display font-black text-[11px] uppercase text-white tracking-widest">Student Profile</h4>
                <div className="space-y-2">
                  <div className="flex justify-between"><span className="text-zinc-500">Student ID:</span><span className="font-mono text-white font-bold">{selectedLeave.student_public_id}</span></div>
                  <div className="flex justify-between"><span className="text-zinc-500">Name:</span><span className="text-zinc-200 font-bold">{selectedLeave.student_name}</span></div>
                  <div className="flex justify-between"><span className="text-zinc-500">Assignment:</span><span className="text-zinc-200">{selectedLeave.task_title}</span></div>
                  <div className="flex justify-between"><span className="text-zinc-500">Submitted:</span><span className="text-zinc-400 font-mono">{selectedLeave.created_at}</span></div>
                </div>

                <div className="p-3 border border-zinc-850 bg-black/40">
                  <label className="text-[9px] text-zinc-500 uppercase tracking-widest font-mono d-block mb-1">Excuse Reason</label>
                  <p className="text-white font-bold m-0">{selectedLeave.reason}</p>
                </div>

                <div className="p-3 border border-zinc-850 bg-brand-primary/5">
                  <label className="text-[9px] text-brand-primary uppercase tracking-widest font-mono d-block mb-1">🤖 AI Advisor Summary</label>
                  <p className="text-zinc-300 italic m-0">{selectedLeave.chatbot_summary || "No AI summary available."}</p>
                </div>
              </div>

              <div className="space-y-4">
                <h4 className="font-display font-black text-[11px] uppercase text-white tracking-widest">Evaluation & Extensions</h4>

                <div className="grid grid-cols-2 gap-2">
                  <div className="p-2 border border-zinc-850 bg-black/20 text-center">
                    <div className="text-[9px] text-zinc-500 font-mono">AI Suggestion</div>
                    <div className="font-bold text-brand-secondary mt-1">{selectedLeave.ai_suggested_extension || "No recommendation"}</div>
                  </div>
                  <div className="p-2 border border-zinc-850 bg-black/20 text-center">
                    <div className="text-[9px] text-zinc-500 font-mono">Priority</div>
                    <span className="inline-block mt-1 font-mono text-[9px] font-black tracking-wider text-brand-primary">{selectedLeave.priority || "Medium"}</span>
                  </div>
                </div>

                <div>
                  <label className="block text-[10px] text-zinc-400 uppercase tracking-wider mb-1 font-bold">Proof Document</label>
                  {selectedLeave.proof_file ? (
                    <a href={`/uploads/${selectedLeave.proof_file}`} target="_blank" rel="noreferrer" className="text-brand-secondary hover:underline font-mono d-block p-2 border border-zinc-850 bg-black/40">{selectedLeave.proof_file}</a>
                  ) : (
                    <div className="text-zinc-500 italic p-2 border border-zinc-900 bg-black/10">No supporting proof document submitted</div>
                  )}
                </div>

                <div>
                  <label className="block text-[10px] text-zinc-400 uppercase tracking-wider mb-1 font-bold">New Due Date (Approved only)</label>
                  <input
                    type="datetime-local"
                    value={modalUpdatedDueDate}
                    onChange={(e) => setModalUpdatedDueDate(e.target.value)}
                    className="w-full bg-zinc-950 border border-zinc-850 focus:border-brand-primary rounded-none px-3 py-2 text-xs text-white focus:outline-none"
                  />
                  <div className="text-[9px] text-zinc-500 font-mono mt-1">Current Due Date: {selectedLeave.original_due_date}</div>
                </div>

                <div>
                  <label className="block text-[10px] text-zinc-400 uppercase tracking-wider mb-1 font-bold">Feedback / Remarks</label>
                  <textarea
                    rows={2}
                    value={modalFacultyRemark}
                    onChange={(e) => setModalFacultyRemark(e.target.value)}
                    placeholder="Provide justification or remarks..."
                    className="w-full bg-zinc-950 border border-zinc-850 focus:border-brand-primary rounded-none px-3 py-2 text-xs text-white focus:outline-none resize-none placeholder:text-zinc-700"
                  />
                </div>
              </div>
            </div>

            <div className="flex justify-between items-center border-t border-zinc-850 pt-4">
              <span className="text-[9px] text-zinc-500 font-mono">Decisions update Capability Scores automatically.</span>
              <div className="flex gap-2">
                <button
                  onClick={() => handleDecideLeave(selectedLeave.request_id, "Rejected")}
                  className="bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/30 text-rose-400 font-black text-xs uppercase tracking-wider px-4 py-2"
                >
                  Reject excuse
                </button>
                <button
                  onClick={() => handleDecideLeave(selectedLeave.request_id, "Approved")}
                  className="bg-brand-primary text-black font-black text-xs uppercase tracking-wider px-5 py-2 hover:brightness-110"
                >
                  Approve Request
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
      </div>
    );
}
