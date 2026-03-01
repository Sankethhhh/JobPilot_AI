from jobpilot.models import JobPosting
from jobpilot.scrapers.base import BaseScraper
from jobpilot.scrapers.orchestrator import discover_jobs


class StubScraper(BaseScraper):
    source_name = "stub"

    def __init__(self, jobs: list[JobPosting]):
        self.jobs = jobs

    def fetch_jobs(self) -> list[JobPosting]:
        return self.jobs


def test_discover_jobs_filters_country_keywords_and_deduplicates():
    jobs = [
        JobPosting(
            source="stub",
            company="Acme",
            role="LLM Engineer",
            location="Berlin, Germany",
            country="",
            description="Build LLM systems",
            apply_link="https://apply/1",
        ),
        JobPosting(
            source="stub",
            company="Acme",
            role="LLM Engineer",
            location="Berlin, Germany",
            country="",
            description="Duplicate listing",
            apply_link="https://apply/1",
        ),
        JobPosting(
            source="stub",
            company="Other",
            role="Data Engineer",
            location="Paris, France",
            country="",
            description="Data role",
            apply_link="https://apply/2",
        ),
    ]

    result = discover_jobs("Germany", ["llm"], [StubScraper(jobs)])
    assert len(result) == 1
    assert result[0].company == "Acme"


def test_discover_jobs_does_not_misclassify_united_states_as_germany():
    jobs = [
        JobPosting(
            source="stub",
            company="USCo",
            role="LLM Engineer",
            location="New York, United States",
            country="",
            description="Build LLM systems",
            apply_link="https://apply/us",
        )
    ]

    result = discover_jobs("Germany", ["llm"], [StubScraper(jobs)])
    assert result == []


def test_discover_jobs_maps_berlin_to_germany():
    jobs = [
        JobPosting(
            source="stub",
            company="DECo",
            role="LLM Engineer",
            location="Berlin",
            country="",
            description="Build LLM systems",
            apply_link="https://apply/de",
        )
    ]

    result = discover_jobs("Germany", ["llm"], [StubScraper(jobs)])
    assert len(result) == 1


def test_discover_jobs_maps_amsterdam_to_netherlands():
    jobs = [
        JobPosting(
            source="stub",
            company="NLCo",
            role="AI Platform Engineer",
            location="Amsterdam",
            country="",
            description="Build AI platform",
            apply_link="https://apply/nl",
        )
    ]

    result = discover_jobs("Netherlands", ["platform"], [StubScraper(jobs)])
    assert len(result) == 1
