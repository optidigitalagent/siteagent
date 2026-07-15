"""Local-only execution adapters for vendored design skills.

The adapters deliberately execute files under the repository's ``.agents``
directory.  They never resolve a global skill directory and never fetch a
moving upstream branch at runtime.
"""
from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REQUIRED_SKILLS = ("frontend-design", "ui-ux-pro-max", "web-design-guidelines")


def project_root(start: Path | None = None) -> Path:
    current = (start or Path(__file__)).resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".agents" / "skills").is_dir():
            return candidate
    raise RuntimeError("Project-level .agents/skills directory is required")


@dataclass(frozen=True)
class SkillExecution:
    name: str
    input: dict[str, Any]
    output: dict[str, Any]
    source_path: str

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "input": self.input, "output": self.output, "source_path": self.source_path}


class LocalSkillRuntime:
    def __init__(self, root: Path | None = None) -> None:
        self.root = project_root(root)
        self.skills_root = self.root / ".agents" / "skills"

    def skill_path(self, name: str) -> Path:
        path = self.skills_root / name
        if name not in REQUIRED_SKILLS or not (path / "SKILL.md").is_file():
            raise RuntimeError(f"Missing required project-local skill: {name}")
        return path

    def frontend_design_brief(self, *, category: str, audience: str, goal: str, atmosphere: str) -> SkillExecution:
        path = self.skill_path("frontend-design") / "SKILL.md"
        text = path.read_text(encoding="utf-8")
        # This excerpt is passed to the content/design role; it is not a flag.
        guidance = "\n".join(line for line in text.splitlines() if line.strip())[:6000]
        return SkillExecution(
            "frontend-design",
            {"category": category, "audience": audience, "goal": goal, "atmosphere": atmosphere},
            {"prompt_guidance": guidance, "activation": "SiteSpecAgent user prompt"},
            str(path.relative_to(self.root)),
        )

    def design_system(self, *, category: str, audience: str, offer: str, atmosphere: str, project_name: str) -> SkillExecution:
        script = self.skill_path("ui-ux-pro-max") / "scripts" / "search.py"
        query = " ".join(part for part in (category, offer, audience, atmosphere, "service website") if part).strip()
        command = [sys.executable, str(script), query, "--design-system", "--json", "--stack", "html-tailwind", "--project-name", project_name, "--variance", "7", "--motion", "3", "--density", "4"]
        completed = subprocess.run(command, cwd=self.root, capture_output=True, text=True, check=True, timeout=30)
        result = json.loads(completed.stdout)
        return SkillExecution(
            "ui-ux-pro-max",
            {"query": query, "command": command[2:]},
            result,
            str(script.relative_to(self.root)),
        )

    def web_guidelines(self, index_path: Path) -> SkillExecution:
        """Run the pinned local rule snapshot and return selector-level findings."""
        path = self.skill_path("web-design-guidelines") / "rules.json"
        rules = json.loads(path.read_text(encoding="utf-8"))
        html = index_path.read_text(encoding="utf-8")
        findings: list[dict[str, str]] = []
        for rule in rules["rules"]:
            if rule["kind"] == "required" and rule["needle"].lower() not in html.lower():
                findings.append({"file": "site/index.html", "selector": rule["selector"], "severity": rule["severity"], "rule": rule["id"], "message": rule["message"]})
        return SkillExecution(
            "web-design-guidelines",
            {"index_path": str(index_path)},
            {"rules_version": rules["source_commit"], "findings": findings},
            str(path.relative_to(self.root)),
        )
