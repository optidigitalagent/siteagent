"""Integrity and durable-history helpers for project-local vendored skills."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def directory_checksum(path: Path) -> str:
    file_hashes = []
    for file in sorted((item for item in path.rglob("*") if item.is_file() and "__pycache__" not in item.parts and item.suffix.lower() != ".pyc"), key=lambda item: str(item).lower()):
        file_hashes.append(hashlib.sha256(file.read_bytes()).hexdigest())
    return hashlib.sha256("".join(file_hashes).encode()).hexdigest()


def validate_skill_lock(path: Path) -> list[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    errors = []
    for skill in payload.get("skills", []):
        target = path.parents[2] / skill["installed_path"]
        if not skill.get("source_commit") or len(skill["source_commit"]) != 40:
            errors.append(f"{skill.get('name')}: unpinned commit")
        if not target.is_dir() or not (target / "SKILL.md").is_file():
            errors.append(f"{skill.get('name')}: missing vendored skill")
        elif skill.get("checksum") != directory_checksum(target):
            errors.append(f"{skill.get('name')}: checksum mismatch")
    return errors


def load_fingerprint_history(path: Path, *, limit: int) -> list[str]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    values = payload.get("fingerprints", []) if isinstance(payload, dict) else []
    return [value for value in values if isinstance(value, str)][-limit:]


def record_fingerprint(path: Path, value: str, *, limit: int) -> None:
    values = load_fingerprint_history(path, limit=limit)
    if value not in values:
        values.append(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"fingerprints": values[-limit:]}, indent=2), encoding="utf-8")
