import pytest

from jobpilot.models import ExperienceEntry, ResumeData, TailorResponse
from jobpilot.resume.tailor import HallucinationError, _validate_no_fabrication


def _base_resume() -> ResumeData:
    return ResumeData(
        full_name="A",
        email="a@example.com",
        summary="summary",
        skills=["Python"],
        experience=[
            ExperienceEntry(
                company="Acme",
                title="Engineer",
                bullets=["Built APIs", "Improved reliability"],
            )
        ],
        education=[],
    )


def test_tailor_rejects_fabricated_bullet():
    base = _base_resume()
    tailored = TailorResponse(
        summary="summary",
        skills=["Python"],
        experiences=[
            ExperienceEntry(
                company="Acme",
                title="Engineer",
                bullets=["Built APIs", "Invented brand new framework"],
            )
        ],
    )

    with pytest.raises(HallucinationError):
        _validate_no_fabrication(base, tailored)
