import json
import logging
from datetime import UTC, datetime

from sqlmodel import Field, Session, SQLModel, create_engine, select

from paos.config.settings import settings
from paos.core.models import InputItem, ProcessedItem
from paos.storage.base import BaseStorage

logger = logging.getLogger(__name__)


class RawInputTable(SQLModel, table=True):
    """原始输入表"""

    __tablename__ = "raw_input"

    id: int | None = Field(default=None, primary_key=True)
    source: str = Field(index=True)
    content: str
    metadata_json: str = Field(default="{}")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ProcessedItemTable(SQLModel, table=True):
    """提纯结果表"""

    __tablename__ = "processed_item"

    id: int | None = Field(default=None, primary_key=True)
    source: str = Field(index=True)
    raw_content: str
    distilled_content: str
    tags_json: str = Field(default="[]")
    metadata_json: str = Field(default="{}")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SQLiteStorage(BaseStorage):
    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path or settings.db_path
        self.engine = create_engine(f"sqlite:///{self.db_path}")

    def init_db(self) -> None:
        SQLModel.metadata.create_all(self.engine)
        logger.info("SQLite database initialized at %s", self.db_path)

    def save_raw(self, item: InputItem) -> int:
        record = RawInputTable(
            source=item.source,
            content=item.content,
            metadata_json=json.dumps(item.metadata, ensure_ascii=False),
            created_at=item.timestamp,
        )
        with Session(self.engine) as session:
            session.add(record)
            session.commit()
            session.refresh(record)
            return record.id or 0

    def save_processed(self, item: ProcessedItem) -> int:
        record = ProcessedItemTable(
            source=item.source,
            raw_content=item.raw_content,
            distilled_content=item.distilled_content,
            tags_json=json.dumps(item.tags, ensure_ascii=False),
            metadata_json=json.dumps(item.metadata, ensure_ascii=False),
            created_at=item.created_at,
        )
        with Session(self.engine) as session:
            session.add(record)
            session.commit()
            session.refresh(record)
            return record.id or 0

    def get_processed(self, item_id: int) -> ProcessedItem | None:
        with Session(self.engine) as session:
            record = session.get(ProcessedItemTable, item_id)
            if not record:
                return None
            return self._to_processed_item(record)

    def list_processed(self, limit: int = 10, offset: int = 0) -> list[ProcessedItem]:
        with Session(self.engine) as session:
            statement = select(ProcessedItemTable).order_by(ProcessedItemTable.created_at.desc()).offset(offset).limit(limit)
            results = session.exec(statement).all()
            return [self._to_processed_item(r) for r in results]

    def update_processed(self, item: ProcessedItem) -> bool:
        with Session(self.engine) as session:
            record = session.get(ProcessedItemTable, item.id)
            if not record:
                return False
            record.distilled_content = item.distilled_content
            record.tags_json = json.dumps(item.tags, ensure_ascii=False)
            record.metadata_json = json.dumps(item.metadata, ensure_ascii=False)
            session.add(record)
            session.commit()
            return True

    @staticmethod
    def _to_processed_item(record: ProcessedItemTable) -> ProcessedItem:
        return ProcessedItem(
            id=record.id,
            source=record.source,
            raw_content=record.raw_content,
            distilled_content=record.distilled_content,
            tags=json.loads(record.tags_json),
            metadata=json.loads(record.metadata_json),
            created_at=record.created_at,
        )
