from pathlib import Path

from jobpilot.db.repo import ApplicationRepo
from jobpilot.models import ApplicationRecord, ApplicationStage


def test_repo_insert_and_stage_update(tmp_path):
    db_path = tmp_path / "test.db"
    schema_path = Path("src/jobpilot/db/schema.sql")
    repo = ApplicationRepo(db_path, schema_path)

    record_id = repo.add_or_update(
        ApplicationRecord(
            company="Acme",
            role="Engineer",
            country="Germany",
            match_score=80,
            resume_path="/tmp/r.pdf",
        )
    )

    repo.update_stage(record_id, ApplicationStage.interview, "Scheduled", True)
    rows = repo.list_applications(country="Germany", stage="Interview")

    assert len(rows) == 1
    assert rows[0].id == record_id
    assert rows[0].applied is True
