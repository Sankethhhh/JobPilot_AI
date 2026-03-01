from __future__ import annotations

from abc import ABC, abstractmethod

from jobpilot.models import JobPosting


class BaseScraper(ABC):
    source_name: str

    @abstractmethod
    def fetch_jobs(self) -> list[JobPosting]:
        raise NotImplementedError
