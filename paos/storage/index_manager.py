import json
import os
from datetime import UTC, datetime
from typing import Any

from paos.config.settings import settings


class IndexManager:
    """管理 data/index.json，记录原文 → 提纯知识 → 生成输出的完整映射目录"""

    def __init__(self, data_dir: str | None = None) -> None:
        self.data_dir = data_dir or settings.data_dir
        self.index_path = os.path.join(self.data_dir, "index.json")
        self._ensure_dir()

    def _ensure_dir(self) -> None:
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(os.path.join(self.data_dir, "raw"), exist_ok=True)
        os.makedirs(os.path.join(self.data_dir, "processed"), exist_ok=True)
        os.makedirs(os.path.join(self.data_dir, "output"), exist_ok=True)

    def _load_index(self) -> list[dict[str, Any]]:
        if not os.path.exists(self.index_path):
            return []
        try:
            with open(self.index_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def _save_index(self, data: list[dict[str, Any]]) -> None:
        with open(self.index_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def add_entry(
        self,
        raw_id: int,
        raw_file: str,
        processed_id: int,
        processed_file: str,
        source: str,
        content_preview: str,
        distilled_preview: str,
    ) -> str:
        """添加一条新的原文→提纯知识的映射记录"""
        data = self._load_index()
        entry_id = f"E{processed_id:05d}"
        entry = {
            "entry_id": entry_id,
            "raw_id": raw_id,
            "raw_file": raw_file,
            "processed_id": processed_id,
            "processed_file": processed_file,
            "source": source,
            "content_preview": content_preview[:200],
            "distilled_preview": distilled_preview[:200],
            "output_files": {},
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
        }
        data.append(entry)
        self._save_index(data)
        return entry_id

    def add_output(self, processed_id: int, output_type: str, output_file: str) -> bool:
        """为指定 processed_id 关联输出生成文件"""
        data = self._load_index()
        for entry in data:
            if entry["processed_id"] == processed_id:
                entry["output_files"][output_type] = output_file
                entry["updated_at"] = datetime.now(UTC).isoformat()
                self._save_index(data)
                return True
        return False

    def get_entry_by_processed_id(self, processed_id: int) -> dict[str, Any] | None:
        data = self._load_index()
        for entry in data:
            if entry["processed_id"] == processed_id:
                return entry
        return None

    def list_entries(self, source: str | None = None) -> list[dict[str, Any]]:
        data = self._load_index()
        if source:
            return [e for e in data if e["source"] == source]
        return data
