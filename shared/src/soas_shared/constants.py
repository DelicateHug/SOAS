"""Shared enums, status codes, and constants."""

from enum import StrEnum


class IncidentSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


class IncidentStatus(StrEnum):
    DETECTED = "detected"
    TRIAGING = "triaging"
    INVESTIGATING = "investigating"
    CONTAINING = "containing"
    REMEDIATING = "remediating"
    RESOLVED = "resolved"
    CLOSED = "closed"
    FALSE_POSITIVE = "false_positive"


ALLOWED_INCIDENT_TRANSITIONS: dict[IncidentStatus, list[IncidentStatus]] = {
    IncidentStatus.DETECTED: [IncidentStatus.TRIAGING, IncidentStatus.FALSE_POSITIVE],
    IncidentStatus.TRIAGING: [
        IncidentStatus.INVESTIGATING,
        IncidentStatus.FALSE_POSITIVE,
        IncidentStatus.DETECTED,
    ],
    IncidentStatus.INVESTIGATING: [
        IncidentStatus.CONTAINING,
        IncidentStatus.REMEDIATING,
        IncidentStatus.TRIAGING,
    ],
    IncidentStatus.CONTAINING: [IncidentStatus.REMEDIATING, IncidentStatus.INVESTIGATING],
    IncidentStatus.REMEDIATING: [IncidentStatus.RESOLVED, IncidentStatus.CONTAINING],
    IncidentStatus.RESOLVED: [IncidentStatus.CLOSED, IncidentStatus.REMEDIATING],
    IncidentStatus.CLOSED: [],
    IncidentStatus.FALSE_POSITIVE: [IncidentStatus.DETECTED],
}


class CaseStatus(StrEnum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    PENDING = "pending"
    CLOSED = "closed"
    ARCHIVED = "archived"


class AutomationStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    DISABLED = "disabled"
    ARCHIVED = "archived"


class ExecutionStatus(StrEnum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


class ScheduleType(StrEnum):
    CRON = "cron"
    INTERVAL = "interval"
    CALENDAR = "calendar"


class TimelineEntryType(StrEnum):
    STATUS_CHANGE = "status_change"
    SEVERITY_CHANGE = "severity_change"
    ASSIGNMENT = "assignment"
    COMMENT = "comment"
    AUTOMATION_RUN = "automation_run"
    AUTOMATION_RESULT = "automation_result"
    EVIDENCE = "evidence"
    ESCALATION = "escalation"
    EXTERNAL_UPDATE = "external_update"
    CREATED = "created"
    LINKED = "linked"
    FORM_SUBMISSION = "form_submission"
    NOTE = "note"


class IncidentRole(StrEnum):
    LEAD = "lead"
    RESPONDER = "responder"
    OBSERVER = "observer"


class WebhookLogStatus(StrEnum):
    SUCCESS = "success"
    ERROR = "error"
    RATE_LIMITED = "rate_limited"
    NORMALIZATION_FAILED = "normalization_failed"


class IssueStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"
    WONT_FIX = "wont_fix"


class IssueLinkTargetType(StrEnum):
    INCIDENT = "incident"
    AUTOMATION = "automation"
    SCHEDULED_JOB = "scheduled_job"
    ROLE = "role"
    CODE_LIBRARY_BLOCK = "code_library_block"
    NORMALIZATION_RULE = "normalization_rule"
    CASE = "case"
    EXECUTION_LOG = "execution_log"


class TransformType(StrEnum):
    DIRECT = "direct"
    REGEX = "regex"
    TEMPLATE = "template"
    STATIC = "static"
    LOOKUP = "lookup"
    LOWERCASE = "lowercase"
    UPPERCASE = "uppercase"


# Prebuilt system role names
SYSTEM_ROLES = {
    "admin": "Administrator",
    "soc_manager": "SOC Manager",
    "soc_analyst_l3": "SOC Analyst L3",
    "soc_analyst_l2": "SOC Analyst L2",
    "soc_analyst_l1": "SOC Analyst L1",
    "viewer": "Viewer",
}

# All resource:action permission pairs
PERMISSIONS = [
    ("user", "create"),
    ("user", "read"),
    ("user", "update"),
    ("user", "delete"),
    ("role", "create"),
    ("role", "read"),
    ("role", "update"),
    ("role", "delete"),
    ("incident", "create"),
    ("incident", "read"),
    ("incident", "update"),
    ("incident", "delete"),
    ("incident", "assign"),
    ("incident", "close"),
    ("case", "create"),
    ("case", "read"),
    ("case", "update"),
    ("case", "delete"),
    ("case", "close"),
    ("automation", "create"),
    ("automation", "read"),
    ("automation", "update"),
    ("automation", "delete"),
    ("automation", "execute"),
    ("execution", "read"),
    ("execution", "cancel"),
    ("timeline", "create"),
    ("timeline", "read"),
    ("dashboard", "read"),
    ("admin", "access"),
    ("graph_editor", "access"),
    ("graph_editor", "test_run"),
    ("soas_variable", "create"),
    ("soas_variable", "read"),
    ("soas_variable", "update"),
    ("soas_variable", "delete"),
    ("job", "create"),
    ("job", "read"),
    ("job", "update"),
    ("job", "delete"),
    ("monitoring", "read"),
    ("monitoring", "admin"),
    ("webhook", "create"),
    ("webhook", "read"),
    ("webhook", "update"),
    ("webhook", "delete"),
    ("normalization", "create"),
    ("normalization", "read"),
    ("normalization", "update"),
    ("normalization", "delete"),
    ("form_definition", "create"),
    ("form_definition", "read"),
    ("form_definition", "update"),
    ("form_definition", "delete"),
    ("form_submission", "create"),
    ("form_submission", "read"),
    ("form_submission", "update"),
    ("form_submission", "delete"),
    ("issue", "create"),
    ("issue", "read"),
    ("issue", "update"),
    ("issue", "delete"),
]


class ComponentStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class AlertSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertStatus(StrEnum):
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class ComponentType(StrEnum):
    API = "api"
    POSTGRES = "postgres"
    REDIS = "redis"
    CELERY_WORKER = "celery_worker"
    CELERY_BEAT = "celery_beat"
    WEBSOCKET = "websocket"

# SLA definitions (in minutes)
SLA_RESPONSE = {
    IncidentSeverity.CRITICAL: 15,
    IncidentSeverity.HIGH: 30,
    IncidentSeverity.MEDIUM: 120,
    IncidentSeverity.LOW: 480,
    IncidentSeverity.INFORMATIONAL: None,
}

SLA_RESOLUTION = {
    IncidentSeverity.CRITICAL: 240,
    IncidentSeverity.HIGH: 480,
    IncidentSeverity.MEDIUM: 1440,
    IncidentSeverity.LOW: 4320,
    IncidentSeverity.INFORMATIONAL: None,
}
