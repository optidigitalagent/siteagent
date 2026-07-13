import json
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel


T = TypeVar("T", bound=BaseModel)


def write_json(path: Path, model: BaseModel | dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(model, BaseModel):
        payload = model.model_dump(mode="json")
    else:
        payload = model
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")

