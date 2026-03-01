from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Callable, TypedDict
import logging

from langgraph.graph import END, StateGraph

from jobpilot.cover_letter.generator import generate_cover_letter
from jobpilot.db.repo import ApplicationRepo
from jobpilot.llm.client import LLMClient
from jobpilot.models import (
    ApplicationRecord,
    CoverLetter,
    JDAnalysis,
    JobPosting,
    PipelineResult,
    ResumeData,
    TailoredResume,
    TargetMeta,
)
from jobpilot.pdf.generator import generate_pdf
from jobpilot.resume.tailor import tailor_resume

logger = logging.getLogger("jobpilot.graphs")


class AnalysisState(TypedDict, total=False):
    llm_client: LLMClient
    analyze_fn: Callable[..., JDAnalysis]
    progress_callback: Callable[[str], None]
    job: JobPosting
    base_resume: ResumeData
    analysis: JDAnalysis
    error: str


class ResumeGenerationState(TypedDict, total=False):
    llm_client: LLMClient
    progress_callback: Callable[[str], None]
    repo: ApplicationRepo
    output_dir: Path
    base_resume: ResumeData
    result: PipelineResult
    tailored_resume: TailoredResume
    pdf_path: Path
    tracker_message: str


class CoverLetterState(TypedDict, total=False):
    llm_client: LLMClient
    progress_callback: Callable[[str], None]
    output_dir: Path
    base_resume: ResumeData
    result: PipelineResult
    tailored_resume: TailoredResume
    cover_letter: CoverLetter


def build_analysis_graph():
    graph = StateGraph(AnalysisState)

    def analyze_node(state: AnalysisState) -> AnalysisState:
        cb = state.get("progress_callback")
        if cb:
            cb("LangGraph node: analyze")
        analyze_fn = state["analyze_fn"]
        analysis = analyze_fn(
            llm_client=state["llm_client"],
            job=state["job"],
            base_resume=state["base_resume"],
        )
        logger.info("Graph node complete: analyze")
        return {"analysis": analysis}

    graph.add_node("analyze", analyze_node)
    graph.set_entry_point("analyze")
    graph.add_edge("analyze", END)
    return graph.compile()


def build_resume_generation_graph():
    graph = StateGraph(ResumeGenerationState)

    def validate_node(state: ResumeGenerationState) -> ResumeGenerationState:
        cb = state.get("progress_callback")
        if cb:
            cb("LangGraph node: validate")
        if state["result"].analysis is None:
            raise ValueError("Analyze the job before generating resume")
        logger.info("Graph node complete: validate_resume")
        return {}

    def tailor_node(state: ResumeGenerationState) -> ResumeGenerationState:
        cb = state.get("progress_callback")
        if cb:
            cb("LangGraph node: tailor_resume")
        result = state["result"]
        tailored = tailor_resume(
            llm_client=state["llm_client"],
            base_resume=state["base_resume"],
            job=result.job,
            analysis=result.analysis,
        )
        logger.info("Graph node complete: tailor_resume")
        return {"tailored_resume": tailored}

    def pdf_node(state: ResumeGenerationState) -> ResumeGenerationState:
        cb = state.get("progress_callback")
        if cb:
            cb("LangGraph node: render_pdf")
        result = state["result"]
        artifact = generate_pdf(
            resume=state["tailored_resume"],
            target=TargetMeta(company=result.job.company, role=result.job.role, date=date.today().isoformat()),
            output_dir=state["output_dir"],
        )
        logger.info("Graph node complete: render_pdf path=%s", artifact.path)
        return {"pdf_path": artifact.path}

    def track_node(state: ResumeGenerationState) -> ResumeGenerationState:
        cb = state.get("progress_callback")
        if cb:
            cb("LangGraph node: track_application")
        result = state["result"]
        analysis = result.analysis
        record_id = state["repo"].add_or_update(
            ApplicationRecord(
                company=result.job.company,
                role=result.job.role,
                country=result.job.country,
                match_score=analysis.match_score,
                resume_path=str(state["pdf_path"]),
                status_reason=result.error,
            )
        )
        logger.info("Graph node complete: track_application record_id=%s", record_id)
        return {"tracker_message": f"Tracked with record ID {record_id}"}

    graph.add_node("validate", validate_node)
    graph.add_node("tailor", tailor_node)
    graph.add_node("render_pdf", pdf_node)
    graph.add_node("track", track_node)

    graph.set_entry_point("validate")
    graph.add_edge("validate", "tailor")
    graph.add_edge("tailor", "render_pdf")
    graph.add_edge("render_pdf", "track")
    graph.add_edge("track", END)
    return graph.compile()


def build_cover_letter_graph():
    graph = StateGraph(CoverLetterState)

    def validate_node(state: CoverLetterState) -> CoverLetterState:
        cb = state.get("progress_callback")
        if cb:
            cb("LangGraph node: validate")
        if state["result"].analysis is None:
            raise ValueError("Analyze the job before generating cover letter")
        logger.info("Graph node complete: validate_cover_letter")
        return {}

    def tailor_node(state: CoverLetterState) -> CoverLetterState:
        cb = state.get("progress_callback")
        if cb:
            cb("LangGraph node: tailor_resume")
        result = state["result"]
        tailored = tailor_resume(
            llm_client=state["llm_client"],
            base_resume=state["base_resume"],
            job=result.job,
            analysis=result.analysis,
        )
        logger.info("Graph node complete: tailor_resume_for_cover")
        return {"tailored_resume": tailored}

    def generate_node(state: CoverLetterState) -> CoverLetterState:
        cb = state.get("progress_callback")
        if cb:
            cb("LangGraph node: generate_cover_letter")
        result = state["result"]
        cover_letter = generate_cover_letter(
            llm_client=state["llm_client"],
            job=result.job,
            resume=state["tailored_resume"],
            output_dir=state["output_dir"],
        )
        logger.info("Graph node complete: generate_cover_letter")
        return {"cover_letter": cover_letter}

    graph.add_node("validate", validate_node)
    graph.add_node("tailor", tailor_node)
    graph.add_node("generate", generate_node)

    graph.set_entry_point("validate")
    graph.add_edge("validate", "tailor")
    graph.add_edge("tailor", "generate")
    graph.add_edge("generate", END)
    return graph.compile()
