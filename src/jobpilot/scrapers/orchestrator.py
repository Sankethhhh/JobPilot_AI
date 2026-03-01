from __future__ import annotations

import logging
import re
from time import sleep

from jobpilot.models import JobPosting
from jobpilot.scrapers.base import BaseScraper

logger = logging.getLogger("jobpilot.discovery")

GERMANY_HINTS = {
    "germany",
    "deutschland",
    "berlin",
    "munich",
    "muenchen",
    "hamburg",
    "frankfurt",
    "cologne",
    "koln",
    "stuttgart",
    "dusseldorf",
    "düsseldorf",
    "bonn",
    "leipzig",
}

NETHERLANDS_HINTS = {
    "netherlands",
    "holland",
    "amsterdam",
    "rotterdam",
    "utrecht",
    "eindhoven",
    "the hague",
    "den haag",
    "delft",
    "groningen",
}

USA_HINTS = {
    "united states",
    "usa",
    "u.s.a.",
    "u.s.",
    "new york",
    "san francisco",
    "seattle",
    "austin",
    "chicago",
    "boston",
}


def _matches_keywords(text: str, keywords: list[str]) -> bool:
    if not keywords:
        return True

    text_l = text.lower()
    for keyword in keywords:
        cleaned = keyword.strip().lower()
        if not cleaned:
            continue
        if cleaned in text_l:
            return True
        tokens = [t for t in re.split(r"[^a-z0-9]+", cleaned) if t]
        if tokens and all(token in text_l for token in tokens):
            return True
    return False


def _normalize_country(location: str) -> str:
    lower = location.lower()
    if any(hint in lower for hint in USA_HINTS) or re.search(r"\bus\b", lower):
        return "United States"
    if any(hint in lower for hint in GERMANY_HINTS) or re.search(r"\bde\b", lower):
        return "Germany"
    if any(hint in lower for hint in NETHERLANDS_HINTS) or re.search(r"\bnl\b", lower):
        return "Netherlands"
    return location


def discover_jobs(country: str, keywords: list[str], scrapers: list[BaseScraper]) -> list[JobPosting]:
    keywords_l = [k.lower().strip() for k in keywords if k.strip()]
    dedupe: dict[tuple[str, str, str], JobPosting] = {}
    total_fetched = 0
    filtered_country = 0
    filtered_keyword = 0

    for scraper in scrapers:
        fetched = scraper.fetch_jobs()
        total_fetched += len(fetched)
        logger.info("Scraper fetched jobs: source=%s count=%s", scraper.source_name, len(fetched))
        sleep(0.15)
        for job in fetched:
            job.country = _normalize_country(job.location)
            if job.country != country:
                filtered_country += 1
                continue

            text = f"{job.role} {job.description}".lower()
            if not _matches_keywords(text, keywords_l):
                filtered_keyword += 1
                continue

            key = (job.company.strip().lower(), job.role.strip().lower(), job.apply_link.strip().lower())
            dedupe[key] = job

    logger.info(
        "Discovery summary: target_country=%s keywords=%s fetched=%s country_filtered=%s keyword_filtered=%s returned=%s",
        country,
        keywords_l,
        total_fetched,
        filtered_country,
        filtered_keyword,
        len(dedupe),
    )
    return list(dedupe.values())
