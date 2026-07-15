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


STUDIO_PLUGIN_SKILLS = (
    "siteagent-web-studio",
    "creative-director",
    "concept-prototyping",
    "storytelling",
    "conversion-copy",
    "responsive-review",
    "design-critic",
    "anti-template-review",
    "accessibility-review",
)


def validate_studio_plugin_bundle(root: Path) -> list[str]:
    """Check the optional IDE bundle mirrors repository-owned skill sources.

    Runtime deliberately does not call this bundle: `.agents/skills` is the only
    production source of truth.  A stale distribution copy is an actionable
    developer error instead of a hidden behavior change.
    """
    errors: list[str] = []
    plugin = root / "plugins" / "siteagent-web-studio"
    manifest = plugin / ".codex-plugin" / "plugin.json"
    if not manifest.is_file():
        return ["siteagent-web-studio: plugin manifest is missing"]
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
    except ValueError:
        return ["siteagent-web-studio: plugin manifest is invalid JSON"]
    if payload.get("name") != "siteagent-web-studio" or payload.get("skills") != "./skills/":
        errors.append("siteagent-web-studio: plugin manifest does not expose the expected skill bundle")
    for name in STUDIO_PLUGIN_SKILLS:
        source = root / ".agents" / "skills" / name
        bundled = plugin / "skills" / name
        if not source.is_dir() or not (source / "SKILL.md").is_file():
            errors.append(f"{name}: repository source skill is missing")
        elif not bundled.is_dir() or not (bundled / "SKILL.md").is_file():
            errors.append(f"{name}: plugin bundle is missing")
        elif directory_checksum(source) != directory_checksum(bundled):
            errors.append(f"{name}: plugin bundle is stale")
    return errors
