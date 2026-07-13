from __future__ import annotations

import json
from typing import TypeVar

from openai import OpenAI
from pydantic import BaseModel, ValidationError

from site_agent.config import settings


T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    pass


class LLMClient:
    def __init__(self, model: str | None = None) -> None:
        if not settings.openai_api_key:
            raise LLMError("OPENAI_API_KEY is required for generation.")
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.model = model or settings.openai_model

    def structured(self, *, system: str, user: str, schema: type[T]) -> T:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": (
                        f"{user}\n\nReturn only valid JSON matching this schema name: "
                        f"{schema.__name__}."
                    ),
                },
            ],
            response_format={"type": "json_object"},
        )
        text = response.choices[0].message.content or ""
        try:
            return schema.model_validate_json(text)
        except ValidationError as exc:
            raise LLMError(f"Model returned invalid {schema.__name__}: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise LLMError(f"Model returned non-JSON {schema.__name__}: {text[:500]}") from exc
