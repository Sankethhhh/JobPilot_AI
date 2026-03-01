from __future__ import annotations

from datetime import datetime
from enum import Enum
from pathlib import Path
from pydantic import AliasChoices, BaseModel, Field, field_validator, model_validator


class RoleType(str, Enum):
    ai = "AI"
    platform = "Platform"
    backend = "Backend"


class JobPosting(BaseModel):
    source: str
    company: str
    role: str
    location: str
    country: str
    description: str
    apply_link: str


class JDAnalysis(BaseModel):
    role_type: RoleType
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    match_score: int = Field(ge=0, le=100)
    missing_skills: list[str] = Field(default_factory=list)


class ExperienceEntry(BaseModel):
    company: str
    title: str
    location: str = ""
    period: str = ""
    bullets: list[str] = Field(min_length=1)


class EducationEntry(BaseModel):
    degree: str
    institution: str
    year: str = ""


class ResumeData(BaseModel):
    full_name: str
    email: str
    phone: str = ""
    location: str = ""
    summary: str
    skills: list[str] = Field(default_factory=list)
    experience: list[ExperienceEntry] = Field(min_length=1)
    education: list[EducationEntry] = Field(default_factory=list)


class TailoredResume(ResumeData):
    target_company: str
    target_role: str


class CoverLetter(BaseModel):
    lines: list[str] = Field(min_length=6, max_length=8)

    @field_validator("lines")
    @classmethod
    def non_empty_lines(cls, value: list[str]) -> list[str]:
        if any(not line.strip() for line in value):
            raise ValueError("Cover letter lines must be non-empty")
        return value


class ApplicationStage(str, Enum):
    applied = "Applied"
    interview = "Interview"
    rejected = "Rejected"
    offer = "Offer"


class ApplicationRecord(BaseModel):
    id: int | None = None
    company: str
    role: str
    country: str
    match_score: int = Field(ge=0, le=100)
    resume_path: str
    cover_letter_text: str = ""
    applied: bool = False
    stage: ApplicationStage = ApplicationStage.applied
    notes: str = ""
    status_reason: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PdfArtifact(BaseModel):
    path: Path
    generated_at: datetime


class TargetMeta(BaseModel):
    company: str
    role: str
    date: str


class PipelineResult(BaseModel):
    job: JobPosting
    analysis: JDAnalysis | None = None
    analysis_failed: bool = False
    error: str = ""


class CandidateProfile(BaseModel):
    summary: str
    skills: list[str] = Field(default_factory=list)


class TailorResponse(BaseModel):
    summary: str
    experiences: list[ExperienceEntry] = Field(validation_alias=AliasChoices("experiences", "experience"))
    skills: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def ensure_experiences(self) -> "TailorResponse":
        if not self.experiences:
            raise ValueError("Tailored response must include experiences")
        return self
