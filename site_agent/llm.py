from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import TypeVar

from openai import OpenAI
from pydantic import BaseModel, ValidationError

from site_agent.config import settings


T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    pass


class LLMClient:
    def __init__(self, model: str | None = None) -> None:
        self.provider = settings.llm_provider.strip().lower()
        if self.provider == "auto":
            self.provider = "openai" if settings.openai_api_key else "codex"

        if self.provider == "openai":
            if not settings.openai_api_key:
                raise LLMError("OPENAI_API_KEY is required when LLM_PROVIDER=openai.")
            self.client = OpenAI(api_key=settings.openai_api_key)
            self.model = model or settings.openai_model
            return

        if self.provider == "codex":
            codex_command = shutil.which(settings.codex_command)
            if not codex_command:
                raise LLMError(
                    f"Codex CLI command not found: {settings.codex_command}. "
                    "Install Codex or set CODEX_COMMAND."
                )
            self.client = None
            self.codex_command = codex_command
            self.model = model or settings.codex_model
            return

        raise LLMError(f"Unsupported LLM_PROVIDER: {settings.llm_provider}")

    def structured(self, *, system: str, user: str, schema: type[T]) -> T:
        if self.provider == "codex":
            return self._codex_structured(system=system, user=user, schema=schema)
        return self._openai_structured(system=system, user=user, schema=schema)

    def _openai_structured(self, *, system: str, user: str, schema: type[T]) -> T:
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

    def _codex_structured(self, *, system: str, user: str, schema: type[T]) -> T:
        prompt = (
            f"{system.strip()}\n\n"
            "You are running as a non-interactive structured generation backend for site-agent. "
            "Do not edit files, run commands, or ask follow-up questions. "
            f"Return only JSON that matches the {schema.__name__} schema.\n\n"
            f"{user.strip()}\n"
        )

        with tempfile.TemporaryDirectory(prefix="site-agent-codex-") as temp_dir:
            temp_path = Path(temp_dir)
            schema_path = temp_path / "schema.json"
            output_path = temp_path / "output.json"
            strict_schema = self._strict_json_schema(schema.model_json_schema())
            schema_path.write_text(
                json.dumps(strict_schema, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            command = [
                self.codex_command,
                "exec",
                "-C",
                str(Path.cwd()),
                "--sandbox",
                "read-only",
                "--output-schema",
                str(schema_path),
                "-o",
                str(output_path),
                "-",
            ]
            if self.model:
                command[2:2] = ["-m", self.model]

            result = subprocess.run(
                command,
                input=prompt,
                text=True,
                encoding="utf-8",
                capture_output=True,
                check=False,
            )
            if result.returncode != 0:
                output = (result.stderr or result.stdout or "").strip()
                raise LLMError(f"Codex CLI generation failed: {output[:2000]}")
            if not output_path.exists():
                output = (result.stdout or result.stderr or "").strip()
                raise LLMError(f"Codex CLI did not write structured output: {output[:2000]}")

            text = output_path.read_text(encoding="utf-8").strip()

        try:
            return schema.model_validate_json(text)
        except ValidationError as exc:
            raise LLMError(f"Codex returned invalid {schema.__name__}: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise LLMError(f"Codex returned non-JSON {schema.__name__}: {text[:500]}") from exc

    def _strict_json_schema(self, schema: dict) -> dict:
        strict_schema = json.loads(json.dumps(schema))

        def normalize(node):
            if isinstance(node, dict):
                node.pop("default", None)
                if node.get("type") == "object" or "properties" in node:
                    node["additionalProperties"] = False
                    properties = node.get("properties")
                    if isinstance(properties, dict):
                        node["required"] = list(properties.keys())
                for value in node.values():
                    normalize(value)
            elif isinstance(node, list):
                for item in node:
                    normalize(item)

        normalize(strict_schema)
        return strict_schema
