"""Case form submission endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from soas_backend.api.deps import get_current_user, require_permission
from soas_backend.database import get_db
from soas_backend.models.user import User
from soas_backend.services.case_form_submission_service import CaseFormSubmissionService
from soas_shared.schemas.case_form_submission import CaseFormSubmissionCreate, CaseFormSubmissionRead
from soas_shared.schemas.form_definition import FormDefinitionBrief
from soas_shared.schemas.user import UserBrief

router = APIRouter(tags=["case-form-submissions"])


def _user_brief(user) -> UserBrief | None:
    if user is None:
        return None
    return UserBrief(id=user.id, username=user.username, display_name=user.display_name)


def _submission_to_read(sub) -> CaseFormSubmissionRead:
    return CaseFormSubmissionRead(
        id=sub.id,
        case_id=sub.case_id,
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
    "/cases/{case_id}/form-submissions",
    response_model=list[CaseFormSubmissionRead],
)
async def list_case_form_submissions(
    case_id: UUID,
    _: dict = Depends(require_permission("case_form_submission", "read")),
    db: AsyncSession = Depends(get_db),
):
    svc = CaseFormSubmissionService(db)
    submissions = await svc.list_for_case(case_id)
    return [_submission_to_read(s) for s in submissions]


@router.post(
    "/cases/{case_id}/form-submissions",
    response_model=CaseFormSubmissionRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_case_form_submission(
    case_id: UUID,
    body: CaseFormSubmissionCreate,
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("case_form_submission", "create")),
    db: AsyncSession = Depends(get_db),
):
    svc = CaseFormSubmissionService(db)
    try:
        submission = await svc.create(
            case_id=case_id,
            form_definition_id=body.form_definition_id,
            data=body.data,
            submitted_by=current_user.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _submission_to_read(submission)


@router.delete(
    "/cases/{case_id}/form-submissions/{submission_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_case_form_submission(
    case_id: UUID,
    submission_id: UUID,
    _: dict = Depends(require_permission("case_form_submission", "delete")),
    db: AsyncSession = Depends(get_db),
):
    svc = CaseFormSubmissionService(db)
    submission = await svc.get(submission_id)
    if not submission or submission.case_id != case_id:
        raise HTTPException(status_code=404, detail="Form submission not found")
    await svc.delete(submission_id)
    return None


@router.post(
    "/cases/{case_id}/form-submissions/{submission_id}/evidence",
    response_model=CaseFormSubmissionRead,
)
async def toggle_submission_evidence(
    case_id: UUID,
    submission_id: UUID,
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("case_form_submission", "read")),
    db: AsyncSession = Depends(get_db),
):
    svc = CaseFormSubmissionService(db)
    submission = await svc.get(submission_id)
    if not submission or submission.case_id != case_id:
        raise HTTPException(status_code=404, detail="Form submission not found")

    submission = await svc.toggle_evidence(submission_id, current_user.id)
    return _submission_to_read(submission)
