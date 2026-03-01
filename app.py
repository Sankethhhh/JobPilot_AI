from __future__ import annotations

from datetime import datetime
import io
import json
import logging
from pathlib import Path

import streamlit as st

from jobpilot.config import settings
from jobpilot.db.repo import ApplicationRepo
from jobpilot.llm.client import LLMClient
from jobpilot.llm.prompts import build_resume_structuring_prompt
from jobpilot.models import ApplicationStage, JobPosting, PipelineResult, ResumeData
from jobpilot.resume.loader import load_resume
from jobpilot.scrapers.arbeitnow import ArbeitnowScraper
from jobpilot.scrapers.greenhouse import GreenhouseScraper
from jobpilot.scrapers.lever import LeverScraper
from jobpilot.scrapers.orchestrator import discover_jobs
from jobpilot.scrapers.remotive import RemotiveScraper
from jobpilot.scrapers.workable import WorkableScraper
from jobpilot.services.pipeline import (
    analyze_jobs,
    generate_cover_letter_for_result,
    generate_resume_and_track,
)

logger = logging.getLogger("jobpilot")

try:
    from pypdf import PdfReader
except Exception:  # pragma: no cover
    PdfReader = None


def _configure_logging() -> None:
    settings.log_path.parent.mkdir(parents=True, exist_ok=True)
    if logger.handlers:
        return
    logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler = logging.FileHandler(settings.log_path)
    file_handler.setFormatter(formatter)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)


def _inject_styles() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&family=IBM+Plex+Serif:wght@500;600&display=swap');

        :root {
            --bg-soft: #f7f5ef;
            --bg-shell: #fffdf8;
            --ink: #1f2937;
            --ink-muted: #5f6b7a;
            --line: #d8d9d1;
            --brand-a: #0f766e;
            --brand-b: #c2410c;
            --ok: #166534;
            --err: #b91c1c;
        }

        html, body, [data-testid="stAppViewContainer"] {
            background:
              radial-gradient(1200px 420px at 8% -8%, rgba(15,118,110,0.18), transparent 60%),
              radial-gradient(900px 360px at 95% 2%, rgba(194,65,12,0.14), transparent 62%),
              var(--bg-soft);
        }

        [data-testid="stHeader"] {
            background: transparent;
        }

        .block-container {
            max-width: 1180px;
            padding-top: 1.1rem;
            padding-bottom: 2.2rem;
        }

        h1, h2, h3, h4 {
            font-family: 'IBM Plex Serif', serif !important;
            color: var(--ink);
            letter-spacing: -0.02em;
        }

        p, li, label, div {
            font-family: 'Space Grotesk', sans-serif;
            color: var(--ink);
        }

        .jp-hero {
            background: linear-gradient(135deg, rgba(15,118,110,0.09), rgba(194,65,12,0.08));
            border: 1px solid rgba(31, 41, 55, 0.10);
            border-radius: 18px;
            padding: 1.2rem 1.2rem 1rem 1.2rem;
            margin-bottom: 1rem;
            animation: rise 340ms ease-out;
        }

        .jp-subtitle {
            color: var(--ink-muted);
            font-size: 0.97rem;
            margin-top: 0.35rem;
        }

        .jp-chip-row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
            margin-top: 0.8rem;
        }

        .jp-chip {
            border: 1px solid rgba(31, 41, 55, 0.16);
            background: rgba(255, 255, 255, 0.72);
            padding: 0.2rem 0.58rem;
            border-radius: 999px;
            font-size: 0.76rem;
            color: #234;
        }

        .jp-panel {
            background: var(--bg-shell);
            border: 1px solid var(--line);
            border-radius: 14px;
            padding: 0.95rem;
            margin-bottom: 0.85rem;
            animation: rise 360ms ease-out;
        }

        .jp-kpi {
            background: white;
            border: 1px solid var(--line);
            border-radius: 14px;
            padding: 0.8rem;
            height: 100%;
        }

        .jp-kpi .label {
            font-size: 0.78rem;
            color: var(--ink-muted);
        }

        .jp-kpi .value {
            font-size: 1.35rem;
            font-weight: 700;
            color: var(--ink);
            line-height: 1.2;
        }

        .stButton > button {
            border-radius: 12px;
            border: 1px solid rgba(31, 41, 55, 0.20);
            background: linear-gradient(90deg, #0f766e 0%, #0d9488 60%, #14b8a6 100%);
            color: #f8fafc;
            font-family: 'Space Grotesk', sans-serif;
            font-weight: 600;
            transition: transform .15s ease, filter .15s ease;
        }

        .stButton > button:hover {
            transform: translateY(-1px);
            filter: brightness(1.05);
        }

        .stTabs [data-baseweb="tab-list"] {
            gap: 0.5rem;
            margin-bottom: 0.9rem;
        }

        .stTabs [data-baseweb="tab"] {
            border: 1px solid var(--line);
            border-radius: 12px;
            padding: 0.35rem 0.75rem;
            background: rgba(255,255,255,0.8);
            font-family: 'Space Grotesk', sans-serif;
            font-weight: 600;
        }

        @keyframes rise {
            from { opacity: 0; transform: translateY(8px); }
            to { opacity: 1; transform: translateY(0); }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _default_scrapers():
    greenhouse_tokens = ["openai", "datadog", "stripe"]
    lever_companies = ["netlify", "sourcegraph", "samsara"]
    workable_subdomains = ["personio", "smallpdf"]
    return [
        GreenhouseScraper(greenhouse_tokens, timeout_seconds=settings.scraper_timeout_seconds),
        LeverScraper(lever_companies, timeout_seconds=settings.scraper_timeout_seconds),
        WorkableScraper(workable_subdomains, timeout_seconds=settings.scraper_timeout_seconds),
        ArbeitnowScraper(timeout_seconds=settings.scraper_timeout_seconds, max_pages=2),
        RemotiveScraper(timeout_seconds=settings.scraper_timeout_seconds),
    ]


def _get_repo() -> ApplicationRepo:
    schema_path = Path("src/jobpilot/db/schema.sql")
    return ApplicationRepo(settings.db_path, schema_path)


def _init_state() -> None:
    st.session_state.setdefault("jobs", [])
    st.session_state.setdefault("results", [])
    st.session_state.setdefault("selected_jobs_for_analysis", [])
    st.session_state.setdefault("selected_job_labels", [])
    st.session_state.setdefault("last_pdf", None)
    st.session_state.setdefault("last_cover_letter", None)
    st.session_state.setdefault("backend_events", [])


def _result_label(item: PipelineResult | JobPosting) -> str:
    job = item.job if isinstance(item, PipelineResult) else item
    return f"{job.company} | {job.role} | {job.country}"


def _push_backend_event(message: str) -> None:
    timestamp = datetime.now().strftime("%H:%M:%S")
    event_line = f"{timestamp} | {message}"
    events: list[str] = st.session_state.get("backend_events", [])
    events.append(event_line)
    st.session_state["backend_events"] = events[-80:]
    logger.info("UI backend event: %s", message)


def _render_backend_activity() -> None:
    st.markdown("<div class='jp-panel'>", unsafe_allow_html=True)
    st.subheader("Backend Activity")
    events: list[str] = st.session_state.get("backend_events", [])
    if not events:
        st.caption("No backend activity yet.")
    else:
        with st.expander("Live execution log", expanded=True):
            st.code("\n".join(events[-25:]), language="text")
    st.markdown("</div>", unsafe_allow_html=True)


def _resume_template() -> dict:
    return {
        "full_name": "",
        "email": "",
        "phone": "",
        "location": "",
        "summary": "",
        "skills": [],
        "experience": [
            {
                "company": "",
                "title": "",
                "location": "",
                "period": "",
                "bullets": [],
            }
        ],
        "education": [
            {
                "degree": "",
                "institution": "",
                "year": "",
            }
        ],
    }


def _extract_uploaded_resume_text(uploaded_file) -> str:
    filename = uploaded_file.name.lower()
    raw = uploaded_file.getvalue()
    if filename.endswith(".pdf"):
        if PdfReader is None:
            raise ValueError("PDF parsing requires pypdf. Run `uv sync` and retry.")
        reader = PdfReader(io.BytesIO(raw))
        parts: list[str] = []
        for page in reader.pages:
            parts.append(page.extract_text() or "")
        return "\n".join(parts).strip()
    return raw.decode("utf-8", errors="ignore").strip()


def _resume_onboarding(llm_client: LLMClient) -> ResumeData | None:
    st.markdown("<div class='jp-panel'>", unsafe_allow_html=True)
    st.subheader("Resume Setup Required")
    st.warning(f"`{settings.resume_path}` was not found. Upload your resume to generate canonical resume.json.")

    with st.expander("resume.json template", expanded=False):
        st.code(json.dumps(_resume_template(), indent=2), language="json")

    uploaded = st.file_uploader(
        "Upload resume",
        type=["pdf", "txt", "md", "json"],
        help="PDF/TXT/MD/JSON supported. JSON can be directly validated as resume.json.",
    )
    extra_details = st.text_area(
        "Additional details for structuring",
        placeholder="Add missing details like phone, location, exact role titles, etc.",
        height=120,
    )

    if uploaded is None:
        st.info("Upload a resume file to continue.")
        st.markdown("</div>", unsafe_allow_html=True)
        return None

    if uploaded.name.lower().endswith(".json"):
        if st.button("Validate and Save Uploaded JSON", width="stretch"):
            try:
                parsed = json.loads(uploaded.getvalue().decode("utf-8", errors="ignore"))
                resume = ResumeData.model_validate(parsed)
                settings.resume_path.parent.mkdir(parents=True, exist_ok=True)
                settings.resume_path.write_text(resume.model_dump_json(indent=2))
                st.success(f"Saved validated resume.json to {settings.resume_path}")
                st.rerun()
            except Exception as exc:
                st.error(f"Invalid resume JSON: {exc}")
        st.markdown("</div>", unsafe_allow_html=True)
        return None

    if st.button("Generate resume.json from uploaded resume", width="stretch"):
        try:
            with st.status("Structuring resume into canonical JSON...", expanded=True) as status:
                status.write("Extracting text from uploaded file")
                resume_text = _extract_uploaded_resume_text(uploaded)
                if not resume_text:
                    raise ValueError("Could not extract resume text from uploaded file.")
                status.write("Calling LLM to generate structured resume.json")
                prompt = build_resume_structuring_prompt(
                    resume_text=resume_text,
                    template=_resume_template(),
                    extra_details=extra_details,
                )
                structured = llm_client.generate_structured(
                    prompt=prompt,
                    schema_name="resume_data",
                    output_model=ResumeData,
                )
                settings.resume_path.parent.mkdir(parents=True, exist_ok=True)
                settings.resume_path.write_text(structured.model_dump_json(indent=2))
                status.write("Saved canonical resume.json")
                status.update(label="Resume setup complete", state="complete")
            st.success(f"Generated and saved {settings.resume_path}")
            st.rerun()
        except Exception as exc:
            st.error(f"Failed to generate resume.json: {exc}")

    st.markdown("</div>", unsafe_allow_html=True)
    return None


def _render_hero() -> None:
    st.markdown(
        f"""
        <div class="jp-hero">
            <h1 style="margin:0;">JobPilot AI</h1>
            <div class="jp-subtitle">Precision-first job search, resume tailoring, and application tracking for AI roles in EU markets.</div>
            <div class="jp-chip-row">
              <span class="jp-chip">Greenhouse</span>
              <span class="jp-chip">Lever</span>
              <span class="jp-chip">Workable</span>
              <span class="jp-chip">Arbeitnow</span>
              <span class="jp-chip">Remotive</span>
              <span class="jp-chip">Logs: {settings.log_path.resolve()}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_kpi(jobs_count: int, results: list[PipelineResult]) -> None:
    analyzed = len(results)
    success = len([r for r in results if r.analysis and not r.analysis_failed])
    failed = len([r for r in results if r.analysis_failed])

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(
            f"<div class='jp-kpi'><div class='label'>Jobs Found</div><div class='value'>{jobs_count}</div></div>",
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f"<div class='jp-kpi'><div class='label'>Analyzed</div><div class='value'>{analyzed}</div></div>",
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            f"<div class='jp-kpi'><div class='label'>Ready For Resume</div><div class='value'>{success}</div></div>",
            unsafe_allow_html=True,
        )
    with c4:
        st.markdown(
            f"<div class='jp-kpi'><div class='label'>Analysis Failed</div><div class='value'>{failed}</div></div>",
            unsafe_allow_html=True,
        )


def main() -> None:
    _configure_logging()
    st.set_page_config(page_title="JobPilot AI", layout="wide")
    _inject_styles()

    _init_state()

    llm_client = LLMClient(settings)
    repo = _get_repo()
    settings.output_dir.mkdir(parents=True, exist_ok=True)

    if not settings.resume_path.exists():
        base_resume = _resume_onboarding(llm_client)
        if base_resume is None:
            return
    else:
        try:
            base_resume = load_resume(settings.resume_path)
        except Exception as exc:
            st.error(f"Failed to load resume at {settings.resume_path}: {exc}")
            return

    _render_hero()
    _render_kpi(len(st.session_state["jobs"]), st.session_state["results"])

    tab_search, tab_resume, tab_tracker = st.tabs(["Job Search", "Resume Preview", "Application Tracker"])

    with tab_search:
        left, right = st.columns([1.05, 1.95], gap="large")

        with left:
            st.markdown("<div class='jp-panel'>", unsafe_allow_html=True)
            st.subheader("Search Controls")
            country = st.selectbox("Target Country", options=list(settings.supported_countries))
            keywords = st.text_input("Keywords", value="LLM, AI Platform, MLOps")
            st.caption("Tip: add role families and tool keywords separated by commas.")
            if st.button("Search Jobs", width="stretch", key="search_jobs_btn"):
                logger.info("Search requested: country=%s keywords=%s", country, keywords)
                _push_backend_event(f"Search requested for {country} with keywords: {keywords}")
                with st.status("Searching job sources...", expanded=True) as status:
                    status.write("Preparing source connectors")
                    _push_backend_event("Initializing scraper connectors")
                    jobs = discover_jobs(
                        country=country,
                        keywords=[k.strip() for k in keywords.split(",")],
                        scrapers=_default_scrapers(),
                    )
                    status.write(f"Filtered and deduplicated results: {len(jobs)} jobs")
                    _push_backend_event(f"Search completed with {len(jobs)} jobs after filters")
                    status.update(label="Search complete", state="complete")
                logger.info("Search completed: discovered=%s", len(jobs))
                st.session_state["jobs"] = jobs
                st.session_state["results"] = []
                st.session_state["selected_jobs_for_analysis"] = []
                st.session_state["selected_job_labels"] = []
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

            st.markdown("<div class='jp-panel'>", unsafe_allow_html=True)
            st.subheader("Analysis")
            jobs = st.session_state["jobs"]
            selected_jobs = st.session_state.get("selected_jobs_for_analysis", [])
            analyze_disabled = not selected_jobs
            if st.button("Analyze Discovered Jobs", disabled=analyze_disabled, width="stretch", key="analyze_btn"):
                logger.info("Analyze requested for %s selected jobs", len(selected_jobs))
                _push_backend_event(f"Analysis batch started for {len(selected_jobs)} selected jobs")
                with st.status("Analyzing job descriptions...", expanded=True) as status:
                    status.write(f"Running LLM analysis for {len(selected_jobs)} jobs")
                    analysis_progress = st.progress(0.0, text=f"Analysis progress: 0/{len(selected_jobs)}")
                    done_count = {"count": 0}

                    def _analysis_progress(message: str) -> None:
                        status.write(message)
                        _push_backend_event(message)
                        if "Completed" in message or "Failed" in message:
                            done_count["count"] += 1
                            ratio = done_count["count"] / max(1, len(selected_jobs))
                            analysis_progress.progress(
                                ratio,
                                text=f"Analysis progress: {done_count['count']}/{len(selected_jobs)}",
                            )

                    analyzed_results = analyze_jobs(
                        llm_client=llm_client,
                        jobs=selected_jobs,
                        base_resume=base_resume,
                        progress_callback=_analysis_progress,
                    )
                    success_count = len([r for r in analyzed_results if r.analysis and not r.analysis_failed])
                    failed_count = len([r for r in analyzed_results if r.analysis_failed])
                    status.write(f"Valid analyses: {success_count}")
                    status.write(f"Failed analyses: {failed_count}")
                    analysis_progress.progress(
                        1.0,
                        text=f"Analysis progress: {len(selected_jobs)}/{len(selected_jobs)}",
                    )
                    _push_backend_event(
                        f"Analysis batch complete: success={success_count}, failed={failed_count}"
                    )
                    status.update(label="Analysis complete", state="complete")
                st.session_state["results"] = analyzed_results
                logger.info("Analyze completed")
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

        with right:
            jobs = st.session_state["jobs"]
            st.markdown("<div class='jp-panel'>", unsafe_allow_html=True)
            st.subheader("Discovered Jobs")
            if jobs:
                st.dataframe(
                    [
                        {
                            "Source": j.source,
                            "Company": j.company,
                            "Role": j.role,
                            "Location": j.location,
                            "Apply Link": j.apply_link,
                        }
                        for j in jobs
                    ],
                    width="stretch",
                    hide_index=True,
                )
                job_options = [_result_label(j) for j in jobs]
                existing_labels = [label for label in st.session_state.get("selected_job_labels", []) if label in job_options]
                if not existing_labels:
                    existing_labels = job_options[: min(10, len(job_options))]
                selected_labels = st.multiselect(
                    "Select jobs for analysis",
                    options=job_options,
                    default=existing_labels,
                    key="selected_job_labels",
                    help="Only selected jobs will be analyzed.",
                )
                selected_jobs = [j for j in jobs if _result_label(j) in selected_labels]
                st.caption(f"Selected for analysis: {len(selected_jobs)}")
                st.session_state["selected_jobs_for_analysis"] = selected_jobs
            else:
                st.info("No jobs discovered yet. Start with Search Jobs.")
                st.session_state["selected_jobs_for_analysis"] = []
            st.markdown("</div>", unsafe_allow_html=True)
            _render_backend_activity()

            results = st.session_state["results"]
            if results:
                st.markdown("<div class='jp-panel'>", unsafe_allow_html=True)
                st.subheader("Match Analysis")
                st.dataframe(
                    [
                        {
                            "Company": r.job.company,
                            "Role": r.job.role,
                            "Country": r.job.country,
                            "Match Score": r.analysis.match_score if r.analysis else None,
                            "Status": "Failed" if r.analysis_failed else "Ready",
                            "Error": r.error,
                        }
                        for r in results
                    ],
                    width="stretch",
                    hide_index=True,
                )

                valid_results = [r for r in results if r.analysis and not r.analysis_failed]
                selected_label = st.selectbox(
                    "Choose an analyzed job for document generation",
                    options=[_result_label(r) for r in valid_results],
                    index=None,
                    placeholder="Select a job",
                    disabled=not valid_results,
                )
                chosen = next((r for r in valid_results if _result_label(r) == selected_label), None)

                b1, b2 = st.columns(2)
                with b1:
                    if st.button(
                        "Generate Tailored Resume PDF",
                        disabled=chosen is None,
                        width="stretch",
                        key="gen_resume_btn",
                    ):
                        try:
                            logger.info("Generate resume requested for %s", _result_label(chosen))
                            _push_backend_event(f"Resume generation started for {_result_label(chosen)}")
                            with st.status("Generating tailored resume...", expanded=True) as status:
                                resume_progress = st.progress(0.0, text="Resume flow: initializing")

                                def _resume_progress(message: str) -> None:
                                    status.write(message)
                                    _push_backend_event(message)
                                    step_map = {
                                        "LangGraph node: validate": (0.2, "Resume flow: validating"),
                                        "LangGraph node: tailor_resume": (0.55, "Resume flow: tailoring"),
                                        "LangGraph node: render_pdf": (0.8, "Resume flow: rendering PDF"),
                                        "LangGraph node: track_application": (0.95, "Resume flow: tracking application"),
                                    }
                                    if message in step_map:
                                        pct, text = step_map[message]
                                        resume_progress.progress(pct, text=text)

                                status.write("Tailoring resume to selected job")
                                path, tracker_msg = generate_resume_and_track(
                                    llm_client=llm_client,
                                    repo=repo,
                                    output_dir=settings.output_dir,
                                    base_resume=base_resume,
                                    result=chosen,
                                    progress_callback=_resume_progress,
                                )
                                status.write("Rendering PDF and tracking application")
                                _push_backend_event(f"Resume generated at {path}")
                                resume_progress.progress(1.0, text="Resume flow: complete")
                                status.update(label="Resume generation complete", state="complete")
                            st.session_state["last_pdf"] = str(path)
                            st.success(f"Resume generated: {path}")
                            st.info(tracker_msg)
                            logger.info("Resume generated at %s", path)
                        except Exception as exc:
                            logger.exception("Resume generation failed")
                            st.error(str(exc))

                with b2:
                    if st.button(
                        "Generate Cover Letter",
                        disabled=chosen is None,
                        width="stretch",
                        key="gen_cover_btn",
                    ):
                        try:
                            logger.info("Generate cover letter requested for %s", _result_label(chosen))
                            _push_backend_event(f"Cover letter generation started for {_result_label(chosen)}")
                            with st.status("Generating cover letter...", expanded=True) as status:
                                cover_progress = st.progress(0.0, text="Cover letter flow: initializing")

                                def _cover_progress(message: str) -> None:
                                    status.write(message)
                                    _push_backend_event(message)
                                    step_map = {
                                        "LangGraph node: validate": (0.25, "Cover letter flow: validating"),
                                        "LangGraph node: tailor_resume": (0.65, "Cover letter flow: tailoring context"),
                                        "LangGraph node: generate_cover_letter": (0.9, "Cover letter flow: generating text"),
                                    }
                                    if message in step_map:
                                        pct, text = step_map[message]
                                        cover_progress.progress(pct, text=text)

                                status.write("Tailoring context for selected job")
                                cl = generate_cover_letter_for_result(
                                    llm_client=llm_client,
                                    result=chosen,
                                    base_resume=base_resume,
                                    output_dir=settings.output_dir,
                                    progress_callback=_cover_progress,
                                )
                                status.write("Saving cover letter artifact")
                                _push_backend_event("Cover letter generated and saved")
                                cover_progress.progress(1.0, text="Cover letter flow: complete")
                                status.update(label="Cover letter generation complete", state="complete")
                            st.session_state["last_cover_letter"] = "\n".join(cl.lines)
                            st.success("Cover letter generated")
                            logger.info("Cover letter generated")
                        except Exception as exc:
                            logger.exception("Cover letter generation failed")
                            st.error(str(exc))
                st.markdown("</div>", unsafe_allow_html=True)

    with tab_resume:
        st.markdown("<div class='jp-panel'>", unsafe_allow_html=True)
        st.subheader("Latest Resume Artifact")
        last_pdf = st.session_state.get("last_pdf")
        if last_pdf and Path(last_pdf).exists():
            with open(last_pdf, "rb") as f:
                st.download_button(
                    "Download Resume PDF",
                    data=f.read(),
                    file_name=Path(last_pdf).name,
                    width="stretch",
                )
            st.caption(f"Stored at: {last_pdf}")
        else:
            st.info("No resume generated yet.")
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div class='jp-panel'>", unsafe_allow_html=True)
        st.subheader("Latest Cover Letter")
        cover_letter = st.session_state.get("last_cover_letter")
        if cover_letter:
            st.text_area("Generated Letter", value=cover_letter, height=260)
        else:
            st.info("No cover letter generated yet.")
        st.markdown("</div>", unsafe_allow_html=True)

    with tab_tracker:
        st.markdown("<div class='jp-panel'>", unsafe_allow_html=True)
        st.subheader("Application Tracker")
        f1, f2 = st.columns(2)
        with f1:
            filter_country = st.selectbox("Country Filter", options=["All", *settings.supported_countries])
        with f2:
            filter_stage = st.selectbox("Stage Filter", options=["All", *[s.value for s in ApplicationStage]])

        records = repo.list_applications(country=filter_country, stage=filter_stage)
        if not records:
            st.info("No application records yet.")
        else:
            st.dataframe([r.model_dump() for r in records], width="stretch", hide_index=True)

            up1, up2, up3 = st.columns([1, 1, 2])
            with up1:
                record_id = st.number_input("Record ID", min_value=1, step=1)
            with up2:
                new_stage = st.selectbox("New Stage", options=[s.value for s in ApplicationStage])
            with up3:
                notes = st.text_input("Notes")
            applied = st.checkbox("Applied")

            if st.button("Save Stage Update", key="save_stage_btn"):
                try:
                    logger.info("Stage update requested: id=%s stage=%s", int(record_id), new_stage)
                    _push_backend_event(f"Updating application record {int(record_id)} to stage {new_stage}")
                    repo.update_stage(
                        record_id=int(record_id),
                        stage=ApplicationStage(new_stage),
                        notes=notes,
                        applied=applied,
                    )
                    st.success("Record updated")
                    logger.info("Stage update completed for id=%s", int(record_id))
                    _push_backend_event(f"Application record {int(record_id)} updated")
                    st.rerun()
                except Exception as exc:
                    logger.exception("Stage update failed")
                    _push_backend_event(f"Stage update failed for record {int(record_id)}: {exc}")
                    st.error(str(exc))
        st.markdown("</div>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
