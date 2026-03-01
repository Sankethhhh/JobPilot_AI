from __future__ import annotations

import httpx

from jobpilot.models import JobPosting
from jobpilot.scrapers.base import BaseScraper


class RemotiveScraper(BaseScraper):
    source_name = "remotive"

    def __init__(self, timeout_seconds: int = 15):
        self.timeout_seconds = timeout_seconds

    def fetch_jobs(self) -> list[JobPosting]:
        jobs: list[JobPosting] = []
        url = "https://remotive.com/api/remote-jobs"

        with httpx.Client(timeout=self.timeout_seconds) as client:
            try:
                resp = client.get(url)
                resp.raise_for_status()
                payload = resp.json()
            except Exception:
                return jobs

            for item in payload.get("jobs", []):
                location = item.get("candidate_required_location", "")
                jobs.append(
                    JobPosting(
                        source=self.source_name,
                        company=item.get("company_name", "Unknown Company"),
                        role=item.get("title", "Unknown Role"),
                        location=location,
                        country=location,
                        description=item.get("description", ""),
                        apply_link=item.get("url", ""),
                    )
                )

        return jobs
