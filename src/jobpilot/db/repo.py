from __future__ import annotations

import sqlite3
from pathlib import Path

from jobpilot.models import ApplicationRecord, ApplicationStage


class ApplicationRepo:
    def __init__(self, db_path: Path, schema_path: Path):
        self.db_path = db_path
        self.schema_path = schema_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        sql = self.schema_path.read_text()
        with self._connect() as conn:
            conn.executescript(sql)
            conn.commit()

    def add_or_update(self, record: ApplicationRecord) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO applications (
                    company, role, country, match_score, resume_path,
                    cover_letter_text, applied, stage, notes, status_reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.company,
                    record.role,
                    record.country,
                    record.match_score,
                    record.resume_path,
                    record.cover_letter_text,
                    int(record.applied),
                    record.stage.value,
                    record.notes,
                    record.status_reason,
                ),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def update_stage(self, record_id: int, stage: ApplicationStage, notes: str = "", applied: bool = False) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE applications
                SET stage = ?, notes = ?, applied = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (stage.value, notes, int(applied), record_id),
            )
            conn.commit()

    def list_applications(self, country: str | None = None, stage: str | None = None) -> list[ApplicationRecord]:
        query = "SELECT * FROM applications"
        clauses: list[str] = []
        params: list[str] = []

        if country and country != "All":
            clauses.append("country = ?")
            params.append(country)
        if stage and stage != "All":
            clauses.append("stage = ?")
            params.append(stage)

        if clauses:
            query += " WHERE " + " AND ".join(clauses)

        query += " ORDER BY created_at DESC, match_score DESC"

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()

        records: list[ApplicationRecord] = []
        for row in rows:
            records.append(
                ApplicationRecord(
                    id=row["id"],
                    company=row["company"],
                    role=row["role"],
                    country=row["country"],
                    match_score=row["match_score"],
                    resume_path=row["resume_path"],
                    cover_letter_text=row["cover_letter_text"],
                    applied=bool(row["applied"]),
                    stage=row["stage"],
                    notes=row["notes"],
                    status_reason=row["status_reason"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
            )
        return records
