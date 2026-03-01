from __future__ import annotations

import httpx

from jobpilot.models import JobPosting
from jobpilot.scrapers.base import BaseScraper


class GreenhouseScraper(BaseScraper):
    source_name = "greenhouse"

    def __init__(self, board_tokens: list[str], timeout_seconds: int = 15):
        self.board_tokens = board_tokens
        self.timeout_seconds = timeout_seconds

    def fetch_jobs(self) -> list[JobPosting]:
        jobs: list[JobPosting] = []
        with httpx.Client(timeout=self.timeout_seconds) as client:
            for token in self.board_tokens:
                url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
                try:
                    resp = client.get(url)
                    resp.raise_for_status()
                    payload = resp.json()
                except Exception:
                    continue

                for item in payload.get("jobs", []):
                    location = (item.get("location") or {}).get("name", "")
                    jobs.append(
                        JobPosting(
                            source=self.source_name,
                            company=token,
                            role=item.get("title", "Unknown Role"),
                            location=location,
                            country=location,
                            description=item.get("content", ""),
                            apply_link=item.get("absolute_url", ""),
                        )
                    )
        return jobs
