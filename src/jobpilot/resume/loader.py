from __future__ import annotations

import json
from pathlib import Path

from jobpilot.models import CandidateProfile, ResumeData


def load_resume(path: Path) -> ResumeData:
    data = json.loads(path.read_text())
    return ResumeData.model_validate(data)


def to_candidate_profile(resume: ResumeData) -> CandidateProfile:
    return CandidateProfile(summary=resume.summary, skills=resume.skills)
