from __future__ import annotations

import json
import os
from typing import Any, Type, TypeVar

from pydantic import BaseModel, ValidationError

from jobpilot.config import Settings
from jobpilot.llm.retry import llm_retry

T = TypeVar("T", bound=BaseModel)


class LLMServiceError(Exception):
    pass


class LLMValidationError(LLMServiceError):
    pass


class LLMClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._litellm = None

    @property
    def litellm(self):
        if self._litellm is None:
            try:
                import litellm  # type: ignore
            except Exception as exc:  # pragma: no cover
                raise LLMServiceError("litellm is not installed") from exc
            self._litellm = litellm
        return self._litellm

    def _base_kwargs(self) -> dict:
        kwargs: dict = {
            "model": self.settings.litellm_model,
            "temperature": 0,
            "timeout": self.settings.llm_timeout_seconds,
        }
        if self.settings.litellm_api_base:
            kwargs["api_base"] = self.settings.litellm_api_base
        if os.getenv("OPENAI_API_KEY"):
            kwargs["api_key"] = os.getenv("OPENAI_API_KEY")
        return kwargs

    def _extract_content(self, response: object) -> str:
        try:
            content = response.choices[0].message.content
        except Exception as exc:
            raise LLMServiceError("Malformed LLM response") from exc
        if not content:
            raise LLMServiceError("Empty LLM response")
        return content

    def _unwrap_common_wrappers(self, data: dict[str, Any]) -> dict[str, Any]:
        # Some providers/models wrap payloads in helper keys.
        for key in ("input_json", "output", "result", "data"):
            wrapped = data.get(key)
            if isinstance(wrapped, dict):
                return wrapped
        return data

    def _normalize_for_schema(self, schema_name: str, data: dict[str, Any]) -> dict[str, Any]:
        normalized = self._unwrap_common_wrappers(data)
        if schema_name != "tailored_resume":
            return normalized

        # Accept both experience and experiences from model responses.
        if "experiences" not in normalized and isinstance(normalized.get("experience"), list):
            normalized["experiences"] = normalized["experience"]

        # If model returned a full-resume payload, map to TailorResponse shape.
        if "summary" not in normalized and isinstance(data.get("summary"), str):
            normalized["summary"] = data["summary"]
        if "skills" not in normalized and isinstance(data.get("skills"), list):
            normalized["skills"] = data["skills"]
        if "experiences" not in normalized and isinstance(data.get("experience"), list):
            normalized["experiences"] = data["experience"]

        return normalized

    def generate_structured(self, prompt: str, schema_name: str, output_model: Type[T]) -> T:
        @llm_retry(max_attempts=self.settings.llm_max_retries + 1)
        def _call() -> T:
            try:
                response = self.litellm.completion(
                    messages=[
                        {"role": "system", "content": "Return JSON only."},
                        {"role": "user", "content": prompt},
                    ],
                    response_format={"type": "json_object"},
                    **self._base_kwargs(),
                )
            except Exception as exc:
                raise LLMServiceError(f"LLM request failed: {exc}") from exc

            text = self._extract_content(response)
            try:
                data = json.loads(text)
            except json.JSONDecodeError as exc:
                raise LLMValidationError(f"{schema_name}: invalid JSON") from exc

            if isinstance(data, dict):
                data = self._normalize_for_schema(schema_name=schema_name, data=data)

            try:
                return output_model.model_validate(data)
            except ValidationError as exc:
                raise LLMValidationError(f"{schema_name}: schema validation failed: {exc}") from exc

        return _call()
