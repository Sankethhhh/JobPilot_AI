import pytest
from pydantic import ValidationError

from jobpilot.models import JDAnalysis


def test_jd_analysis_rejects_invalid_match_score():
    with pytest.raises(ValidationError):
        JDAnalysis(
            role_type="AI",
            required_skills=["Python"],
            preferred_skills=[],
            match_score=150,
            missing_skills=[],
        )
