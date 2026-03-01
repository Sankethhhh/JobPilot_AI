from pathlib import Path

from jobpilot.db.repo import ApplicationRepo
from jobpilot.models import (
    CoverLetter,
    ExperienceEntry,
    JDAnalysis,
    JobPosting,
    PipelineResult,
    ResumeData,
    RoleType,
    TailorResponse,
)
from jobpilot.services.pipeline import generate_cover_letter_for_result, generate_resume_and_track


class FakeLLM:
    def generate_structured(self, prompt, schema_name, output_model):
        if output_model is JDAnalysis:
            return JDAnalysis(
                role_type=RoleType.ai,
                required_skills=["Python"],
                preferred_skills=[],
                match_score=88,
                missing_skills=[],
            )
        if output_model is TailorResponse:
            return TailorResponse(
                summary="Tailored summary",
                skills=["Python"],
                experiences=[
                    ExperienceEntry(company="Acme", title="Engineer", bullets=["Built APIs"])
                ],
            )
        if output_model is CoverLetter:
            return CoverLetter(
                lines=[
                    "Dear Hiring Team,",
                    "I am excited to apply for this role.",
                    "I build AI and LLM infrastructure systems.",
                    "I have strong platform engineering experience.",
                    "I am open to relocating to the EU.",
                    "Thank you for your consideration.",
                ]
            )
        raise AssertionError("unexpected model")


def test_pipeline_happy_path(tmp_path):
    llm = FakeLLM()
    repo = ApplicationRepo(tmp_path / "db.sqlite", Path("src/jobpilot/db/schema.sql"))

    base_resume = ResumeData(
        full_name="A",
        email="a@example.com",
        summary="base summary",
        skills=["Python"],
        experience=[
            ExperienceEntry(company="Acme", title="Engineer", bullets=["Built APIs"])
        ],
        education=[],
    )
    job = JobPosting(
        source="x",
        company="Acme",
        role="AI Engineer",
        location="Berlin, Germany",
        country="Germany",
        description="Need Python",
        apply_link="https://apply",
    )
    result = PipelineResult(
        job=job,
        analysis=JDAnalysis(
            role_type=RoleType.ai,
            required_skills=["Python"],
            preferred_skills=[],
            match_score=88,
            missing_skills=[],
        ),
    )

    pdf_path, _ = generate_resume_and_track(llm, repo, tmp_path, base_resume, result)
    assert pdf_path.exists()

    cover_letter = generate_cover_letter_for_result(llm, result, base_resume, tmp_path)
    assert len(cover_letter.lines) >= 6

    rows = repo.list_applications(country="Germany", stage="All")
    assert len(rows) == 1
