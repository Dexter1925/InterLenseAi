export interface Task {
  id: string;
  studentName: string;
  taskName: string;
  course: string;
  submittedAt: string;
  status: "review" | "progress" | "completed";
  avatar: string;
}

export interface Deliverable {
  id: string;
  title: string;
  info: string;
  completed: boolean;
  type: string;
}

export interface Submission {
  id: string;
  fileName: string;
  date: string;
  size: string;
  status: "APPROVED" | "PENDING" | "NEEDS_REVISION";
  type: string;
  feedback?: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  mode?: "normal" | "issue" | "medical_leave";
  step?: number;
  issueData?: any;
  showConfirm?: boolean;
}

export interface StudentIssue {
  id?: number;
  student_id?: number;
  student_name: string;
  roll_number?: string;
  issue_type: string;
  subject: string;
  date_of_incident: string;
  description: string;
  details: string;
  status?: "Pending" | "Accepted" | "Rejected" | "Resolved";
  faculty_reply?: string;
  created_at?: string;
  student_email?: string;
}

export type RoleMode = "student" | "faculty" | "landing";
export type ChatMode = "normal" | "issue" | "medical_leave";

export interface LeaveRequest {
  request_id: number;
  student_id: number;
  student_name?: string;
  student_public_id?: string;
  faculty_id: number;
  faculty_name?: string;
  assignment_id: number;
  task_title?: string;
  reason: string;
  chatbot_summary?: string;
  proof_file?: string;
  ai_suggested_extension?: string;
  requested_date?: string;
  updated_due_date?: string;
  original_due_date?: string;
  faculty_remark?: string;
  status: "Pending Faculty Review" | "Approved" | "Rejected";
  priority?: "Low" | "Medium" | "High";
  created_at: string;
}
