"""Incident pre-processing pipeline.

Composes:
  1. classifier_service.classify() → sets incident.category_key
  2. dedup_service.find_parent + link_to_parent → sets parent_incident_id
  3. template merge (future: apply IncidentTemplate.defaults)

Called by webhook_service after the raw payload has been normalised to
an Incident. Each step is independently optional and best-effort —
errors are logged but do not block ingest.
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from soas_backend.models.incident import Incident
from soas_backend.services.classifier_service import ClassifierService
from soas_backend.services.dedup_service import DedupService

logger = logging.getLogger(__name__)


class IncidentPreprocessor:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.classifier = ClassifierService(db)
        self.dedup = DedupService(db)

    async def run(self, incident: Incident) -> Incident:
        # 1. Classification
        try:
            key = await self.classifier.classify(incident)
            if key:
                incident.category_key = key
        except Exception:
            logger.exception("preprocessor: classifier failed for %s", incident.id)

        # 2. Dedup
        try:
            parent = await self.dedup.find_parent(incident)
            if parent is not None:
                await self.dedup.link_to_parent(incident, parent)
        except Exception:
            logger.exception("preprocessor: dedup failed for %s", incident.id)

        return incident
