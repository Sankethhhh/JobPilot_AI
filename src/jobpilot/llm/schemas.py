from __future__ import annotations

from jobpilot.models import CoverLetter, JDAnalysis, TailorResponse


ANALYSIS_SCHEMA = JDAnalysis.model_json_schema()
TAILOR_SCHEMA = TailorResponse.model_json_schema()
COVER_LETTER_SCHEMA = CoverLetter.model_json_schema()
