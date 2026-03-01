from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

from jobpilot.db.repo import ApplicationRepo
from jobpilot.llm.client import LLMClient
from jobpilot.llm.prompts import build_analysis_prompt
from jobpilot.models import (
    JDAnalysis,
    JobPosting,
    PipelineResult,
    ResumeData,
)
from jobpilot.resume.loader import to_candidate_profile
from jobpilot.services.graphs import (
    build_analysis_graph,
    build_cover_letter_graph,
    build_resume_generation_graph,
)

logger = logging.getLogger("jobpilot.pipeline")


def analyze_job(llm_client: LLMClient, job: JobPosting, base_resume: ResumeData) -> JDAnalysis:
    prompt = build_analysis_prompt(job=job, profile=to_candidate_profile(base_resume))
    return llm_client.generate_structured(prompt=prompt, schema_name="jd_analysis", output_model=JDAnalysis)


def analyze_jobs(
    llm_client: LLMClient,
    jobs: list[JobPosting],
    base_resume: ResumeData,
    progress_callback: Callable[[str], None] | None = None,
) -> list[PipelineResult]:
    graph = build_analysis_graph()
    results: list[PipelineResult] = []
    total = len(jobs)
    logger.info("Analysis batch started: total_jobs=%s", total)
    for idx, job in enumerate(jobs, start=1):
        job_tag = f"{job.company} | {job.role}"
        logger.info("Analysis started: index=%s/%s job=%s", idx, total, job_tag)
        if progress_callback:
            progress_callback(f"[{idx}/{total}] Analyzing {job_tag}")
        try:
            state = graph.invoke(
                {
                    "llm_client": llm_client,
                    "analyze_fn": analyze_job,
                    "job": job,
                    "base_resume": base_resume,
                    "progress_callback": progress_callback,
                }
            )
            analysis = state["analysis"]
            results.append(PipelineResult(job=job, analysis=analysis))
            logger.info(
                "Analysis completed: index=%s/%s job=%s match_score=%s",
                idx,
                total,
                job_tag,
                analysis.match_score,
            )
            if progress_callback:
                progress_callback(f"[{idx}/{total}] Completed {job_tag} -> score {analysis.match_score}")
        except Exception as exc:
            results.append(PipelineResult(job=job, analysis_failed=True, error=str(exc)))
            logger.exception("Analysis failed: index=%s/%s job=%s", idx, total, job_tag)
            if progress_callback:
                progress_callback(f"[{idx}/{total}] Failed {job_tag}: {exc}")
    logger.info("Analysis batch completed: successful=%s failed=%s", len([r for r in results if r.analysis]), len([r for r in results if r.analysis_failed]))
    return results


def generate_resume_and_track(
    llm_client: LLMClient,
    repo: ApplicationRepo,
    output_dir: Path,
    base_resume: ResumeData,
    result: PipelineResult,
    progress_callback: Callable[[str], None] | None = None,
) -> tuple[Path, str]:
    job_tag = f"{result.job.company} | {result.job.role}"
    logger.info("Resume generation flow started: job=%s", job_tag)
    if progress_callback:
        progress_callback("Validating analysis state")
    graph = build_resume_generation_graph()
    state = graph.invoke(
        {
            "llm_client": llm_client,
            "repo": repo,
            "output_dir": output_dir,
            "base_resume": base_resume,
            "result": result,
            "progress_callback": progress_callback,
        }
    )
    logger.info("Resume generation flow completed: job=%s pdf_path=%s", job_tag, state["pdf_path"])
    if progress_callback:
        progress_callback("Resume PDF generated and tracker updated")
    return state["pdf_path"], state["tracker_message"]


def generate_cover_letter_for_result(
    llm_client: LLMClient,
    result: PipelineResult,
    base_resume: ResumeData,
    output_dir: Path,
    progress_callback: Callable[[str], None] | None = None,
):
    job_tag = f"{result.job.company} | {result.job.role}"
    logger.info("Cover letter flow started: job=%s", job_tag)
    if progress_callback:
        progress_callback("Validating analysis state")
    graph = build_cover_letter_graph()
    state = graph.invoke(
        {
            "llm_client": llm_client,
            "output_dir": output_dir,
            "base_resume": base_resume,
            "result": result,
            "progress_callback": progress_callback,
        }
    )
    logger.info("Cover letter flow completed: job=%s", job_tag)
    if progress_callback:
        progress_callback("Cover letter generated and saved")
    return state["cover_letter"]
