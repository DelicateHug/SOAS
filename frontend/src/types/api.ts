/**
 * TypeScript types matching the shared Pydantic schemas.
 */

export interface UserBrief {
  id: string;
  username: string;
  display_name: string;
}

export interface PaginatedResponse<T> {
  data: T[];
  meta: {
    total: number;
    page: number;
    per_page: number;
    total_pages: number;
  };
}

// Incidents
export type IncidentSeverity = "critical" | "high" | "medium" | "low" | "informational";
export type IncidentStatus =
  | "detected"
  | "triaging"
  | "investigating"
  | "containing"
  | "remediating"
  | "resolved"
  | "closed"
  | "false_positive";

export interface Incident {
  id: string;
  title: string;
  summary?: string;
  severity: IncidentSeverity;
  status: IncidentStatus;
  source?: string;
  source_ref?: string;
  lead?: UserBrief;
  created_by: UserBrief;
  detected_at?: string;
  resolved_at?: string;
  closed_at?: string;
  tags: string[];
  metadata: Record<string, unknown>;
  raw_event?: Record<string, unknown>;
  assignment_count: number;
  case_id?: string;
  group_ids: string[];
  created_at: string;
  updated_at: string;
}

export interface IncidentListItem {
  id: string;
  title: string;
  severity: IncidentSeverity;
  status: IncidentStatus;
  lead?: UserBrief;
  created_by: UserBrief;
  detected_at?: string;
  tags: string[];
  assignment_count: number;
  group_ids: string[];
  created_at: string;
  updated_at: string;
}

// Cases / Incident Groups
export type CaseStatus = "open" | "investigating" | "pending" | "closed" | "archived";

export interface CaseItem {
  id: string;
  title: string;
  description?: string;
  status: CaseStatus;
  priority: number;
  lead?: UserBrief;
  created_by: UserBrief;
  tags: string[];
  incident_count: number;
  incidents: IncidentListItem[];
  created_at: string;
  updated_at: string;
}

export interface IncidentGroupWithIncidents extends CaseItem {
  incidents: IncidentListItem[];
}

// Automations
export type AutomationStatus = "draft" | "active" | "disabled" | "archived";

export interface AutomationItem {
  id: string;
  name: string;
  description?: string;
  status: AutomationStatus;
  version: number;
  created_by: UserBrief;
  tags: string[];
  created_at: string;
  updated_at: string;
}

// Executions
export type ExecutionStatus =
  | "pending"
  | "queued"
  | "running"
  | "completed"
  | "failed"
  | "cancelled"
  | "timed_out";

export interface ExecutionItem {
  id: string;
  automation_id: string;
  automation_name?: string;
  triggered_by: UserBrief;
  status: ExecutionStatus;
  celery_task_id?: string;
  worker_id?: string;
  started_at?: string;
  completed_at?: string;
  duration_ms?: number;
  created_at: string;
}

export interface ExecutionDetail extends ExecutionItem {
  incident_id?: string;
  case_id?: string;
  worker_id?: string;
  parameters: Record<string, unknown>;
  stdout?: string;
  stderr?: string;
  result_data?: Record<string, unknown>;
  exit_code?: number;
  error_message?: string;
}

// Users (admin)
export interface UserRead {
  id: string;
  username: string;
  email: string;
  display_name: string;
  is_active: boolean;
  is_mfa_enabled: boolean;
  last_login_at?: string;
  roles: string[];
  created_at: string;
  updated_at: string;
}

// Timeline
export type TimelineEntryType =
  | "status_change"
  | "severity_change"
  | "assignment"
  | "comment"
  | "automation_run"
  | "automation_result"
  | "evidence"
  | "escalation"
  | "external_update"
  | "created"
  | "linked"
  | "form_submission"
  | "note";

export interface TimelineEntry {
  id: string;
  incident_id?: string;
  case_id?: string;
  entry_type: TimelineEntryType;
  content: string;
  details: Record<string, unknown>;
  is_evidence: boolean;
  created_by?: UserBrief;
  created_at: string;
}

// Scheduled Jobs
export type ScheduleType = "cron" | "interval" | "calendar";

export interface CalendarConfig {
  days_of_week: number[]; // 0=Mon..6=Sun
  days_of_month: number[]; // 1-31
  months: number[]; // 1-12, empty=all
  time: string; // "HH:MM"
}

export interface ScheduledJobItem {
  id: string;
  automation_id: string;
  automation_name: string;
  name: string;
  description?: string;
  schedule_type: ScheduleType;
  cron_expression?: string;
  interval_seconds?: number;
  calendar_config?: CalendarConfig;
  timezone: string;
  is_enabled: boolean;
  last_run_at?: string;
  next_run_at?: string;
  run_count: number;
  start_date?: string;
  end_date?: string;
  created_by: UserBrief;
  created_at: string;
  updated_at: string;
}

// Roles
export interface Role {
  id: string;
  name: string;
  display_name: string;
  description?: string;
  is_system: boolean;
  permissions: Permission[];
}

export interface Permission {
  id: string;
  resource: string;
  action: string;
  description?: string;
}

// Webhooks
export type WebhookLogStatus = "success" | "error" | "rate_limited" | "normalization_failed";
export type TransformType = "direct" | "regex" | "template" | "static" | "lookup" | "lowercase" | "uppercase";

export interface Webhook {
  id: string;
  name: string;
  description?: string;
  secret_token: string;
  source_type: string;
  source_id?: string;
  source_name?: string;
  is_enabled: boolean;
  default_severity: IncidentSeverity;
  default_tags: string[];
  rate_limit_per_minute: number;
  ingest_url?: string;
  last_received_at?: string;
  total_received: number;
  created_by: UserBrief;
  created_at: string;
  updated_at: string;
}

export interface WebhookListItem {
  id: string;
  name: string;
  source_type: string;
  is_enabled: boolean;
  last_received_at?: string;
  total_received: number;
  created_at: string;
}

export interface WebhookLog {
  id: string;
  webhook_id: string;
  status: WebhookLogStatus;
  request_body: Record<string, unknown>;
  normalized_data?: Record<string, unknown>;
  incident_id?: string;
  error_message?: string;
  processing_time_ms?: number;
  remote_ip?: string;
  created_at: string;
}

// Normalization
export interface NormalizationGroup {
  id: string;
  name: string;
  display_name: string;
  description?: string;
  icon?: string;
  display_order: number;
}

export interface NormalizationRule {
  id: string;
  group_id: string;
  group?: NormalizationGroup;
  source_path: string;
  target_field: string;
  transform_type: TransformType;
  transform_config: Record<string, unknown>;
  is_required: boolean;
  default_value?: unknown;
  display_order: number;
  is_enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface NormalizationTestResult {
  normalized: Record<string, unknown>;
  errors: string[];
  warnings: string[];
}

// Monitoring
export type ComponentStatus = "healthy" | "degraded" | "unhealthy" | "unknown";
export type AlertSeverity = "info" | "warning" | "critical";
export type AlertStatusType = "active" | "acknowledged" | "resolved";

export interface ComponentHealth {
  component_type: string;
  component_id: string;
  status: ComponentStatus;
  metrics: Record<string, number | string>;
  last_check_at?: string;
}

export interface SystemHealthOverview {
  overall_status: ComponentStatus;
  components: ComponentHealth[];
  uptime_seconds: number;
  timestamp: string;
}

export interface AlertItem {
  id: string;
  rule_id?: string;
  component_type: string;
  component_id: string;
  severity: AlertSeverity;
  title: string;
  message: string;
  metric_value?: number;
  status: AlertStatusType;
  acknowledged_by?: UserBrief;
  acknowledged_at?: string;
  resolved_at?: string;
  created_at: string;
}

export interface AlertRule {
  id: string;
  name: string;
  description?: string;
  component_type: string;
  metric_key: string;
  condition: string;
  threshold: number;
  severity: AlertSeverity;
  is_enabled: boolean;
  cooldown_seconds: number;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface MonitoringAgent {
  id: string;
  name: string;
  description?: string;
  component_type: string;
  check_interval_seconds: number;
  is_enabled: boolean;
  last_check_at?: string;
  last_status?: string;
  consecutive_failures: number;
  is_alive: boolean;
  created_at: string;
  updated_at: string;
}

export interface QuorumMember {
  instance_id: string;
  hostname: string;
  started_at: string;
  last_heartbeat: string;
  is_alive: boolean;
}

export interface QuorumStatus {
  has_quorum: boolean;
  active_members: number;
  total_members: number;
  quorum_threshold: number;
  members: QuorumMember[];
}

export interface HealthMetricSnapshot {
  id: string;
  component_type: string;
  component_id: string;
  status: ComponentStatus;
  metrics: Record<string, number | string>;
  recorded_at: string;
}

// Versions
export interface VersionItem {
  id: string;
  version_number: number;
  name: string | null;
  description: string | null;
  created_by: UserBrief;
  created_at: string;
}

// Dependencies
export interface DependencyItem {
  id: string;
  type: "automation" | "code_block";
  name: string | null;
}

export interface AutomationDependencies {
  dependencies: DependencyItem[];
  dependents: DependencyItem[];
}

export interface DependencyGraphData {
  nodes: Array<{
    id: string;
    type: "automation" | "code_block";
    name: string;
    status?: string;
    version?: number;
    language?: string;
  }>;
  edges: Array<{
    source: string;
    target: string;
    type: string;
  }>;
}

// Incident Notes
export interface IncidentNote {
  id: string;
  incident_id: string;
  content: string;
  is_evidence: boolean;
  created_by: UserBrief;
  updated_by?: UserBrief;
  created_at: string;
  updated_at: string;
}

// Incident Files
export interface IncidentFile {
  id: string;
  incident_id: string;
  filename: string;
  content_type: string;
  file_size: number;
  description?: string;
  is_evidence: boolean;
  uploaded_by: UserBrief;
  created_at: string;
  expires_at?: string;
  can_delete: boolean;
}

// Webhook Sources
export interface WebhookSource {
  id: string;
  name: string;
  description?: string;
  icon?: string;
  automations: SourceAutomation[];
  created_at: string;
  updated_at: string;
}

export interface WebhookSourceListItem {
  id: string;
  name: string;
  description?: string;
  icon?: string;
  automation_count: number;
  created_at: string;
}

export interface SourceAutomation {
  id: string;
  source_id: string;
  automation_id: string;
  automation_name: string;
  is_enabled: boolean;
  run_order: number;
  created_at: string;
}

// Form Definitions
export type FormFieldType = "text" | "textarea" | "number" | "select" | "checkbox" | "date";

export interface FormField {
  key: string;
  label: string;
  type: FormFieldType;
  required: boolean;
  options: string[];
  placeholder?: string;
  help_text?: string;
}

export interface FormDefinition {
  id: string;
  name: string;
  description?: string;
  fields: FormField[];
  is_active: boolean;
  created_by: UserBrief;
  updated_by?: UserBrief;
  created_at: string;
  updated_at: string;
}

export interface FormDefinitionBrief {
  id: string;
  name: string;
  description?: string;
  is_active: boolean;
}

// Form Submissions
export interface FormSubmission {
  id: string;
  incident_id: string;
  form_definition_id: string;
  form_definition: FormDefinitionBrief;
  data: Record<string, unknown>;
  is_evidence: boolean;
  submitted_by: UserBrief;
  created_at: string;
}

// Issues
export type IssueStatus = "open" | "in_progress" | "resolved" | "closed" | "wont_fix";
export type IssueLinkTargetType =
  | "incident"
  | "automation"
  | "scheduled_job"
  | "role"
  | "code_library_block"
  | "normalization_rule"
  | "case"
  | "execution_log";

export interface GraphAnnotation {
  x: number;
  y: number;
  width: number;
  height: number;
  automation_version: number;
  node_id?: string;
}

export interface IssueLink {
  id: string;
  target_type: IssueLinkTargetType;
  target_id: string;
  target_name?: string;
}

export interface IssueNote {
  id: string;
  issue_id: string;
  content: string;
  is_evidence: boolean;
  created_by: UserBrief;
  updated_by?: UserBrief;
  created_at: string;
  updated_at: string;
}

export interface IssueChecklistItem {
  id: string;
  content: string;
  is_checked: boolean;
  sort_order: number;
  created_by: UserBrief;
  created_at: string;
}

export interface IssueItem {
  id: string;
  title: string;
  status: IssueStatus;
  assigned_to?: UserBrief;
  created_by: UserBrief;
  link_count: number;
  note_count: number;
  checklist_total: number;
  checklist_checked: number;
  created_at: string;
  updated_at: string;
}

export interface IssueDetail extends IssueItem {
  description?: string;
  closed_at?: string;
  graph_annotation?: GraphAnnotation;
  links: IssueLink[];
}

export interface GraphIssueItem {
  id: string;
  title: string;
  description?: string;
  status: IssueStatus;
  assigned_to?: UserBrief;
  graph_annotation: GraphAnnotation;
  created_at: string;
  updated_at: string;
}

// Wiki
export type WikiPageStatus = "draft" | "published" | "archived";

export interface WikiPageListItem {
  id: string;
  title: string;
  slug: string;
  parent_id: string | null;
  sort_order: number;
  tags: string[];
  status: WikiPageStatus;
  version: number;
  icon: string | null;
  created_by: UserBrief;
  updated_by: UserBrief | null;
  child_count: number;
  created_at: string;
  updated_at: string;
}

export interface WikiPage extends WikiPageListItem {
  content: string | null;
}

export interface WikiTreeNode {
  id: string;
  title: string;
  slug: string;
  icon: string | null;
  sort_order: number;
  status: string;
  children: WikiTreeNode[];
}

export interface WikiBreadcrumb {
  id: string;
  title: string;
  slug: string;
}

export interface WikiPageVersion {
  id: string;
  page_id: string;
  version_number: number;
  title: string | null;
  content: string | null;
  tags: string[] | null;
  change_summary: string | null;
  created_by: UserBrief;
  created_at: string;
}

export interface WikiPagePermission {
  page_id: string;
  role_id: string;
  role_name: string;
  can_read: boolean;
  can_edit: boolean;
}

export interface WikiSearchResult {
  id: string;
  title: string;
  slug: string;
  snippet: string;
  tags: string[];
  updated_at: string;
}

// Case Notes
export interface CaseNote {
  id: string;
  case_id: string;
  content: string;
  is_evidence: boolean;
  created_by: UserBrief;
  updated_by?: UserBrief;
  created_at: string;
  updated_at: string;
}

// Case Files
export interface CaseFile {
  id: string;
  case_id: string;
  filename: string;
  content_type: string;
  file_size: number;
  description?: string;
  is_evidence: boolean;
  uploaded_by: UserBrief;
  created_at: string;
  expires_at?: string;
  can_delete: boolean;
}

// Case Form Submissions
export interface CaseFormSubmission {
  id: string;
  case_id: string;
  form_definition_id: string;
  form_definition: FormDefinitionBrief;
  data: Record<string, unknown>;
  is_evidence: boolean;
  submitted_by: UserBrief;
  created_at: string;
}

// Incident Automation Execution (from /incidents/{id}/automations)
export interface IncidentAutomationExecution {
  id: string;
  automation_id: string;
  automation_name: string;
  status: ExecutionStatus;
  triggered_by: string;
  parameters: Record<string, unknown>;
  started_at?: string;
  completed_at?: string;
  duration_ms?: number;
  created_at: string;
  is_evidence: boolean;
}

// Git Sync
export interface GitSyncStatus {
  enabled: boolean;
  remote_url: string;
  branch: string;
  entity_types: string[];
  interval_seconds: number;
  last_sync_at: string | null;
  last_status: string | null;
  last_commit: {
    sha: string;
    message: string;
    author: string;
    date: string;
  } | null;
  repo_initialized: boolean;
}

export interface GitSyncLog {
  id: string;
  sync_type: string;
  status: string;
  entities_pushed: number;
  entities_pulled: number;
  conflicts: { entity_type: string; entity_name: string; resolution: string }[];
  error_message: string | null;
  started_at: string;
  completed_at: string | null;
  duration_ms: number | null;
  triggered_by: string;
}

export interface GitSyncLogsResponse {
  data: GitSyncLog[];
  total: number;
}

export interface GitSyncConfig {
  git_sync_enabled: string;
  git_sync_remote_url: string;
  git_sync_branch: string;
  git_sync_interval_seconds: string;
  git_sync_auth_type: string;
  git_sync_auth_token: string;
  git_sync_ssh_key_path: string;
  git_sync_entity_types: string;
}
