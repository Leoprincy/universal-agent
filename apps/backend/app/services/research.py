import uuid
from datetime import datetime, timezone
from typing import Sequence

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, UnprocessableEntityError
from app.database.models import OpportunityResearchAssociation, ResearchRecord
from app.schemas.research import ResearchRecordCreate, ResearchRecordUpdate


class ResearchService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_records(
        self,
        project_id: str,
        source_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[Sequence[ResearchRecord], int]:
        base_query = select(ResearchRecord).where(ResearchRecord.project_id == project_id)
        count_query = (
            select(func.count())
            .select_from(ResearchRecord)
            .where(ResearchRecord.project_id == project_id)
        )

        if source_type:
            base_query = base_query.where(ResearchRecord.source_type == source_type)
            count_query = count_query.where(ResearchRecord.source_type == source_type)

        total = self._session.scalar(count_query) or 0
        items_query = (
            base_query.order_by(ResearchRecord.collected_at.desc(), ResearchRecord.id.desc())
            .offset(offset)
            .limit(limit)
        )
        items = self._session.scalars(items_query).all()
        return items, total

    def get_record(self, record_id: str, project_id: str) -> ResearchRecord:
        stmt = select(ResearchRecord).where(
            (ResearchRecord.id == record_id) & (ResearchRecord.project_id == project_id)
        )
        record = self._session.scalar(stmt)
        if not record:
            raise NotFoundError(f"Research record '{record_id}' not found in this project")
        return record

    def create_record(self, data: ResearchRecordCreate, project_id: str) -> ResearchRecord:
        record = ResearchRecord(
            id=str(uuid.uuid4()),
            project_id=project_id,
            title=data.title,
            source_type=data.source_type,
            source_url=data.source_url,
            source_name=data.source_name,
            author=data.author,
            source_quote=data.source_quote,
            observation_summary=data.observation_summary,
            interpretation_notes=data.interpretation_notes,
            evidence_data=data.evidence_data,
            observed_at=data.observed_at,
            published_at=data.published_at,
            collected_at=datetime.now(timezone.utc),
            metadata_json=data.metadata_json,
        )
        try:
            self._session.add(record)
            self._session.commit()
            self._session.refresh(record)
            return record
        except Exception:
            self._session.rollback()
            raise

    def update_record(
        self, record_id: str, data: ResearchRecordUpdate, project_id: str
    ) -> ResearchRecord:
        record = self.get_record(record_id, project_id=project_id)

        # Merge fields
        update_data = data.model_dump(exclude_unset=True, by_alias=False)
        for field, value in update_data.items():
            if field == "metadata_json":
                record.metadata_json = value
            elif hasattr(record, field):
                setattr(record, field, value)

        record.updated_at = datetime.now(timezone.utc)

        # Re-validate with model validator if fields changed
        full_dict = {
            "title": record.title,
            "source_type": record.source_type,
            "source_url": record.source_url,
            "source_name": record.source_name,
            "author": record.author,
            "source_quote": record.source_quote,
            "observation_summary": record.observation_summary,
            "interpretation_notes": record.interpretation_notes,
            "evidence_data": record.evidence_data,
            "observed_at": record.observed_at,
            "published_at": record.published_at,
            "metadata_json": record.metadata_json,
        }
        # Validates per source_type
        try:
            ResearchRecordCreate.model_validate(full_dict)
        except ValidationError as exc:
            raise UnprocessableEntityError(
                "Updated research record violates source-type requirements",
                code="validation_error",
            ) from exc

        try:
            self._session.commit()
            self._session.refresh(record)
            return record
        except Exception:
            self._session.rollback()
            raise

    def delete_record(self, record_id: str, project_id: str) -> None:
        record = self.get_record(record_id, project_id=project_id)

        # Guard: research linked to opportunities cannot be deleted
        link_count = self._session.scalar(
            select(func.count())
            .select_from(OpportunityResearchAssociation)
            .where(OpportunityResearchAssociation.research_id == record.id)
        )
        if link_count and link_count > 0:
            raise ConflictError(
                "Research record is linked to one or more opportunities. Unlink it first to preserve evidence traceability.",
                code="cannot_delete_linked_research",
            )

        try:
            self._session.delete(record)
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise
