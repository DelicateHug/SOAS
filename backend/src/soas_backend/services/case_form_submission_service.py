"""Case form submission service -- creating submissions and toggling evidence."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from soas_backend.models.case_form_submission import CaseFormSubmission
from soas_backend.models.form_definition import FormDefinition
from soas_backend.models.timeline import TimelineEntry


class CaseFormSubmissionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_for_case(self, case_id: UUID) -> list[CaseFormSubmission]:
        result = await self.db.execute(
            select(CaseFormSubmission)
            .where(CaseFormSubmission.case_id == case_id)
            .options(
                selectinload(CaseFormSubmission.submitter),
                selectinload(CaseFormSubmission.form_definition),
            )
            .order_by(CaseFormSubmission.created_at.desc())
        )
        return list(result.scalars().all())

    async def get(self, submission_id: UUID) -> CaseFormSubmission | None:
        result = await self.db.execute(
            select(CaseFormSubmission)
            .where(CaseFormSubmission.id == submission_id)
            .options(
                selectinload(CaseFormSubmission.submitter),
                selectinload(CaseFormSubmission.form_definition),
            )
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        case_id: UUID,
        form_definition_id: UUID,
        data: dict,
        submitted_by: UUID,
    ) -> CaseFormSubmission:
        defn_result = await self.db.execute(
            select(FormDefinition).where(FormDefinition.id == form_definition_id)
        )
        defn = defn_result.scalar_one_or_none()
        if not defn:
            raise ValueError("Form definition not found")
        if not defn.is_active:
            raise ValueError("Form definition is not active")

        for field in defn.fields:
            if field.get("required") and not data.get(field["key"]):
                raise ValueError(f"Required field '{field['label']}' is missing")

        submission = CaseFormSubmission(
            case_id=case_id,
            form_definition_id=form_definition_id,
            data=data,
            submitted_by=submitted_by,
        )
        self.db.add(submission)
        await self.db.flush()

        self.db.add(
            TimelineEntry(
                case_id=case_id,
                entry_type="form_submission",
                content=f"Form submitted: {defn.name}",
                details={
                    "form_definition_id": str(form_definition_id),
                    "form_name": defn.name,
                    "submission_id": str(submission.id),
                },
                created_by=submitted_by,
            )
        )
        await self.db.flush()

        return await self.get(submission.id)

    async def delete(self, submission_id: UUID) -> bool:
        submission = await self.get(submission_id)
        if not submission:
            return False
        await self.db.delete(submission)
        await self.db.flush()
        return True

    async def toggle_evidence(self, submission_id: UUID, user_id: UUID) -> CaseFormSubmission | None:
        submission = await self.get(submission_id)
        if not submission:
            return None
        submission.is_evidence = not submission.is_evidence
        await self.db.flush()

        action = "marked as evidence" if submission.is_evidence else "unmarked as evidence"
        self.db.add(
            TimelineEntry(
                case_id=submission.case_id,
                entry_type="evidence",
                content=f"Form submission {action}: {submission.form_definition.name}",
                details={
                    "submission_id": str(submission_id),
                    "is_evidence": submission.is_evidence,
                },
                created_by=user_id,
            )
        )
        await self.db.flush()

        return await self.get(submission_id)
