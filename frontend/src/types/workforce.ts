export type WorkerApplicationStatus =
  | "PENDING"
  | "UNDER_REVIEW"
  | "APPROVED"
  | "REJECTED"
  | "ADDITIONAL_INFORMATION_REQUIRED"
  | "SUSPENDED";

export type WorkerStatus = "ACTIVE" | "SUSPENDED";

export type AssignmentStatus =
  | "OFFERED"
  | "ACCEPTED"
  | "DECLINED"
  | "IN_PROGRESS"
  | "COMPLETION_SUBMITTED"
  | "VERIFIED_COMPLETED"
  | "CANCELLED";

export interface WorkerApplication {
  id: string;
  applicant_id: string;
  full_name: string;
  phone: string | null;
  email: string | null;
  specialization: string;
  department_id: string | null;
  service_area: string;
  address: string | null;
  experience: string | null;
  credentials_note: string | null;
  status: WorkerApplicationStatus;
  review_note: string | null;
  reviewer_id: string | null;
  reviewed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface WorkerProfile {
  id: string;
  profile_id: string;
  application_id: string;
  specialization: string;
  department_id: string | null;
  service_area: string;
  status: WorkerStatus;
  approved_by: string;
  approved_at: string;
  full_name: string | null;
  active_assignments: number;
  total_assignments: number;
}

export interface Candidate {
  worker_profile_id: string;
  profile_id: string;
  full_name: string;
  specialization: string;
  service_area: string;
  department_id: string | null;
  active_assignments: number;
  area_match: boolean;
  specialization_match: boolean;
  eligible: boolean;
  rationale: string;
}

export interface AssignmentEvent {
  id: string;
  from_status: AssignmentStatus | null;
  to_status: AssignmentStatus;
  note: string | null;
  actor_id: string;
  created_at: string;
}

export interface Assignment {
  id: string;
  incident_id: string;
  worker_profile_id: string;
  assigned_by: string;
  status: AssignmentStatus;
  rationale: string | null;
  note: string | null;
  completion_note: string | null;
  review_note: string | null;
  deadline: string | null;
  completed_at: string | null;
  verified_at: string | null;
  created_at: string;
  updated_at: string;
  events: AssignmentEvent[];
}

export interface AdminOverview {
  total_incidents: number;
  unreviewed_incidents: number;
  verified_awaiting_assignment: number;
  assigned_incidents: number;
  in_progress_incidents: number;
  awaiting_verification: number;
  verified_completed: number;
  resolved_incidents: number;
  rejected_incidents: number;
  pending_applications: number;
  active_workers: number;
  suspended_workers: number;
}

export interface WorkforceEventRecord {
  id: string;
  actor_id: string | null;
  action: string;
  entity_type: string;
  entity_id: string;
  previous_state: string | null;
  new_state: string | null;
  detail: Record<string, unknown>;
  created_at: string;
}

export interface WorkforceNotification {
  id: string;
  kind: string;
  title: string;
  body: string;
  entity_type: string | null;
  entity_id: string | null;
  read_at: string | null;
  created_at: string;
}

export interface ListResponse<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface ApplicationPayload {
  full_name: string;
  phone?: string;
  email?: string;
  specialization: string;
  department_id?: string;
  service_area: string;
  address?: string;
  experience?: string;
  credentials_note?: string;
}
