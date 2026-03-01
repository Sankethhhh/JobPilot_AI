from __future__ import annotations

import httpx

from jobpilot.models import JobPosting
from jobpilot.scrapers.base import BaseScraper


class ArbeitnowScraper(BaseScraper):
    source_name = "arbeitnow"

    def __init__(self, timeout_seconds: int = 15, max_pages: int = 2):
        self.timeout_seconds = timeout_seconds
        self.max_pages = max_pages

    def fetch_jobs(self) -> list[JobPosting]:
        jobs: list[JobPosting] = []
        url = "https://www.arbeitnow.com/api/job-board-api"

        with httpx.Client(timeout=self.timeout_seconds) as client:
            pages = 0
            next_url: str | None = url
            while next_url and pages < self.max_pages:
                try:
                    resp = client.get(next_url)
                    resp.raise_for_status()
                    payload = resp.json()
                except Exception:
                    break

                for item in payload.get("data", []):
                    location = item.get("location", "")
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

                next_url = ((payload.get("links") or {}).get("next_page_url"))
                pages += 1

        return jobs
