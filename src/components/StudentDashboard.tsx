import React, { useState, useEffect, useRef } from "react";
import {
  CheckCircle2,
  Clock,
  FileText,
  Send,
  UploadCloud,
  X,
  Bot,
  AlertCircle,
  Briefcase,
  AlertTriangle,
  CheckCheck,
  XCircle,
  Inbox
} from "lucide-react";
import { Deliverable, Submission, ChatMessage, StudentIssue, LeaveRequest } from "../types";

// ---------------------------------------------------------------------------
// Demo student identity (in a real app this comes from auth context)
// ---------------------------------------------------------------------------
const DEMO_STUDENT = { id: 1, name: "Alex Chen", rollNumber: "IL-2026-001" };

// ---------------------------------------------------------------------------
// Markdown-lite renderer (bold only)
// ---------------------------------------------------------------------------
function renderMarkdown(text: string) {
  return text
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(/\n/g, "<br/>");
}

// ---------------------------------------------------------------------------
// Issue summary card shown in chat when step === 5
// ---------------------------------------------------------------------------
function IssueSummaryCard({
  issueData,
  onYes,
  onNo,
  disabled,
}: {
  issueData: StudentIssue;
  onYes: () => void;
  onNo: () => void;
  disabled: boolean;
}) {
  return (
    <div className="bg-zinc-900 border border-brand-primary/30 rounded-xl p-4 space-y-3 text-xs w-full mt-1">
      <p className="text-brand-primary font-black uppercase tracking-wider text-[10px] flex items-center gap-1.5">
        <AlertTriangle className="w-3.5 h-3.5" /> Issue Report Summary
      </p>
      <div className="space-y-1.5">
        <div className="flex gap-2"><span className="text-zinc-500 w-28 shrink-0">Type</span><span className="text-white font-bold">{issueData.issue_type}</span></div>
        <div className="flex gap-2"><span className="text-zinc-500 w-28 shrink-0">Description</span><span className="text-white">{issueData.description}</span></div>
        <div className="flex gap-2"><span className="text-zinc-500 w-28 shrink-0">Subject</span><span className="text-white">{issueData.subject}</span></div>
        <div className="flex gap-2"><span className="text-zinc-500 w-28 shrink-0">Date</span><span className="text-white">{issueData.date_of_incident}</span></div>
        <div className="flex gap-2"><span className="text-zinc-500 w-28 shrink-0">Details</span><span className="text-white">{issueData.details}</span></div>
      </div>
      <p className="text-zinc-300 font-medium pt-1">Would you like me to notify your faculty?</p>
      <div className="flex gap-2 pt-1">
        <button
          onClick={onYes}
          disabled={disabled}
          className="flex-1 bg-brand-primary text-black font-black text-[10px] uppercase tracking-widest py-2 rounded-lg hover:brightness-110 disabled:opacity-50 transition-all flex items-center justify-center gap-1.5"
        >
          <CheckCheck className="w-3.5 h-3.5" /> YES, Notify Faculty
        </button>
        <button
          onClick={onNo}
          disabled={disabled}
          className="flex-1 bg-zinc-800 border border-zinc-700 text-zinc-300 font-black text-[10px] uppercase tracking-widest py-2 rounded-lg hover:bg-zinc-700 disabled:opacity-50 transition-all flex items-center justify-center gap-1.5"
        >
          <XCircle className="w-3.5 h-3.5" /> NO, Cancel
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Faculty Reply badge shown in chat for resolved/replied issues
// ---------------------------------------------------------------------------
function FacultyReplyCard({ issue }: { issue: StudentIssue }) {
  const statusColors: Record<string, string> = {
    Accepted: "text-emerald-400 border-emerald-500/30 bg-emerald-500/10",
    Rejected: "text-rose-400 border-rose-500/30 bg-rose-500/10",
    Resolved: "text-blue-400 border-blue-500/30 bg-blue-500/10",
    Pending: "text-amber-400 border-amber-500/30 bg-amber-500/10",
  };
  const statusClass = statusColors[issue.status || "Pending"] || statusColors.Pending;
  return (
    <div className={`border rounded-xl p-3 text-xs space-y-1.5 mt-1 ${statusClass}`}>
      <p className="font-black uppercase tracking-wider text-[10px] flex items-center gap-1.5">
        <AlertCircle className="w-3.5 h-3.5" />
        Faculty Response — {issue.issue_type}
        <span className="ml-auto">[{issue.status}]</span>
      </p>
      {issue.faculty_reply && (
        <p className="text-white font-medium">"{issue.faculty_reply}"</p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------
export default function StudentDashboard() {
  const [deliverables, setDeliverables] = useState<Deliverable[]>([]);
  const [submissions, setSubmissions] = useState<Submission[]>([]);
  const [loading, setLoading] = useState(true);

  const [newDeliverableTitle, setNewDeliverableTitle] = useState("");
  const [submitFileName, setSubmitFileName] = useState("");
  const [submitFileSize, setSubmitFileSize] = useState("");
  const [submitContent, setSubmitContent] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submissionFeedback, setSubmissionFeedback] = useState<string | null>(null);

  // Chat state
  const [isChatOpen, setIsChatOpen] = useState(false);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([
    {
      id: "init",
      role: "assistant",
      content:
        "Welcome back, Alex! I've analysed your performance metrics. Your next deadline for the **Final Reflection Report** is in 48 hours.\n\nI'm also here to help if you're facing a personal issue (absence, medical, accident, internet outage, etc.) — just tell me what happened and I'll guide you through reporting it to faculty. How can I help?",
      timestamp: "Just now",
      mode: "normal",
    },
  ]);
  const [chatInput, setChatInput] = useState("");
  const [isSendingChat, setIsSendingChat] = useState(false);
  const [chatMode, setChatMode] = useState<"normal" | "issue" | "medical_leave">("normal");
  const [pendingIssueData, setPendingIssueData] = useState<StudentIssue | null>(null);
  const [pendingConfirmMsgId, setPendingConfirmMsgId] = useState<string | null>(null);
  
  // Leave request state
  const [leaveRequests, setLeaveRequests] = useState<LeaveRequest[]>([]);

  // Faculty replies panel
  const [myIssues, setMyIssues] = useState<StudentIssue[]>([]);
  const [loadingIssues, setLoadingIssues] = useState(false);

  const chatEndRef = useRef<HTMLDivElement>(null);

  // Skills radar
  const skills = [
    { name: "Technical", value: 85, angle: -Math.PI / 2 },
    { name: "Soft Skills", value: 70, angle: -Math.PI / 2 + (Math.PI * 2) / 6 },
    { name: "Leadership", value: 60, angle: -Math.PI / 2 + (Math.PI * 2 * 2) / 6 },
    { name: "Innovation", value: 90, angle: -Math.PI / 2 + (Math.PI * 2 * 3) / 6 },
    { name: "Collaboration", value: 75, angle: -Math.PI / 2 + (Math.PI * 2 * 4) / 6 },
    { name: "Problem Solving", value: 88, angle: -Math.PI / 2 + (Math.PI * 2 * 5) / 6 },
  ];
  const cx = 150, cy = 130, r = 90;

  const getCoordinates = (value: number, angle: number) => ({
    x: cx + r * (value / 100) * Math.cos(angle),
    y: cy + r * (value / 100) * Math.sin(angle),
  });

  const hexGridPaths = [0.2, 0.4, 0.6, 0.8, 1.0].map((scale) => {
    const pts = skills.map((s) => {
      const x = cx + r * scale * Math.cos(s.angle);
      const y = cy + r * scale * Math.sin(s.angle);
      return `${x},${y}`;
    });
    return pts.join(" ");
  });

  const skillPoints = skills
    .map((s) => {
      const c = getCoordinates(s.value, s.angle);
      return `${c.x},${c.y}`;
    })
    .join(" ");

  // Scroll to bottom on new messages
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages]);

  // Fetch initial data
  useEffect(() => {
    async function fetchData() {
      try {
        const [delRes, subRes, leaveRes] = await Promise.all([
          fetch("/api/deliverables"),
          fetch("/api/submissions"),
          fetch("/api/student/leave-requests"),
        ]);
        if (delRes.ok) setDeliverables(await delRes.json());
        if (subRes.ok) setSubmissions(await subRes.json());
        if (leaveRes.ok) setLeaveRequests(await leaveRes.json());
      } catch (err) {
        console.error("Error fetching student data:", err);
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, []);

  // Fetch faculty replies on issues when chat is open
  useEffect(() => {
    if (isChatOpen) {
      fetchMyIssues();
      const interval = window.setInterval(fetchMyIssues, 15000);
      return () => window.clearInterval(interval);
    }
  }, [isChatOpen]);

  async function fetchMyIssues() {
    setLoadingIssues(true);
    try {
      const res = await fetch(`/api/student-issues/${DEMO_STUDENT.id}`);
      if (res.ok) {
        const data: StudentIssue[] = await res.json();
        setMyIssues(data);
        // Show new faculty replies in chat if not already shown
        data.forEach((issue) => {
          if (issue.faculty_reply && issue.status !== "Pending") {
            const replyMsg: ChatMessage = {
                id: `reply-issue-${issue.id}`,
                role: "assistant",
                content: `Faculty has responded to your **${issue.issue_type}** report.`,
                timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
                mode: "issue",
                issueData: issue,
            };
            setChatMessages((prev) => prev.some((m) => m.id === replyMsg.id) ? prev : [...prev, replyMsg]);
          }
        });
      }
    } catch (e) {
      console.error("Error fetching student issues:", e);
    } finally {
      setLoadingIssues(false);
    }
  }

  async function fetchLeaveRequests() {
    try {
      const res = await fetch("/api/student/leave-requests");
      if (res.ok) setLeaveRequests(await res.json());
    } catch (e) {
      console.error("Error fetching leave requests:", e);
    }
  }

  const handleUploadProof = async (reqId: number, e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || e.target.files.length === 0) return;
    const file = e.target.files[0];
    const formData = new FormData();
    formData.append("proof", file);
    try {
      const res = await fetch(`/api/student/leave-requests/${reqId}/upload-proof`, {
        method: "POST",
        body: formData,
      });
      if (res.ok) {
        alert("Proof document uploaded successfully!");
        fetchLeaveRequests();
      } else {
        alert("Failed to upload proof document.");
      }
    } catch (err) {
      console.error("Error uploading proof:", err);
    }
  };

  // ---------------------------------------------------------------------------
  // Deliverables actions
  // ---------------------------------------------------------------------------
  const handleToggleDeliverable = async (id: string, currentCompleted: boolean) => {
    try {
      const res = await fetch(`/api/deliverables/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ completed: !currentCompleted }),
      });
      if (res.ok) {
        const updated = await res.json();
        setDeliverables(deliverables.map((d) => (d.id === id ? updated : d)));
      }
    } catch (e) {
      console.error("Error toggling deliverable:", e);
    }
  };

  const handleAddDeliverable = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newDeliverableTitle.trim()) return;
    try {
      const res = await fetch("/api/deliverables", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: newDeliverableTitle, info: "Due soon • Self Assigned" }),
      });
      if (res.ok) {
        const added = await res.json();
        setDeliverables([...deliverables, added]);
        setNewDeliverableTitle("");
      }
    } catch (e) {
      console.error("Error adding deliverable:", e);
    }
  };

  // ---------------------------------------------------------------------------
  // Submission upload
  // ---------------------------------------------------------------------------
  const handleSubmitFile = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!submitFileName.trim()) return;
    setIsSubmitting(true);
    setSubmissionFeedback(null);
    try {
      const res = await fetch("/api/submissions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ fileName: submitFileName, size: submitFileSize || "2.4 MB", content: submitContent }),
      });
      if (res.ok) {
        const submission = await res.json();
        setSubmissions([submission, ...submissions]);
        setSubmissionFeedback(
          submission.feedback ||
            "Your file was submitted successfully! AI review has automatically graded it."
        );
        setSubmitFileName("");
        setSubmitFileSize("");
        setSubmitContent("");
      }
    } catch (err) {
      console.error("Error submitting file:", err);
    } finally {
      setIsSubmitting(false);
    }
  };

  // ---------------------------------------------------------------------------
  // Chat — core send function
  // ---------------------------------------------------------------------------
  const handleSendChat = async (textToSend?: string) => {
    const text = (textToSend || chatInput).trim();
    if (!text || isSendingChat) return;

    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: text,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      mode: chatMode,
    };

    setChatMessages((prev) => [...prev, userMsg]);
    if (!textToSend) setChatInput("");
    setIsSendingChat(true);

    // Typing indicator
    const typingId = `typing-${Date.now()}`;
    setChatMessages((prev) => [...prev, { id: typingId, role: "assistant", content: "...", timestamp: "" }]);

    try {
      const history = chatMessages
        .filter((m) => m.id !== "init" && m.content !== "..." && m.role !== "assistant")
        .concat(userMsg)
        .map((m) => ({ role: m.role, content: m.content }));

      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          messages: history,
          student_id: DEMO_STUDENT.id,
          student_name: DEMO_STUDENT.name,
          student_roll_number: DEMO_STUDENT.rollNumber,
        }),
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const data = await res.json();
      const newMode = (data.mode as "normal" | "issue") || "normal";
      const step: number = data.step ?? 0;
      const issueData: StudentIssue | null = data.issue_data || null;

      setChatMode(newMode);

      // Build assistant message
      const assistantMsg: ChatMessage = {
        id: `reply-${Date.now()}`,
        role: "assistant",
        content: data.reply || "I'm here to help!",
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        mode: newMode,
        step,
        issueData: issueData || undefined,
        showConfirm: (newMode === "issue" && step === 6 && !!issueData) || (newMode === "medical_leave" && step === 7 && !!issueData),
      };

      if (assistantMsg.showConfirm && issueData) {
        setPendingIssueData(issueData);
        setPendingConfirmMsgId(assistantMsg.id);
      }

      if (data.action === "SAVE_STUDENT_ISSUE" || data.action === "SAVE_MEDICAL_LEAVE") {
        setChatMode("normal");
        setPendingIssueData(null);
        setPendingConfirmMsgId(null);
        setTimeout(() => {
          fetchMyIssues();
          fetchLeaveRequests();
        }, 1000);
      }

      setChatMessages((prev) =>
        prev.filter((m) => m.id !== typingId).concat(assistantMsg)
      );
    } catch (e) {
      setChatMessages((prev) =>
        prev.filter((m) => m.id !== typingId).concat({
          id: `err-${Date.now()}`,
          role: "assistant",
          content:
            "⚠️ I'm having trouble connecting to my core right now. Please check that the Flask server is running on port 5000 and try again.",
          timestamp: "Just now",
          mode: "normal",
        })
      );
    } finally {
      setIsSendingChat(false);
    }
  };

  // YES — confirm submit issue
  const handleConfirmYes = async () => {
    setPendingConfirmMsgId(null);
    // Disable the confirm card visually
    setChatMessages((prev) =>
      prev.map((m) => (m.showConfirm ? { ...m, showConfirm: false } : m))
    );
    await handleSendChat("YES");
  };

  // NO — cancel issue
  const handleConfirmNo = async () => {
    setPendingConfirmMsgId(null);
    setChatMessages((prev) =>
      prev.map((m) => (m.showConfirm ? { ...m, showConfirm: false } : m))
    );
    await handleSendChat("NO");
  };

  const handleSuggestedTopic = (topic: string) => {
    setIsChatOpen(true);
    handleSendChat(topic);
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[500px]">
        <div className="w-12 h-12 border-4 border-brand-tertiary border-t-transparent rounded-full animate-spin" />
        <p className="mt-4 text-on-surface-variant text-sm font-display tracking-wider">Syncing Student Portal...</p>
      </div>
    );
  }

  return (
    <div className="space-y-8 animate-fade-in">
      {/* Top Banner */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 pb-4 border-b border-zinc-800">
        <div>
          <span className="text-brand-primary text-xs font-black uppercase tracking-[0.3em] block mb-1">STUDENT COMPLIANCE BOARD</span>
          <h2 className="text-4xl sm:text-5xl font-black font-display tracking-tighter text-white uppercase leading-[0.9]">Good morning, Alex.</h2>
          <div className="flex flex-wrap items-center gap-3 mt-3">
            <span className="bg-brand-primary/10 text-brand-primary border border-brand-primary/20 px-3 py-1 rounded-none text-[10px] font-black uppercase tracking-wider flex items-center gap-1.5">
              <span className="inline-block w-2 h-2 rounded-full bg-brand-primary animate-pulse" />
              Hybrid AI Assistant Active
            </span>
            <span className="text-zinc-400 text-xs font-mono uppercase tracking-wider flex items-center gap-1">
              <Briefcase className="w-4 h-4 text-brand-primary" />
              Current Internship: <strong className="text-white font-black">Neural-Ops Systems</strong>
            </span>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex -space-x-2">
            <img className="w-10 h-10 rounded-none border-2 border-zinc-800" src="https://lh3.googleusercontent.com/aida-public/AB6AXuD-Edn1Vbn_t7WARRjiMX98R8xIPOv2urtGIlLiUCTmQGit1SRSBpVoIPNkpz7Wou6hRCEselbqjBZvdorIskPdoR6DDKILfXNbRqHfDKbNOpC0ZxXsXYqW2CNGHoVX2rkc5poOsMtnsZXngLbFaTP3eT13CsrOGkzNysmhyorxF-ZFYJhIocRzaeoDLt5btMY8th_HYdtnjGy2W0WKVDc6wOmnoYEkHhuT9QMQllPnJobhMu5ge7TE0vAUxxYxntBGmN6Z9p3NYuE" alt="Avatar" />
            <div className="w-10 h-10 rounded-none bg-zinc-900 border-2 border-zinc-800 text-xs font-black text-brand-primary flex items-center justify-center">+4</div>
          </div>
          <button
            onClick={() => handleSuggestedTopic("Check internship progress")}
            className="glass-panel hover:bg-zinc-800 p-2.5 rounded-none text-zinc-400 hover:text-white transition-all flex items-center gap-2 text-xs font-black uppercase tracking-wider"
          >
            <Bot className="w-4 h-4 text-brand-primary animate-bounce" />
            <span>AI Status</span>
          </button>
        </div>
      </div>

      {/* Main Grid: Progress + Radar */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <div className="lg:col-span-4 glass-panel p-6 rounded-none border border-zinc-800 flex flex-col items-center justify-center text-center relative overflow-hidden">
          <div className="absolute top-0 left-0 w-full h-1 bg-brand-primary opacity-90" />
          <h3 className="font-display font-black text-xs uppercase text-brand-primary self-start tracking-[0.25em] mb-6">Internship Completion</h3>
          <div className="relative w-44 h-44 mb-6">
            <svg className="w-full h-full transform -rotate-90">
              <circle className="text-zinc-800/50" cx="88" cy="88" fill="transparent" r="74" stroke="currentColor" strokeWidth="10" />
              <circle className="text-brand-primary drop-shadow-[0_0_8px_rgba(242,125,38,0.4)]" cx="88" cy="88" fill="transparent" r="74" stroke="currentColor" strokeWidth="10" strokeDasharray="465" strokeDashoffset="116.25" strokeLinecap="square" />
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center">
              <span className="text-5xl font-black font-display text-white tracking-tighter">75%</span>
              <span className="text-[9px] text-zinc-400 font-mono font-black uppercase tracking-widest mt-1">Phase 3 / 4</span>
            </div>
          </div>
          <p className="text-zinc-400 text-xs font-medium px-2">You're ahead of <span className="text-white font-black">82%</span> of your cohort. Keep it up!</p>
        </div>

        <div className="lg:col-span-8 glass-panel p-6 rounded-none border border-zinc-800 flex flex-col">
          <div className="flex justify-between items-center mb-4">
            <h3 className="font-display font-black text-xs uppercase text-white tracking-[0.25em]">Competency Analysis</h3>
            <span className="px-2.5 py-1 bg-brand-primary/10 rounded-none text-[9px] font-mono font-black text-brand-primary border border-brand-primary/20 tracking-widest uppercase">SKILLS RADAR</span>
          </div>
          <div className="flex-1 flex flex-col sm:flex-row items-center justify-around gap-4 py-2">
            <div className="relative w-[300px] h-[260px] shrink-0">
              <svg width="300" height="260">
                {hexGridPaths.map((path, idx) => (
                  <polygon key={idx} points={path} fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="1" />
                ))}
                {skills.map((s, idx) => {
                  const end = getCoordinates(100, s.angle);
                  return <line key={idx} x1={cx} y1={cy} x2={end.x} y2={end.y} stroke="rgba(255,255,255,0.04)" strokeWidth="1" />;
                })}
                <polygon points={skillPoints} fill="rgba(242,125,38,0.15)" stroke="#F27D26" strokeWidth="2.5" className="drop-shadow-[0_0_10px_rgba(242,125,38,0.35)]" />
                {skills.map((s, idx) => {
                  const p = getCoordinates(s.value, s.angle);
                  return <circle key={idx} cx={p.x} cy={p.y} r="4" fill="#FFFFFF" stroke="#F27D26" strokeWidth="2" />;
                })}
                {skills.map((s, idx) => {
                  const p = getCoordinates(120, s.angle);
                  let textAnchor: "start" | "middle" | "end" = "middle";
                  if (p.x > cx + 20) textAnchor = "start";
                  else if (p.x < cx - 20) textAnchor = "end";
                  return <text key={idx} x={p.x} y={p.y + 4} fill="#c2c6d6" fontSize="9" fontWeight="700" textAnchor={textAnchor} className="font-mono tracking-wider uppercase opacity-85">{s.name}</text>;
                })}
              </svg>
            </div>
            <div className="space-y-2 text-xs w-full max-w-xs">
              <p className="text-[10px] text-zinc-500 font-mono uppercase tracking-[0.2em] border-b border-zinc-800 pb-1.5 mb-2.5 font-black">Core Strengths</p>
              {skills.slice().sort((a, b) => b.value - a.value).map((s, idx) => (
                <div key={idx} className="flex justify-between items-center bg-zinc-950 p-2.5 rounded-none border border-zinc-900">
                  <span className="text-zinc-300 font-bold uppercase text-[10px] tracking-wider">{s.name}</span>
                  <span className="text-brand-primary font-mono font-black">{s.value}%</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Suggested Chat Topics */}
      <div className="glass-panel p-5 rounded-none border border-zinc-800 flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-2 text-xs text-white uppercase font-black tracking-wider">
          <Bot className="w-5 h-5 text-brand-primary" />
          <span className="font-display font-black tracking-wider">Coaching Topics:</span>
        </div>
        <div className="flex flex-wrap gap-2">
          {[
            { label: "Resume Feedback", msg: "How can I improve my resume based on my API Refactor?" },
            { label: "Next Deadlines", msg: "What is my next critical deadline?" },
            { label: "Review Progress", msg: "Can you review my internship progress so far?" },
            { label: "Report Absence", msg: "I was absent yesterday due to a medical emergency" },
          ].map(({ label, msg }) => (
            <button
              key={label}
              onClick={() => handleSuggestedTopic(msg)}
              className="text-[10px] bg-zinc-900 hover:bg-brand-primary hover:text-black border border-zinc-800 text-zinc-300 px-3 py-1.5 rounded-none font-bold uppercase tracking-wider transition-all"
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Leave Request Status Section */}
      <div className="glass-panel p-6 rounded-none border border-zinc-800">
        <h3 className="font-display font-black text-xs uppercase tracking-[0.25em] text-white mb-4 flex items-center gap-2">
          <AlertCircle className="w-4 h-4 text-brand-primary" /> Leave & Absence Request Status
        </h3>
        {leaveRequests.length > 0 ? (
          <div className="overflow-x-auto no-scrollbar">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="text-zinc-500 text-[10px] uppercase tracking-[0.2em] border-b border-zinc-850">
                  <th className="pb-3 font-black">Assignment</th>
                  <th className="pb-3 font-black">Reason</th>
                  <th className="pb-3 font-black">Status</th>
                  <th className="pb-3 font-black">Submitted</th>
                  <th className="pb-3 font-black">Proof Document</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-850">
                {leaveRequests.map((lr) => (
                  <tr key={lr.request_id} className="hover:bg-zinc-900/30">
                    <td className="py-3">
                      <div className="font-bold text-white uppercase">{lr.task_title}</div>
                      <div className="text-[10px] text-zinc-500 font-mono">Faculty: {lr.faculty_name}</div>
                    </td>
                    <td className="py-3">
                      <div className="text-zinc-300">{lr.reason}</div>
                      {lr.chatbot_summary && <div className="text-[10px] text-zinc-500 italic mt-0.5">Summary: {lr.chatbot_summary}</div>}
                    </td>
                    <td className="py-3">
                      <span className={`px-2 py-0.5 rounded-none text-[9px] font-black tracking-wider ${lr.status === "Approved" ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20" : lr.status === "Rejected" ? "bg-rose-500/10 text-rose-400 border border-rose-500/20" : "bg-amber-500/10 text-amber-400 border border-amber-500/20"}`}>
                        {lr.status}
                      </span>
                      {lr.status === "Approved" && <div className="text-[9px] text-zinc-400 mt-1 font-mono">New Due: {lr.updated_due_date}</div>}
                      {lr.faculty_remark && <div className="text-[9px] text-zinc-500 mt-1 italic">Remarks: {lr.faculty_remark}</div>}
                    </td>
                    <td className="py-3 text-zinc-500 font-mono">{lr.created_at}</td>
                    <td className="py-3">
                      {lr.proof_file ? (
                        <a href={`/uploads/${lr.proof_file}`} target="_blank" rel="noreferrer" className="text-brand-primary hover:underline font-mono text-[10px]">{lr.proof_file}</a>
                      ) : lr.status === "Pending Faculty Review" ? (
                        <div className="flex items-center gap-1">
                          <label className="bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 text-zinc-300 text-[9px] px-2 py-1 rounded cursor-pointer font-bold">
                            Upload Proof
                            <input type="file" onChange={(e) => handleUploadProof(lr.request_id, e)} className="hidden" accept=".pdf,.png,.jpg,.jpeg,.zip" />
                          </label>
                        </div>
                      ) : (
                        <span className="text-zinc-600">No proof submitted</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-center py-4 bg-zinc-950/20 border border-dashed border-zinc-850">
            <p className="text-xs text-zinc-500 font-mono italic uppercase m-0">No active leave or absence requests logged</p>
          </div>
        )}
      </div>

      {/* Grid: Deliverables + Submissions */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Deliverables */}
        <div className="lg:col-span-5 glass-panel p-6 rounded-none border border-zinc-800 flex flex-col">
          <h3 className="font-display font-black text-xs uppercase tracking-[0.25em] text-white mb-4">Upcoming Deliverables</h3>
          <div className="space-y-3 flex-1 overflow-y-auto no-scrollbar max-h-[300px] pr-1">
            {deliverables.map((del) => (
              <div
                key={del.id}
                onClick={() => handleToggleDeliverable(del.id, del.completed)}
                className={`flex items-start gap-4 p-3.5 rounded-none border transition-all cursor-pointer group ${del.completed ? "bg-zinc-950/20 border-zinc-900 opacity-55" : "bg-zinc-900/40 border-zinc-800/80 hover:bg-zinc-900/60 hover:border-brand-primary"}`}
              >
                <div className="mt-0.5">
                  <input type="checkbox" checked={del.completed} onChange={() => {}} className="w-4 h-4 rounded-none bg-transparent border-zinc-700 text-brand-primary focus:ring-0 cursor-pointer" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className={`text-xs font-black uppercase tracking-wide truncate ${del.completed ? "text-zinc-500 line-through" : "text-white"}`}>{del.title}</p>
                  <p className="text-[10px] font-mono text-zinc-500 uppercase mt-0.5 tracking-wider">{del.info}</p>
                </div>
                <div>{del.completed ? <CheckCircle2 className="w-4 h-4 text-emerald-500" /> : <Clock className="w-4 h-4 text-brand-primary" />}</div>
              </div>
            ))}
          </div>
          <form onSubmit={handleAddDeliverable} className="mt-6 pt-4 border-t border-zinc-800 flex gap-2">
            <input type="text" value={newDeliverableTitle} onChange={(e) => setNewDeliverableTitle(e.target.value)} placeholder="QUICK-ADD SELF ASSIGNED MILESTONE..." className="flex-1 bg-zinc-950 border border-zinc-850 focus:border-brand-primary rounded-none px-3 py-2 text-xs text-white focus:outline-none uppercase placeholder:text-zinc-600" />
            <button type="submit" className="bg-zinc-900 hover:bg-zinc-800 text-white border border-zinc-800 font-black uppercase px-4 rounded-none text-xs transition-colors shrink-0">Add</button>
          </form>
        </div>

        {/* Submissions */}
        <div className="lg:col-span-7 glass-panel p-6 rounded-none border border-zinc-800 flex flex-col">
          <div className="flex justify-between items-center mb-4">
            <h3 className="font-display font-black text-xs uppercase tracking-[0.25em] text-white">Submission History</h3>
            <span className="text-[10px] text-zinc-500 font-mono uppercase tracking-wider">Recent Uploads</span>
          </div>
          <div className="overflow-x-auto no-scrollbar flex-1 mb-6">
            <table className="w-full text-left">
              <thead>
                <tr className="text-zinc-500 text-[10px] uppercase tracking-[0.2em] border-b border-zinc-850">
                  <th className="pb-3 font-black">File Name</th>
                  <th className="pb-3 font-black">Date</th>
                  <th className="pb-3 font-black">Size</th>
                  <th className="pb-3 font-black text-right">Status</th>
                </tr>
              </thead>
              <tbody className="text-xs divide-y divide-zinc-850">
                {submissions.map((sub) => (
                  <tr key={sub.id} className="hover:bg-zinc-900/30 transition-colors">
                    <td className="py-3">
                      <div className="flex items-center gap-2.5">
                        <FileText className={`w-4 h-4 ${sub.type === "pdf" ? "text-brand-primary" : sub.type === "sheet" ? "text-emerald-500" : "text-white"}`} />
                        <span className="font-bold text-white max-w-[160px] truncate uppercase text-[11px] tracking-wide">{sub.fileName}</span>
                      </div>
                    </td>
                    <td className="py-3 text-zinc-400 font-mono uppercase">{sub.date}</td>
                    <td className="py-3 text-zinc-400 font-mono uppercase">{sub.size}</td>
                    <td className="py-3 text-right">
                      <span className={`px-2 py-0.5 rounded-none text-[9px] font-black tracking-wider ${sub.status === "APPROVED" ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20" : "bg-amber-500/10 text-amber-400 border border-amber-500/20"}`}>
                        {sub.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="pt-4 border-t border-zinc-800">
            <h4 className="text-xs font-black uppercase text-white mb-2.5 tracking-wider flex items-center gap-1.5">
              <UploadCloud className="w-4 h-4 text-brand-primary" /> Upload New Report Submission
            </h4>
            <form onSubmit={handleSubmitFile} className="space-y-3">
              <div className="grid grid-cols-2 gap-2">
                <input type="text" required placeholder="e.g., Final_Report_V1.pdf" value={submitFileName} onChange={(e) => setSubmitFileName(e.target.value)} className="bg-zinc-950 border border-zinc-850 focus:border-brand-primary rounded-none px-3 py-2 text-xs text-white focus:outline-none w-full placeholder:text-zinc-600" />
                <input type="text" placeholder="e.g., 2.4 MB (Optional)" value={submitFileSize} onChange={(e) => setSubmitFileSize(e.target.value)} className="bg-zinc-950 border border-zinc-850 focus:border-brand-primary rounded-none px-3 py-2 text-xs text-white focus:outline-none w-full placeholder:text-zinc-600" />
              </div>
              <textarea required rows={2} placeholder="PASTE REPORT SUMMARY TEXT HERE. AI WILL AUTOMATICALLY REVIEW AND GRADE THIS CONTENT!" value={submitContent} onChange={(e) => setSubmitContent(e.target.value)} className="bg-zinc-950 border border-zinc-850 focus:border-brand-primary rounded-none px-3 py-2 text-xs text-white focus:outline-none w-full resize-none no-scrollbar placeholder:text-zinc-600 uppercase" />
              <button type="submit" disabled={isSubmitting} className="w-full bg-brand-primary text-black font-black uppercase text-xs tracking-wider py-3 rounded-none hover:bg-white hover:text-black border-2 border-brand-primary transition-all disabled:opacity-50">
                {isSubmitting ? "Uploading & Pre-grading with AI..." : "Upload & Analyze Submission"}
              </button>
            </form>
            {submissionFeedback && (
              <div className="mt-3 p-3 bg-zinc-950 border border-zinc-800 rounded-none text-[11px] text-brand-primary flex gap-2">
                <Bot className="w-4 h-4 text-brand-primary shrink-0 mt-0.5" />
                <div className="flex-1">
                  <strong className="text-white uppercase tracking-wider text-[10px]">AI Grading Feedback:</strong>
                  <p className="mt-1 text-zinc-400 italic font-medium">{submissionFeedback}</p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── Floating Chat Button ── */}
      <div className="fixed bottom-8 right-8 z-50">
        <button
          onClick={() => setIsChatOpen(!isChatOpen)}
          className="w-16 h-16 rounded-full bg-gradient-to-br from-brand-primary to-brand-secondary shadow-[0_0_20px_rgba(173,198,255,0.4)] hover:shadow-[0_0_30px_rgba(173,198,255,0.6)] hover:scale-105 active:scale-95 transition-all flex items-center justify-center text-slate-950 group relative"
          style={{ animation: "bounce 3s infinite" }}
        >
          {isChatOpen ? <X className="w-6 h-6" /> : <Bot className="w-7 h-7 text-slate-950 group-hover:rotate-12 transition-transform" />}
          {!isChatOpen && myIssues.filter((i) => i.faculty_reply && i.status !== "Pending").length > 0 && (
            <div className="absolute -top-1 -right-1 w-5 h-5 bg-emerald-500 rounded-full border-2 border-brand-bg flex items-center justify-center text-[10px] font-bold text-white shadow">
              {myIssues.filter((i) => i.faculty_reply && i.status !== "Pending").length}
            </div>
          )}
          {!isChatOpen && myIssues.filter((i) => i.faculty_reply && i.status !== "Pending").length === 0 && (
            <div className="absolute -top-1 -right-1 w-5 h-5 bg-rose-500 rounded-full border-2 border-brand-bg flex items-center justify-center text-[10px] font-bold text-white shadow">
              {chatMode === "issue" ? "!" : "2"}
            </div>
          )}
        </button>
      </div>

      {/* ── Floating Chat Panel ── */}
      {isChatOpen && (
        <div className="fixed bottom-28 right-8 z-50 w-full max-w-md h-[560px] glass-panel-floating rounded-2xl overflow-hidden flex flex-col shadow-2xl animate-scale-up">
          {/* Header */}
          <div className="bg-brand-surface p-4 border-b border-white/10 flex justify-between items-center shrink-0">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-full bg-brand-tertiary/15 border border-brand-tertiary/30 flex items-center justify-center">
                <Bot className="w-4.5 h-4.5 text-brand-tertiary ai-pulse" />
              </div>
              <div>
                <h4 className="text-sm font-bold text-white font-display">InternLens Hybrid AI</h4>
                <p className="text-[10px] font-mono tracking-widest uppercase flex items-center gap-1">
                  <span className={`inline-block w-1.5 h-1.5 rounded-full animate-pulse ${chatMode === "issue" ? "bg-amber-400" : "bg-emerald-400"}`} />
                  <span className={chatMode === "issue" ? "text-amber-400" : "text-emerald-400"}>
                    {chatMode === "issue" ? "Issue Report Mode" : "AI Assistant Active"}
                  </span>
                </p>
              </div>
            </div>
            <button onClick={() => setIsChatOpen(false)} className="text-on-surface-variant hover:text-white transition-colors">
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Messages Area */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3 no-scrollbar bg-brand-surface/20">
            {chatMessages.map((msg, idx) => (
              <div
                key={msg.id || idx}
                className={`flex gap-3 ${msg.role === "user" ? "self-end flex-row-reverse ml-auto max-w-[85%]" : "self-start max-w-[92%]"}`}
              >
                {msg.role !== "user" && (
                  <div className="w-7 h-7 rounded-full bg-white/5 flex items-center justify-center shrink-0 border border-white/10 mt-0.5">
                    <Bot className="w-4 h-4 text-brand-primary" />
                  </div>
                )}
                {msg.role === "user" && (
                  <img className="w-7 h-7 rounded-full border border-white/10 shrink-0 object-cover mt-0.5" src="https://lh3.googleusercontent.com/aida-public/AB6AXuD-Edn1Vbn_t7WARRjiMX98R8xIPOv2urtGIlLiUCTmQGit1SRSBpVoIPNkpz7Wou6hRCEselbqjBZvdorIskPdoR6DDKILfXNbRqHfDKbNOpC0ZxXsXYqW2CNGHoVX2rkc5poOsMtnsZXngLbFaTP3eT13CsrOGkzNysmhyorxF-ZFYJhIocRzaeoDLt5btMY8th_HYdtnjGy2W0WKVDc6wOmnoYEkHhuT9QMQllPnJobhMu5ge7TE0vAUxxYxntBGmN6Z9p3NYuE" alt="User" />
                )}
                <div className="space-y-2 flex-1">
                  <div className={`p-3 rounded-2xl text-xs leading-relaxed ${msg.role === "user" ? "bg-gradient-to-br from-brand-primary to-brand-secondary text-slate-900 font-medium rounded-tr-none" : "bg-white/[0.03] border border-white/5 text-on-surface-variant rounded-tl-none"}`}>
                    {msg.content === "..." ? (
                      <div className="flex items-center gap-1.5 py-1">
                        <span className="w-1.5 h-1.5 rounded-full bg-brand-tertiary animate-bounce" />
                        <span className="w-1.5 h-1.5 rounded-full bg-brand-tertiary animate-bounce" style={{ animationDelay: "0.2s" }} />
                        <span className="w-1.5 h-1.5 rounded-full bg-brand-tertiary animate-bounce" style={{ animationDelay: "0.4s" }} />
                      </div>
                    ) : (
                      <p dangerouslySetInnerHTML={{ __html: renderMarkdown(msg.content) }} />
                    )}
                    {msg.timestamp && <span className="block text-[8px] opacity-40 text-right mt-1 font-mono">{msg.timestamp}</span>}
                  </div>

                  {/* Confirm Card (step 5 summary) */}
                  {msg.showConfirm && msg.issueData && (
                    <IssueSummaryCard
                      issueData={msg.issueData}
                      onYes={handleConfirmYes}
                      onNo={handleConfirmNo}
                      disabled={isSendingChat}
                    />
                  )}

                  {/* Faculty Reply Card */}
                  {msg.mode === "issue" && msg.issueData && !msg.showConfirm && msg.issueData.faculty_reply && (
                    <FacultyReplyCard issue={msg.issueData} />
                  )}
                </div>
              </div>
            ))}
            <div ref={chatEndRef} />
          </div>

          {/* Quick Suggestions */}
          <div className="p-2.5 bg-brand-surface border-t border-white/5 flex gap-1.5 overflow-x-auto no-scrollbar shrink-0">
            {chatMode === "normal" ? (
              <>
                <button onClick={() => handleSuggestedTopic("Draft my Final Reflection Report outline")} className="text-[10px] bg-white/5 hover:bg-white/10 border border-white/5 text-on-surface-variant hover:text-white px-2 py-1 rounded-lg transition-all shrink-0">📝 Draft report outline</button>
                <button onClick={() => handleSuggestedTopic("I was absent due to a family emergency")} className="text-[10px] bg-white/5 hover:bg-white/10 border border-white/5 text-on-surface-variant hover:text-white px-2 py-1 rounded-lg transition-all shrink-0">🚨 Report absence</button>
                <button onClick={() => handleSuggestedTopic("I had an internet outage and couldn't submit")} className="text-[10px] bg-white/5 hover:bg-white/10 border border-white/5 text-on-surface-variant hover:text-white px-2 py-1 rounded-lg transition-all shrink-0">📶 Internet issue</button>
              </>
            ) : (
              <>
                <button onClick={() => handleSendChat("cancel")} className="text-[10px] bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/20 text-rose-300 hover:text-white px-2 py-1 rounded-lg transition-all shrink-0">✗ Cancel Report</button>
                <span className="text-[10px] text-zinc-600 flex items-center px-1 font-mono">Step-by-step mode active</span>
              </>
            )}
          </div>

          {/* Input Area */}
          <div className="p-3 bg-brand-surface border-t border-white/10 shrink-0">
            <div className="flex items-center gap-2 bg-white/[0.02] border border-white/10 rounded-xl p-1 focus-within:border-brand-tertiary/40 transition-colors">
              <input
                type="text"
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSendChat()}
                placeholder={chatMode === "issue" ? "Type your answer..." : "Ask anything to your Career Assistant..."}
                className="flex-1 bg-transparent border-none text-xs text-white placeholder:text-on-surface-variant/30 px-3.5 focus:ring-0 focus:outline-none"
              />
              <button
                onClick={() => handleSendChat()}
                disabled={isSendingChat || !chatInput.trim()}
                className="bg-brand-primary text-slate-900 p-2 rounded-lg hover:brightness-110 hover:shadow-[0_0_10px_rgba(173,198,255,0.3)] disabled:opacity-30 transition-all shrink-0"
              >
                <Send className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
