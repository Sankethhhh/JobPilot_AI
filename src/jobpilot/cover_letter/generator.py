from __future__ import annotations

from pathlib import Path
import re

from jobpilot.llm.client import LLMClient
from jobpilot.llm.prompts import build_cover_letter_prompt
from jobpilot.models import CoverLetter, JobPosting, TailoredResume


def _slug(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_")


def generate_cover_letter(
    llm_client: LLMClient,
    job: JobPosting,
    resume: TailoredResume,
    output_dir: Path,
) -> CoverLetter:
    prompt = build_cover_letter_prompt(job=job, resume_summary=resume.summary, key_skills=resume.skills)
    cover_letter = llm_client.generate_structured(
        prompt=prompt,
        schema_name="cover_letter",
        output_model=CoverLetter,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{_slug(job.company)}_{_slug(job.role)}_cover_letter.txt"
    (output_dir / filename).write_text("\n".join(cover_letter.lines))
    return cover_letter
