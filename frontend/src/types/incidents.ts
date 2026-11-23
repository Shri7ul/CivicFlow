export type IncidentCategory =
  | "ROADS"
  | "DRAINAGE"
  | "SANITATION"
  | "UTILITIES"
  | "PUBLIC_SAFETY"
  | "HEALTH"
  | "ENVIRONMENT"
  | "OTHER";

export type IncidentSeverity = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

export type IncidentStatus =
  | "OPEN"
  | "ACKNOWLEDGED"
  | "IN_PROGRESS"
  | "RESOLVED"
  | "CLOSED";

export type ProfileSummary = {
  id: string;
  full_name: string;
};

export type DepartmentSummary = {
  id: string;
  name: string;
};

export type Department = DepartmentSummary & {
  description: string | null;
  is_active: boolean;
};

export type StatusEvent = {
  id: string;
  from_status: IncidentStatus | null;
  to_status: IncidentStatus;
  note: string | null;
  actor: ProfileSummary | null;
  created_at: string;
};

export type Evidence = {
  id: string;
  incident_id: string;
  file_name: string;
  mime_type: string;
  file_size: number;
  uploader: ProfileSummary;
  created_at: string;
};

export type EvidenceUrl = {
  signed_url: string;
  expires_in: number;
};

export type Incident = {
  id: string;
  title: string;
  description: string;
  category: IncidentCategory;
  severity: IncidentSeverity;
  status: IncidentStatus;
  latitude: number;
  longitude: number;
  address: string | null;
  reporter: ProfileSummary;
  assigned_department: DepartmentSummary | null;
  resolved_at: string | null;
  created_at: string;
  updated_at: string;
  history: StatusEvent[];
  evidence: Evidence[];
};

export type IncidentList = {
  items: Incident[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
};

export type IncidentFilters = {
  page?: number;
  pageSize?: number;
  status?: IncidentStatus | "";
  category?: IncidentCategory | "";
  severity?: IncidentSeverity | "";
  departmentId?: string;
  query?: string;
  minLatitude?: number;
  minLongitude?: number;
  maxLatitude?: number;
  maxLongitude?: number;
};

export type IncidentCreateInput = {
  title: string;
  description: string;
  category: IncidentCategory;
  severity: IncidentSeverity;
  latitude: number;
  longitude: number;
  address?: string | null;
};

export type IncidentUpdateInput = Partial<IncidentCreateInput>;
