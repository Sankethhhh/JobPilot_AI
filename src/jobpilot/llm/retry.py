from __future__ import annotations

from tenacity import retry, stop_after_attempt, wait_exponential


def llm_retry(max_attempts: int):
    return retry(
        reraise=True,
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=1, max=5),
    )
