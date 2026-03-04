"""Case file upload/download service."""

import uuid as uuid_mod
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from soas_backend.config import settings
from soas_backend.models.case_file import CaseFile


class CaseFileService:
    def __init__(self, db: AsyncSession):
        self.db = db

    def _storage_dir(self, case_id: UUID) -> Path:
        base = Path(settings.file_storage_path)
        return base / "cases" / str(case_id)

    async def list_files(self, case_id: UUID) -> list[CaseFile]:
        result = await self.db.execute(
            select(CaseFile)
            .where(CaseFile.case_id == case_id)
            .options(selectinload(CaseFile.uploader))
            .order_by(CaseFile.created_at.desc())
        )
        return list(result.scalars().all())

    async def get(self, file_id: UUID) -> CaseFile | None:
        result = await self.db.execute(
            select(CaseFile)
            .where(CaseFile.id == file_id)
            .options(selectinload(CaseFile.uploader))
        )
        return result.scalar_one_or_none()

    async def upload(
        self,
        case_id: UUID,
        filename: str,
        content_type: str,
        file_bytes: bytes,
        uploaded_by: UUID,
        description: str | None = None,
        ttl_days: int = 0,
    ) -> CaseFile:
        storage_dir = self._storage_dir(case_id)
        storage_dir.mkdir(parents=True, exist_ok=True)

        safe_name = filename.replace("/", "_").replace("\\", "_")
        unique_name = f"{uuid_mod.uuid4().hex[:12]}_{safe_name}"
        file_path = storage_dir / unique_name
        file_path.write_bytes(file_bytes)

        relative_path = str(file_path.relative_to(Path(settings.file_storage_path)))

        expires_at = None
        if ttl_days > 0:
            expires_at = datetime.now(timezone.utc) + timedelta(days=ttl_days)

        record = CaseFile(
            case_id=case_id,
            filename=filename,
            storage_path=relative_path,
            content_type=content_type,
            file_size=len(file_bytes),
            description=description,
            uploaded_by=uploaded_by,
            expires_at=expires_at,
        )
        self.db.add(record)
        await self.db.flush()
        return await self.get(record.id)

    def get_file_path(self, file_record: CaseFile) -> Path:
        return Path(settings.file_storage_path) / file_record.storage_path

    async def delete(self, file_id: UUID) -> bool:
        record = await self.get(file_id)
        if not record:
            return False

        disk_path = self.get_file_path(record)
        if disk_path.exists():
            disk_path.unlink()

        await self.db.delete(record)
        await self.db.flush()
        return True

    async def toggle_evidence(self, file_id: UUID) -> CaseFile | None:
        record = await self.get(file_id)
        if not record:
            return None
        record.is_evidence = not record.is_evidence
        await self.db.flush()
        return await self.get(file_id)
