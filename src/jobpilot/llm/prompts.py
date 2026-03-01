from __future__ import annotations

import json

from jobpilot.models import CandidateProfile, JDAnalysis, JobPosting, ResumeData


def build_analysis_prompt(job: JobPosting, profile: CandidateProfile) -> str:
    return (
        "Analyze this job description and return strict JSON only. "
        "Classify role_type as one of AI, Platform, Backend. "
        "Compute match_score from 0-100 based on required skill overlap and experience fit. "
        "Do not hallucinate.\n\n"
        f"Candidate summary: {profile.summary}\n"
        f"Candidate skills: {', '.join(profile.skills)}\n\n"
        f"Job title: {job.role}\n"
        f"Company: {job.company}\n"
        f"Job description: {job.description}\n"
    )


def build_tailor_prompt(base_resume: ResumeData, job: JobPosting, analysis: JDAnalysis) -> str:
    return (
        "Tailor the resume while preserving factual integrity. Return strict JSON only. "
        "The JSON must contain EXACTLY these top-level keys: "
        "\"summary\", \"skills\", \"experiences\". "
        "Do not wrap output in keys like input_json/output/result/data. "
        "Rules: keep same experience entries, reorder bullets by relevance, "
        "adjust summary slightly, do not create new achievements or tools.\n\n"
        f"Target role: {job.role} at {job.company}\n"
        f"Analysis: role_type={analysis.role_type.value}, match={analysis.match_score}, "
        f"required_skills={analysis.required_skills}, missing_skills={analysis.missing_skills}\n\n"
        f"Base resume JSON:\n{base_resume.model_dump_json(indent=2)}"
    )


def build_cover_letter_prompt(job: JobPosting, resume_summary: str, key_skills: list[str]) -> str:
    return (
        "Generate a concise professional cover letter in 6-8 lines. Return strict JSON only with field lines. "
        "Include relocation willingness to EU and highlight AI/LLM infrastructure strengths. "
        "Avoid copying resume bullets verbatim.\n\n"
        f"Job: {job.role} at {job.company} in {job.location}\n"
        f"Description: {job.description}\n"
        f"Resume summary: {resume_summary}\n"
        f"Key skills: {', '.join(key_skills)}"
    )


def build_resume_structuring_prompt(
    resume_text: str,
    template: dict,
    extra_details: str = "",
) -> str:
    template_json = json.dumps(template, indent=2)
    return (
        "Convert the uploaded resume information into strict JSON matching the template schema. "
        "Return JSON only. Do not include markdown or extra keys. "
        "If a field is unknown, use an empty string or empty list. "
        "Do not hallucinate achievements.\n\n"
        f"Target template:\n{template_json}\n\n"
        f"Extra user details:\n{extra_details}\n\n"
        f"Uploaded resume content:\n{resume_text}\n"
    )
