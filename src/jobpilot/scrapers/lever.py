from __future__ import annotations

import httpx

from jobpilot.models import JobPosting
from jobpilot.scrapers.base import BaseScraper


class LeverScraper(BaseScraper):
    source_name = "lever"

    def __init__(self, companies: list[str], timeout_seconds: int = 15):
        self.companies = companies
        self.timeout_seconds = timeout_seconds

    def fetch_jobs(self) -> list[JobPosting]:
        jobs: list[JobPosting] = []
        with httpx.Client(timeout=self.timeout_seconds) as client:
            for company in self.companies:
                url = f"https://api.lever.co/v0/postings/{company}?mode=json"
                try:
                    resp = client.get(url)
                    resp.raise_for_status()
                    payload = resp.json()
                except Exception:
                    continue

                for item in payload:
                    categories = item.get("categories", {})
                    location = categories.get("location", "")
                    jobs.append(
                        JobPosting(
                            source=self.source_name,
                            company=company,
                            role=item.get("text", "Unknown Role"),
                            location=location,
                            country=location,
                            description=item.get("descriptionPlain", ""),
                            apply_link=item.get("hostedUrl", ""),
                        )
                    )
        return jobs
