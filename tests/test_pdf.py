from datetime import date

from jobpilot.models import ExperienceEntry, TailoredResume, TargetMeta
from jobpilot.pdf.generator import generate_pdf


def test_pdf_generation_creates_file(tmp_path):
    resume = TailoredResume(
        full_name="A",
        email="a@example.com",
        summary="summary",
        skills=["Python"],
        experience=[
            ExperienceEntry(company="Acme", title="Engineer", bullets=["Did work"])
        ],
        education=[],
        target_company="Acme",
        target_role="Engineer",
    )
    artifact = generate_pdf(
        resume=resume,
        target=TargetMeta(company="Acme", role="Engineer", date=date.today().isoformat()),
        output_dir=tmp_path,
    )
    assert artifact.path.exists()
