from __future__ import annotations

from jobpilot.llm.client import LLMClient
from jobpilot.llm.prompts import build_tailor_prompt
from jobpilot.models import JDAnalysis, JobPosting, ResumeData, TailoredResume, TailorResponse


class HallucinationError(Exception):
    pass


def _normalize_bullet(text: str) -> str:
    return text.replace("*", "").replace("_", "").strip().lower()


def _validate_no_fabrication(base: ResumeData, tailored: TailorResponse) -> None:
    base_pairs = {(e.company, e.title) for e in base.experience}
    base_bullets = {_normalize_bullet(b) for e in base.experience for b in e.bullets}

    for exp in tailored.experiences:
        if (exp.company, exp.title) not in base_pairs:
            raise HallucinationError(f"Unknown experience entry: {exp.company} / {exp.title}")
        for bullet in exp.bullets:
            if _normalize_bullet(bullet) not in base_bullets:
                raise HallucinationError("Tailored resume introduced a new bullet/achievement")


def tailor_resume(
    llm_client: LLMClient,
    base_resume: ResumeData,
    job: JobPosting,
    analysis: JDAnalysis,
) -> TailoredResume:
    prompt = build_tailor_prompt(base_resume=base_resume, job=job, analysis=analysis)
    response = llm_client.generate_structured(
        prompt=prompt,
        schema_name="tailored_resume",
        output_model=TailorResponse,
    )
    _validate_no_fabrication(base_resume, response)

    base_payload = base_resume.model_dump(exclude={"summary", "skills", "experience"})
    return TailoredResume(
        **base_payload,
        summary=response.summary,
        skills=response.skills or base_resume.skills,
        experience=response.experiences,
        target_company=job.company,
        target_role=job.role,
    )
