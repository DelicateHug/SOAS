"""Form submission service -- creating submissions and toggling evidence."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from soas_backend.models.form_definition import FormDefinition
from soas_backend.models.form_submission import FormSubmission
from soas_backend.models.timeline import TimelineEntry


class FormSubmissionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_for_incident(self, incident_id: UUID) -> list[FormSubmission]:
        result = await self.db.execute(
            select(FormSubmission)
            .where(FormSubmission.incident_id == incident_id)
            .options(
                selectinload(FormSubmission.submitter),
                selectinload(FormSubmission.form_definition),
            )
            .order_by(FormSubmission.created_at.desc())
        )
        return list(result.scalars().all())

    async def get(self, submission_id: UUID) -> FormSubmission | None:
        result = await self.db.execute(
            select(FormSubmission)
            .where(FormSubmission.id == submission_id)
            .options(
                selectinload(FormSubmission.submitter),
                selectinload(FormSubmission.form_definition),
            )
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        incident_id: UUID,
        form_definition_id: UUID,
        data: dict,
        submitted_by: UUID,
    ) -> FormSubmission:
        # Validate form definition exists and is active
        defn_result = await self.db.execute(
            select(FormDefinition).where(FormDefinition.id == form_definition_id)
        )
        defn = defn_result.scalar_one_or_none()
        if not defn:
            raise ValueError("Form definition not found")
        if not defn.is_active:
            raise ValueError("Form definition is not active")

        # Validate required fields
        for field in defn.fields:
            if field.get("required") and not data.get(field["key"]):
                raise ValueError(f"Required field '{field['label']}' is missing")

        submission = FormSubmission(
            incident_id=incident_id,
            form_definition_id=form_definition_id,
            data=data,
            submitted_by=submitted_by,
        )
        self.db.add(submission)
        await self.db.flush()

        # Create timeline entry
        self.db.add(
            TimelineEntry(
                incident_id=incident_id,
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

    async def toggle_evidence(self, submission_id: UUID, user_id: UUID) -> FormSubmission | None:
        submission = await self.get(submission_id)
        if not submission:
            return None
        submission.is_evidence = not submission.is_evidence
        await self.db.flush()

        # Create timeline entry for evidence toggle
        action = "marked as evidence" if submission.is_evidence else "unmarked as evidence"
        self.db.add(
            TimelineEntry(
                incident_id=submission.incident_id,
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
