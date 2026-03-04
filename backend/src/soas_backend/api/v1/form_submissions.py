"""Form submission endpoints -- incident-scoped."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from soas_backend.api.deps import get_current_user, require_permission
from soas_backend.database import get_db
from soas_backend.models.user import User
from soas_backend.services.form_submission_service import FormSubmissionService
from soas_shared.schemas.form_definition import FormDefinitionBrief
from soas_shared.schemas.form_submission import FormSubmissionCreate, FormSubmissionRead
from soas_shared.schemas.user import UserBrief

router = APIRouter(tags=["form-submissions"])


def _user_brief(user) -> UserBrief | None:
    if user is None:
        return None
    return UserBrief(id=user.id, username=user.username, display_name=user.display_name)


def _submission_to_read(sub) -> FormSubmissionRead:
    return FormSubmissionRead(
        id=sub.id,
        incident_id=sub.incident_id,
        form_definition_id=sub.form_definition_id,
        form_definition=FormDefinitionBrief(
            id=sub.form_definition.id,
            name=sub.form_definition.name,
            description=sub.form_definition.description,
            is_active=sub.form_definition.is_active,
        ),
        data=sub.data,
        is_evidence=sub.is_evidence,
        submitted_by=_user_brief(sub.submitter),
        created_at=sub.created_at,
    )


@router.get(
    "/incidents/{incident_id}/form-submissions",
    response_model=list[FormSubmissionRead],
)
async def list_form_submissions(
    incident_id: UUID,
    _: dict = Depends(require_permission("form_submission", "read")),
    db: AsyncSession = Depends(get_db),
):
    svc = FormSubmissionService(db)
    submissions = await svc.list_for_incident(incident_id)
    return [_submission_to_read(s) for s in submissions]


@router.post(
    "/incidents/{incident_id}/form-submissions",
    response_model=FormSubmissionRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_form_submission(
    incident_id: UUID,
    body: FormSubmissionCreate,
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("form_submission", "create")),
    db: AsyncSession = Depends(get_db),
):
    svc = FormSubmissionService(db)
    try:
        submission = await svc.create(
            incident_id=incident_id,
            form_definition_id=body.form_definition_id,
            data=body.data,
            submitted_by=current_user.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _submission_to_read(submission)


@router.delete(
    "/incidents/{incident_id}/form-submissions/{submission_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_form_submission(
    incident_id: UUID,
    submission_id: UUID,
    _: dict = Depends(require_permission("form_submission", "delete")),
    db: AsyncSession = Depends(get_db),
):
    svc = FormSubmissionService(db)
    submission = await svc.get(submission_id)
    if not submission or submission.incident_id != incident_id:
        raise HTTPException(status_code=404, detail="Form submission not found")
    await svc.delete(submission_id)
    return None


@router.post(
    "/incidents/{incident_id}/form-submissions/{submission_id}/evidence",
    response_model=FormSubmissionRead,
)
async def toggle_submission_evidence(
    incident_id: UUID,
    submission_id: UUID,
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("form_submission", "update")),
    db: AsyncSession = Depends(get_db),
):
    svc = FormSubmissionService(db)
    submission = await svc.get(submission_id)
    if not submission or submission.incident_id != incident_id:
        raise HTTPException(status_code=404, detail="Form submission not found")

    submission = await svc.toggle_evidence(submission_id, current_user.id)
    return _submission_to_read(submission)
