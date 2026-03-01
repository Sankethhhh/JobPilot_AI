from __future__ import annotations

import httpx

from jobpilot.models import JobPosting
from jobpilot.scrapers.base import BaseScraper


class WorkableScraper(BaseScraper):
    source_name = "workable"

    def __init__(self, subdomains: list[str], timeout_seconds: int = 15):
        self.subdomains = subdomains
        self.timeout_seconds = timeout_seconds

    def fetch_jobs(self) -> list[JobPosting]:
        jobs: list[JobPosting] = []
        with httpx.Client(timeout=self.timeout_seconds) as client:
            for subdomain in self.subdomains:
                url = f"https://{subdomain}.workable.com/spi/v3/jobs"
                try:
                    resp = client.get(url)
                    resp.raise_for_status()
                    payload = resp.json()
                except Exception:
                    continue

                for item in payload.get("results", []):
                    location = item.get("location", {}).get("location_str", "")
                    jobs.append(
                        JobPosting(
                            source=self.source_name,
                            company=subdomain,
                            role=item.get("title", "Unknown Role"),
                            location=location,
                            country=location,
                            description=item.get("description", ""),
                            apply_link=item.get("url", ""),
                        )
                    )
        return jobs
