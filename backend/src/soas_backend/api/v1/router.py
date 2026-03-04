"""Aggregate v1 API router."""

from fastapi import APIRouter

from soas_backend.api.v1.auth import router as auth_router
from soas_backend.api.v1.automations import router as automations_router
from soas_backend.api.v1.cases import router as cases_router
from soas_backend.api.v1.dashboard import router as dashboard_router
from soas_backend.api.v1.executions import router as executions_router
from soas_backend.api.v1.graph_editor import router as graph_editor_router
from soas_backend.api.v1.jobs import router as jobs_router
from soas_backend.api.v1.incident_variables import router as incident_variables_router
from soas_backend.api.v1.incidents import router as incidents_router
from soas_backend.api.v1.soas_variables import router as soas_variables_router
from soas_backend.api.v1.roles import router as roles_router
from soas_backend.api.v1.timelines import router as timelines_router
from soas_backend.api.v1.users import router as users_router
from soas_backend.api.v1.monitoring import router as monitoring_router
from soas_backend.api.v1.code_library import router as code_library_router
from soas_backend.api.v1.normalization import router as normalization_router
from soas_backend.api.v1.webauthn_routes import router as webauthn_router
from soas_backend.api.v1.incident_automations import router as incident_automations_router
from soas_backend.api.v1.incident_files import router as incident_files_router
from soas_backend.api.v1.incident_notes import router as incident_notes_router
from soas_backend.api.v1.settings import router as settings_router
from soas_backend.api.v1.webhook_sources import router as webhook_sources_router
from soas_backend.api.v1.webhooks import ingest_router as webhook_ingest_router
from soas_backend.api.v1.webhooks import router as webhooks_router
from soas_backend.api.v1.form_definitions import router as form_definitions_router
from soas_backend.api.v1.form_submissions import router as form_submissions_router
from soas_backend.api.v1.issues import router as issues_router
from soas_backend.api.v1.wiki import router as wiki_router
from soas_backend.api.v1.git_sync import router as git_sync_router
from soas_backend.api.v1.case_notes import router as case_notes_router
from soas_backend.api.v1.case_files import router as case_files_router
from soas_backend.api.v1.case_form_submissions import router as case_form_submissions_router
from soas_backend.api.v1.case_automations import router as case_automations_router
from soas_backend.api.v1.user_secrets import router as user_secrets_router

v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(auth_router)
v1_router.include_router(webauthn_router)
v1_router.include_router(roles_router)
v1_router.include_router(incidents_router)
v1_router.include_router(cases_router)
v1_router.include_router(timelines_router)
v1_router.include_router(automations_router)
v1_router.include_router(executions_router)
v1_router.include_router(dashboard_router)
v1_router.include_router(users_router)
v1_router.include_router(graph_editor_router)
v1_router.include_router(soas_variables_router)
v1_router.include_router(incident_variables_router)
v1_router.include_router(jobs_router)
v1_router.include_router(monitoring_router)
v1_router.include_router(webhooks_router)
v1_router.include_router(webhook_ingest_router)
v1_router.include_router(normalization_router)
v1_router.include_router(code_library_router)
v1_router.include_router(incident_notes_router)
v1_router.include_router(incident_files_router)
v1_router.include_router(incident_automations_router)
v1_router.include_router(webhook_sources_router)
v1_router.include_router(form_definitions_router)
v1_router.include_router(form_submissions_router)
v1_router.include_router(settings_router)
v1_router.include_router(issues_router)
v1_router.include_router(wiki_router)
v1_router.include_router(git_sync_router)
v1_router.include_router(case_notes_router)
v1_router.include_router(case_files_router)
v1_router.include_router(case_form_submissions_router)
v1_router.include_router(case_automations_router)
v1_router.include_router(user_secrets_router)
