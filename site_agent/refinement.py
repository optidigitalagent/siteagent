"""Persistent browser-gated refinement workflow for existing site projects.

The refinement lane is separate from new-site generation and has no publisher,
Telegram queue, or production-deployment dependency.
"""
from __future__ import annotations

import hashlib
import fnmatch
import json
import os
import re
import shlex
import shutil
import socket
import subprocess
import tempfile
import time
import uuid
from urllib.parse import urljoin, urlparse
from urllib.request import urlopen
from datetime import datetime, timezone
from contextlib import contextmanager
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Literal, Protocol

from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field, ValidationError

from site_agent.config import settings
from site_agent.critic import TechnicalInspector
from site_agent.models import TechnicalGate
from site_agent.studio import CodexStudioRunner


REFINEMENT_MODE = "site_refinement"
TARGET_WIDTHS = (1440, 1024, 768, 390, 360)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class RefinementError(RuntimeError):
    pass


class RefinementStatus(str, Enum):
    INTAKE_INCOMPLETE = "INTAKE_INCOMPLETE"
    BASELINE_CAPTURED = "BASELINE_CAPTURED"
    IMPLEMENTING = "IMPLEMENTING"
    VISUAL_QA = "VISUAL_QA"
    CONTENT_QA = "CONTENT_QA"
    FUNCTIONAL_QA = "FUNCTIONAL_QA"
    BROWSER_QA = "BROWSER_QA"
    BLOCKED = "BLOCKED"
    CANDIDATE_READY = "CANDIDATE_READY"
    USER_ACCEPTED = "USER_ACCEPTED"


class RequirementState(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    SUPERSEDED = "superseded"
    REJECTED = "rejected"


class RefinementRequirement(BaseModel):
    id: str
    text: str
    state: RequirementState = RequirementState.ACTIVE
    scope: list[str] = Field(default_factory=list)
    created_at: str
    iteration: int
    supersedes: list[str] = Field(default_factory=list)
    resolution: str = ""


class RefinementAttachmentInput(BaseModel):
    path: str
    kind: Literal["reference", "screenshot", "business_photo", "document", "other"] = "other"
    target_page: str = ""
    target_section: str = ""
    match_kind: Literal["exact", "visual_direction"] = "visual_direction"
    interpretation: str = ""
    transfer: list[str] = Field(default_factory=list)


class RefinementAttachment(BaseModel):
    id: str
    original_name: str
    stored_path: str
    sha256: str
    kind: str
    target_page: str = ""
    target_section: str = ""
    match_kind: str = "visual_direction"
    interpretation: str = ""
    transfer: list[str] = Field(default_factory=list)
    extracted_text: str = ""
    added_at: str


class RefinementBusinessData(BaseModel):
    contacts: list[str] = Field(default_factory=list)
    address: str = ""
    hours: list[str] = Field(default_factory=list)
    prices: list[str] = Field(default_factory=list)
    services: list[str] = Field(default_factory=list)
    texts: list[str] = Field(default_factory=list)
    other: dict[str, Any] = Field(default_factory=dict)


class BusinessDataRevision(BaseModel):
    recorded_at: str
    iteration: int
    data: RefinementBusinessData


class StatusTransition(BaseModel):
    from_status: str
    to_status: str
    at: str
    reason: str


class RefinementSession(BaseModel):
    schema_version: int = 1
    session_id: str
    project_id: str
    project_path: str
    active_mode: Literal["site_refinement"] = REFINEMENT_MODE
    user_goal: str
    status: RefinementStatus = RefinementStatus.INTAKE_INCOMPLETE
    iteration: int = 0
    requirements: list[RefinementRequirement] = Field(default_factory=list)
    business_data: RefinementBusinessData = Field(default_factory=RefinementBusinessData)
    business_data_history: list[BusinessDataRevision] = Field(default_factory=list)
    attachments: list[RefinementAttachment] = Field(default_factory=list)
    immutable_constraints: list[str] = Field(default_factory=list)
    scope: list[str] = Field(default_factory=list)
    completed_tasks: list[str] = Field(default_factory=list)
    open_tasks: list[str] = Field(default_factory=list)
    rejected_tasks: dict[str, str] = Field(default_factory=dict)
    blockers: list[str] = Field(default_factory=list)
    resolved_blockers: list[str] = Field(default_factory=list)
    last_qa_result: dict[str, Any] = Field(default_factory=dict)
    candidate_summary: str = ""
    candidate_tree_sha256: str = ""
    candidate_requirement_sha256: str = ""
    candidate_screenshot_sha256: dict[str, str] = Field(default_factory=dict)
    candidate_artifact_sha256: dict[str, str] = Field(default_factory=dict)
    candidate_baseline_sha256: str = ""
    candidate_baseline_tree_sha256: str = ""
    candidate_snapshot_sha256: str = ""
    candidate_iteration: int = -1
    baseline_path: str = ""
    preview_url: str = ""
    entry_path: str = ""
    build_command: str = ""
    start_command: str = ""
    test_commands: list[str] = Field(default_factory=list)
    status_history: list[StatusTransition] = Field(default_factory=list)
    created_at: str
    updated_at: str

    @property
    def active_requirements(self) -> list[RefinementRequirement]:
        return [item for item in self.requirements if item.state is RequirementState.ACTIVE]


class RefinementRequest(BaseModel):
    project: str = ""
    goal: str = ""
    feedback: list[str] = Field(default_factory=list)
    supersedes: list[str] = Field(default_factory=list)
    attachments: list[RefinementAttachmentInput] = Field(default_factory=list)
    business_data: RefinementBusinessData = Field(default_factory=RefinementBusinessData)
    constraints: list[str] = Field(default_factory=list)
    immutable_elements: list[str] = Field(default_factory=list)
    scope: list[str] = Field(default_factory=list)
    preview_url: str = ""
    entry_path: str = ""
    build_command: str = ""
    start_command: str = ""
    test_commands: list[str] = Field(default_factory=list)
    resolve_blockers: list[str] = Field(default_factory=list)


class RefinementImplementationResult(BaseModel):
    summary: str
    changed_files: list[str] = Field(default_factory=list)
    completed_requirement_ids: list[str] = Field(default_factory=list)
    open_requirement_ids: list[str] = Field(default_factory=list)
    rejected_requirements: dict[str, str] = Field(default_factory=dict)
    blockers: list[str] = Field(default_factory=list)
    remaining_differences: list[str] = Field(default_factory=list)
    functional_qa_passed: bool = False
    content_qa_passed: bool = False
    animation_qa_passed: bool = False
    business_data_applied: bool = False
    placeholders_absent: bool = False
    browser_review_performed: bool = False
    functional_scenarios: list["FunctionalScenarioEvidence"] = Field(default_factory=list)


class FunctionalScenarioEvidence(BaseModel):
    kind: Literal["navigation", "cta", "form", "menu", "accordion", "modal", "slider", "map", "video", "other"]
    target: str
    states_checked: list[str] = Field(default_factory=list)
    passed: bool
    evidence: str


RefinementImplementationResult.model_rebuild()


class RefinementReviewIssue(BaseModel):
    severity: Literal["p0", "p1", "p2", "p3"]
    area: str
    problem: str
    required_fix: str


class RefinementReviewResult(BaseModel):
    decision: Literal["accept", "revise", "blocked"]
    visual_qa_passed: bool
    responsive_qa_passed: bool
    requirements_match: bool
    reference_comparison_passed: bool
    functional_qa_passed: bool
    content_qa_passed: bool
    animation_qa_passed: bool
    issues: list[RefinementReviewIssue] = Field(default_factory=list)
    remaining_differences: list[str] = Field(default_factory=list)
    summary: str


class ReferenceAnalysisResult(BaseModel):
    target_page: str
    target_section: str
    match_kind: Literal["exact", "visual_direction"]
    interpretation: str
    transfer: list[str]
    ambiguous: bool = False
    blocker: str = ""


class RefinementExecutor(Protocol):
    def run(self, *, session: RefinementSession, iteration_dir: Path,
            attachments: list[Path]) -> RefinementImplementationResult: ...


class RefinementReviewer(Protocol):
    def review(self, *, session: RefinementSession, iteration_dir: Path,
               implementation: RefinementImplementationResult, gate: TechnicalGate,
               screenshots: list[Path]) -> RefinementReviewResult: ...


class CodexRefinementExecutor:
    """Edit the existing project with the local Codex implementation plane."""

    def __init__(self, *, timeout: int | None = None) -> None:
        self.timeout = timeout or settings.codex_creative_fixer_timeout_seconds

    def run(self, *, session: RefinementSession, iteration_dir: Path,
            attachments: list[Path]) -> RefinementImplementationResult:
        prompt = f"""
Execute SiteAgent {REFINEMENT_MODE} for the existing project at
{session.project_path}. This is not new-site generation. Preserve its current
design system and accepted business context.

Use the project-local frontend/design, implementation, responsive,
accessibility, browser and visual-QA skills that apply. Read the accumulated
brief below before editing. Implement every active, safely actionable
requirement. Respect immutable constraints. Never widen a reference beyond its
recorded target page/section. Confirmed business data has priority; do not
invent contacts, prices, services, people, qualifications, guarantees or
numeric claims. Missing facts become blockers without stopping unrelated work.

Run relevant build/tests and inspect the rendered result in a real browser.
Check functionality and animation/reduced-motion behavior. Do not publish,
deploy, touch Telegram state or recreate the site from scratch. After editing,
return only the structured iteration result. Record a passed functional_scenario
for every applicable navigation/CTA/form/menu/accordion/modal/slider/map/video
journey, including invalid plus success/error or honest fallback states for forms.

Accumulated session contract:
{session.model_dump_json(indent=2)}
""".strip()
        return _invoke_codex_model(
            project_dir=Path(session.project_path), prompt=prompt,
            schema=RefinementImplementationResult,
            output_dir=iteration_dir / "implementation", sandbox="workspace-write",
            images=attachments, timeout=self.timeout,
        )


class CodexRefinementReviewer:
    """Independent screenshot-led critic that cannot edit the project."""

    def __init__(self, *, timeout: int | None = None) -> None:
        self.timeout = timeout or settings.codex_art_director_timeout_seconds

    def review(self, *, session: RefinementSession, iteration_dir: Path,
               implementation: RefinementImplementationResult, gate: TechnicalGate,
               screenshots: list[Path]) -> RefinementReviewResult:
        prompt = f"""
Act as an independent SiteAgent refinement critic. Review the rendered
screenshots against the complete live brief, immutable constraints and scoped
reference mappings. Do not edit. Reject when an active requirement is missing,
a scoped reference was applied globally, a P0/P1 defect remains, or responsive,
functional, content, animation/reduced-motion or browser evidence is missing.
A passing build alone is never acceptance.

Session:
{session.model_dump_json(indent=2)}

Implementation report:
{implementation.model_dump_json(indent=2)}

Deterministic browser gate:
{gate.model_dump_json(indent=2)}
""".strip()
        return _invoke_codex_model(
            project_dir=Path(session.project_path), prompt=prompt,
            schema=RefinementReviewResult,
            output_dir=iteration_dir / "independent_review", sandbox="read-only",
            images=screenshots, timeout=self.timeout,
        )


def load_refinement_request(path: Path) -> RefinementRequest:
    try:
        return RefinementRequest.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError, json.JSONDecodeError) as exc:
        raise RefinementError(f"Invalid refinement input JSON: {path}") from exc


def _invoke_codex_model(*, project_dir: Path, prompt: str, schema: type[BaseModel],
                        output_dir: Path, sandbox: Literal["workspace-write", "read-only"],
                        images: list[Path], timeout: int) -> Any:
    codex = shutil.which(settings.codex_command)
    if not codex:
        raise RefinementError(f"Codex CLI command not found: {settings.codex_command}")
    output_dir.mkdir(parents=True, exist_ok=True)
    schema_path, output_path = output_dir / "schema.json", output_dir / "result.json"
    schema_path.write_text(
        json.dumps(_strict_schema(schema.model_json_schema()), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    command = [codex, "exec", "--disable", "code_mode_host", "-C", str(project_dir),
               "--sandbox", sandbox, "--output-schema", str(schema_path),
               "-o", str(output_path), "-"]
    for image in images:
        if image.is_file():
            command[2:2] = ["--image", str(image)]
    if settings.codex_model:
        command[2:2] = ["-m", settings.codex_model]
    try:
        completed = CodexStudioRunner._run_subprocess_tree(
            command, prompt, timeout=timeout, env=_safe_refinement_env()
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RefinementError(f"Codex refinement invocation failed: {type(exc).__name__}") from exc
    if completed.returncode != 0 or not output_path.is_file():
        diagnostic = (completed.stderr or completed.stdout or "").strip()[:1200]
        raise RefinementError(f"Codex refinement task failed: {diagnostic}")
    try:
        return schema.model_validate_json(output_path.read_text(encoding="utf-8"))
    except (ValidationError, json.JSONDecodeError) as exc:
        raise RefinementError(f"Codex returned invalid {schema.__name__} output.") from exc


def _strict_schema(schema: dict[str, Any]) -> dict[str, Any]:
    value = json.loads(json.dumps(schema))

    def normalize(node: Any) -> None:
        if isinstance(node, dict):
            node.pop("default", None)
            if node.get("type") == "object" or "properties" in node:
                node["additionalProperties"] = False
                if isinstance(node.get("properties"), dict):
                    node["required"] = list(node["properties"].keys())
            for child in node.values():
                normalize(child)
        elif isinstance(node, list):
            for child in node:
                normalize(child)

    normalize(value)
    return value


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _normalized_nonempty(values: list[str]) -> list[str]:
    return _unique([" ".join(value.split()) for value in values if value and value.strip()])


def _brief_checksum(session: RefinementSession) -> str:
    payload = {
        "user_goal": session.user_goal,
        "requirements": [item.model_dump(mode="json") for item in session.requirements],
        "business_data": session.business_data.model_dump(mode="json"),
        "business_data_history": [item.model_dump(mode="json")
                                  for item in session.business_data_history],
        "immutable_constraints": session.immutable_constraints,
        "scope": session.scope,
        "attachments": [item.model_dump(mode="json") for item in session.attachments],
    }
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def _observation_payloads(observations: dict[str, str]) -> list[dict[str, Any]]:
    payloads = []
    for value in observations.values():
        try:
            payload = json.loads(value)
        except (TypeError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            payloads.append(payload)
    return payloads


def _functional_coverage_passes(implementation: RefinementImplementationResult,
                                observations: dict[str, str]) -> bool:
    payloads = _observation_payloads(observations)
    detected = {"forms": 0, "menus": 0, "accordions": 0, "dialogs": 0,
                "sliders": 0, "videos": 0, "maps": 0, "primary_ctas": 0}
    for payload in payloads:
        interactions = payload.get("interactions") or {}
        for key in detected.keys() - {"primary_ctas"}:
            detected[key] = max(detected[key], int(interactions.get(key, 0) or 0))
        detected["primary_ctas"] = max(
            detected["primary_ctas"], int(payload.get("primaryCtaCount", 0) or 0)
        )
    required = {
        "forms": "form", "menus": "menu", "accordions": "accordion",
        "dialogs": "modal", "sliders": "slider", "videos": "video",
        "maps": "map", "primary_ctas": "cta",
    }
    scenarios = [item for item in implementation.functional_scenarios if item.passed]
    action_links = [link for payload in payloads for link in payload.get("actionLinks", [])
                    if isinstance(link, dict)]
    for detected_key, scenario_kind in required.items():
        if detected[detected_key] and not any(item.kind == scenario_kind for item in scenarios):
            return False
    for item in scenarios:
        if item.kind in {"cta", "navigation"} and not any(
            link.get("href") == item.target and
            (item.kind != "cta" or link.get("primary"))
            for link in action_links
        ):
            return False
    for item in scenarios:
        if item.kind == "form":
            states = {state.casefold() for state in item.states_checked}
            if "invalid" not in states or not states.intersection({"success", "error", "fallback"}):
                return False
    if detected["forms"]:
        browser_checks = [payload.get("interactionChecks") or {} for payload in payloads]
        if not browser_checks or any(
            not check.get("passed") or
            not {"form-invalid", "form-valid"}.issubset(set(check.get("checked") or []))
            for check in browser_checks
        ):
            return False
    return True


def _business_values(data: RefinementBusinessData) -> list[str]:
    values = data.contacts + data.hours + data.prices + data.services + data.texts
    if data.address:
        values.append(data.address)

    def flatten(value: Any) -> None:
        if isinstance(value, dict):
            for item in value.values():
                flatten(item)
        elif isinstance(value, list):
            for item in value:
                flatten(item)
        elif value is not None and str(value).strip():
            values.append(str(value))

    flatten(data.other)
    return _unique([" ".join(value.split()) for value in values])


def _contact_endpoint(value: str) -> str:
    candidate = value.strip().casefold()
    if "@" in candidate and not candidate.startswith("mailto:"):
        return "mailto:" + candidate
    digits = re.sub(r"\D", "", candidate)
    if len(digits) >= 7 and not candidate.startswith(("http://", "https://")):
        return "tel:" + digits
    return candidate.rstrip("/")


def _observed_action_links(observations: dict[str, str]) -> list[dict[str, Any]]:
    return [link for payload in _observation_payloads(observations)
            for link in payload.get("actionLinks", []) if isinstance(link, dict)]


def _business_data_matches(session: RefinementSession, observations: dict[str, str],
                           session_dir: Path) -> bool:
    required = _business_values(session.business_data)
    rendered = " ".join(str(item.get("bodyText", ""))
                        for item in _observation_payloads(observations)).casefold()
    rendered = " ".join(rendered.split())
    if not all(" ".join(value.split()).casefold() in rendered for value in required):
        return False
    links = _observed_action_links(observations)
    current_endpoints = {_contact_endpoint(str(link.get("href", ""))) for link in links}
    explicit_endpoints = {_contact_endpoint(value) for value in required
                          if "@" in value or len(re.sub(r"\D", "", value)) >= 7
                          or value.strip().casefold().startswith(("http://", "https://"))}
    if not explicit_endpoints.issubset(current_endpoints):
        return False
    baseline_path = session_dir / session.baseline_path
    try:
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    baseline_endpoints = {
        _contact_endpoint(str(link.get("href", "")))
        for link in _observed_action_links(baseline.get("observations") or {})
        if link.get("contact") or link.get("primary")
    }
    authorized = baseline_endpoints | explicit_endpoints
    used_contacts = {
        _contact_endpoint(str(link.get("href", ""))) for link in links
        if link.get("contact") or link.get("primary")
    }
    return used_contacts.issubset(authorized)


_NUMBER_WORDS = (
    "zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
    "thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|"
    "thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|million|"
    "ноль|один|одна|одно|два|две|три|четыре|пять|шесть|семь|восемь|девять|"
    "десять|одиннадцать|двенадцать|тринадцать|четырнадцать|пятнадцать|"
    "шестнадцать|семнадцать|восемнадцать|девятнадцать|двадцать|тридцать|"
    "сорок|пятьдесят|шестьдесят|семьдесят|восемьдесят|девяносто|сто|"
    "двести|триста|четыреста|пятьсот|шестьсот|семьсот|восемьсот|девятьсот|"
    "тысяча|тысячи|тысяч|миллион|миллиона|миллионов|"
    "нуль|один|одна|одне|два|дві|три|чотири|п'ять|п’ять|шість|сім|вісім|"
    "дев'ять|дев’ять|десять|одинадцять|дванадцять|тринадцять|чотирнадцять|"
    "п'ятнадцять|п’ятнадцять|шістнадцять|сімнадцять|вісімнадцять|"
    "дев'ятнадцять|дев’ятнадцять|двадцять|тридцять|сорок|п'ятдесят|"
    "п’ятдесят|шістдесят|сімдесят|вісімдесят|дев'яносто|дев’яносто|сто|"
    "двісті|триста|чотириста|п'ятсот|п’ятсот|шістсот|сімсот|вісімсот|"
    "дев'ятсот|дев’ятсот|тисяча|тисячі|тисяч|мільйон|мільйона|мільйонів"
)


def _numeric_claim_fragments(text: str) -> set[str]:
    fragments = re.split(r"[\r\n.!?;]+", text)
    indicator = re.compile(rf"(?<!\w)\d|\b(?:{_NUMBER_WORDS})\b", re.IGNORECASE)
    return {
        " ".join(re.sub(r"[^\w@+%.,:/-]+", " ", fragment.casefold()).split())
        for fragment in fragments if indicator.search(fragment)
    } - {""}


def _numeric_claims_safe(session: RefinementSession, observations: dict[str, str],
                         session_dir: Path) -> bool:
    current = " ".join(str(item.get("bodyText", ""))
                       for item in _observation_payloads(observations))
    baseline_path = session_dir / session.baseline_path
    try:
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    baseline_observations = baseline.get("observations") or {}
    prior = " ".join(str(item.get("bodyText", ""))
                     for item in _observation_payloads(baseline_observations))
    allowed_values = _business_values(session.business_data) + [
        item.text for item in session.requirements
    ]
    current_claims = _numeric_claim_fragments(current)
    prior_claims = _numeric_claim_fragments(prior)
    allowed_claims = _numeric_claim_fragments("\n".join(allowed_values))
    for claim in current_claims - prior_claims:
        if claim not in allowed_claims:
            return False
    return True


def _safe_refinement_env() -> dict[str, str]:
    allowed = {
        "PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "COMSPEC", "TEMP", "TMP",
        "USERPROFILE", "APPDATA", "LOCALAPPDATA", "PROGRAMDATA", "VIRTUAL_ENV",
        "LANG", "LC_ALL",
    }
    env = {key: value for key, value in os.environ.items() if key.upper() in allowed}
    env["PUBLISH_REQUIRED"] = "false"
    env["HOSTING_PROVIDER"] = "local"
    return env


def _codex_sandbox_executable() -> Path:
    """Resolve the native Codex binary so shell wrappers cannot reinterpret args."""
    override = os.getenv("SITEAGENT_CODEX_SANDBOX_EXE", "").strip()
    if override:
        candidate = Path(override).resolve()
        if candidate.is_file():
            return candidate
        raise RefinementError("SITEAGENT_CODEX_SANDBOX_EXE is not a file.")
    if os.name == "nt":
        launcher = shutil.which("codex.cmd") or shutil.which("codex")
        if launcher:
            npm_root = Path(launcher).resolve().parent
            matches = sorted((npm_root / "node_modules" / "@openai" / "codex" /
                              "node_modules" / "@openai").glob(
                                  "codex-win32-*/vendor/*/bin/codex.exe"
                              ))
            if len(matches) == 1 and matches[0].is_file():
                return matches[0].resolve()
    else:
        launcher = shutil.which("codex")
        if launcher and Path(launcher).is_file():
            return Path(launcher).resolve()
    raise RefinementError(
        "Refinement commands require the native Codex sandbox executable; "
        "the workflow fails closed when it is unavailable."
    )


def _sandboxed_command(tokens: list[str], project: Path) -> list[str]:
    executable = shutil.which(tokens[0])
    if not executable and Path(tokens[0]).is_file():
        executable = str(Path(tokens[0]).resolve())
    if not executable:
        raise RefinementError(f"Refinement command executable was not found: {tokens[0]}")
    return [
        str(_codex_sandbox_executable()), "sandbox", "-P", ":workspace",
        "-C", str(project.resolve()), "--", executable, *tokens[1:],
    ]


def _localhost_endpoint_open(preview_url: str) -> bool:
    """Fail closed by exclusively probing ownership of every localhost address."""
    parsed = urlparse(preview_url)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in {
        "localhost", "127.0.0.1",
    }:
        raise RefinementError("Preview endpoint checks accept only localhost HTTP URLs.")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    # A successful connect catches wildcard/dual-stack listeners that Windows
    # may allow an exclusive specific-address bind to overlap. Failure remains
    # ambiguous and is resolved by the bind probes below.
    try:
        with socket.create_connection((parsed.hostname, port), timeout=0.2):
            return True
    except OSError:
        pass
    try:
        addresses = socket.getaddrinfo(
            parsed.hostname, port, type=socket.SOCK_STREAM
        )
    except OSError:
        return True
    addresses.append((
        socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "",
        ("0.0.0.0", port),
    ))
    if socket.has_ipv6:
        addresses.append((
            socket.AF_INET6, socket.SOCK_STREAM, socket.IPPROTO_TCP, "",
            ("::", port, 0, 0),
        ))
    checked: set[tuple[int, str]] = set()
    for family, socktype, protocol, _, sockaddr in addresses:
        key = (family, str(sockaddr))
        if key in checked:
            continue
        checked.add(key)
        probe = socket.socket(family, socktype, protocol)
        try:
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            probe.bind(sockaddr)
        except OSError:
            return True
        finally:
            probe.close()
    return not checked


def _validate_local_command(command: str, project: Path | None = None) -> None:
    forbidden = re.compile(
        r"\b(deploy|publish|wrangler|vercel|netlify|railway|firebase|cloudflare|"
        r"git\s+push|gh\s+release|aws\s+|curl|wget|invoke-webrequest|"
        r"invoke-restmethod|ssh|scp|sftp|ftp|rsync)\b",
        re.IGNORECASE,
    )
    if forbidden.search(command):
        raise RefinementError("Build/test commands may not publish or deploy from refinement mode.")
    try:
        tokens = shlex.split(command, posix=os.name != "nt")
    except ValueError as exc:
        raise RefinementError("Build/test command quoting is invalid.") from exc
    if not tokens:
        raise RefinementError("Build/test command may not be empty.")
    executable = Path(tokens[0]).name.casefold()
    executable = executable.removesuffix(".exe").removesuffix(".cmd").removesuffix(".bat")
    if executable in {
        "powershell", "pwsh", "cmd", "bash", "sh", "zsh", "fish", "wsl",
        "git", "gh", "curl", "wget", "ssh", "scp", "sftp", "ftp", "rsync",
        "docker", "podman", "terraform", "rm", "rmdir", "del",
    }:
        raise RefinementError("Shell, network, VCS and infrastructure executables are forbidden in refinement commands.")
    if executable in {"python", "python3", "py"} and any(
            token in {"-c", "-"} for token in tokens[1:]):
        raise RefinementError("Inline Python execution is forbidden in refinement commands.")
    if executable in {"node", "deno", "bun"} and any(
            token in {"-e", "--eval", "-p", "--print"} for token in tokens[1:]):
        raise RefinementError("Inline JavaScript execution is forbidden in refinement commands.")
    if project is not None and executable in {"npm", "pnpm", "yarn", "bun"}:
        script_name = ""
        if len(tokens) >= 3 and tokens[1].casefold() in {"run", "run-script"}:
            script_name = tokens[2]
        elif len(tokens) >= 2 and tokens[1].casefold() == "test":
            script_name = "test"
        package_path = project / "package.json"
        if script_name and package_path.is_file():
            try:
                package = json.loads(package_path.read_text(encoding="utf-8"))
                script = str((package.get("scripts") or {}).get(script_name, ""))
            except (OSError, ValueError) as exc:
                raise RefinementError("package.json scripts are unreadable.") from exc
            if not script:
                raise RefinementError(f"Package script is not declared: {script_name}")
            lifecycle = {
                name: str((package.get("scripts") or {}).get(name, ""))
                for name in (f"pre{script_name}", script_name, f"post{script_name}")
            }
            if any(forbidden.search(value) for value in lifecycle.values() if value):
                raise RefinementError(
                    "Referenced package script lifecycle contains a forbidden external action."
                )


def _merge_business_data(current: RefinementBusinessData,
                         incoming: RefinementBusinessData) -> RefinementBusinessData:
    return RefinementBusinessData(
        contacts=_unique(current.contacts + incoming.contacts),
        address=incoming.address or current.address,
        hours=_unique(current.hours + incoming.hours),
        prices=_unique(current.prices + incoming.prices),
        services=_unique(current.services + incoming.services),
        texts=_unique(current.texts + incoming.texts),
        other={**current.other, **incoming.other},
    )


def _project_manifest(project: Path) -> dict[str, Any]:
    excluded = {".git", "node_modules", ".venv", "__pycache__", ".siteagent"}
    records, digest = [], hashlib.sha256()
    files = []
    for item in project.rglob("*"):
        relative = item.relative_to(project)
        if excluded.intersection(relative.parts):
            continue
        if _unsafe_project_link(item):
            raise RefinementError(
                f"Refinement projects and recovery snapshots may not contain links: {relative.as_posix()}"
            )
        if item.is_file():
            files.append(item)
    for path in sorted(files):
        relative, file_digest = path.relative_to(project).as_posix(), _file_sha(path)
        records.append({"path": relative, "sha256": file_digest, "size": path.stat().st_size})
        digest.update(relative.encode("utf-8")); digest.update(file_digest.encode("ascii"))
    return {"tree_sha256": digest.hexdigest(), "files": records}


def _manifest_diff(before: dict[str, Any], after: dict[str, Any]) -> dict[str, list[str]]:
    left = {item["path"]: item["sha256"] for item in before["files"]}
    right = {item["path"]: item["sha256"] for item in after["files"]}
    return {
        "added": sorted(right.keys() - left.keys()),
        "modified": sorted(path for path in right.keys() & left.keys()
                           if right[path] != left[path]),
        "deleted": sorted(left.keys() - right.keys()),
    }


def _merge_technical_gates(gates: list[TechnicalGate]) -> TechnicalGate:
    list_fields = (
        "missing_images", "console_errors", "failed_network_requests", "broken_links",
        "small_tap_targets", "persistent_header_issues", "footer_issues",
        "clipped_primary_ctas", "functional_issues", "reduced_motion_issues", "notes",
    )
    values = {
        field: list(dict.fromkeys(item for gate in gates for item in getattr(gate, field)))
        for field in list_fields
    }
    return TechnicalGate(
        passed=bool(gates) and all(gate.passed for gate in gates),
        horizontal_scroll=any(gate.horizontal_scroll for gate in gates),
        **values,
    )


def _copy_project_snapshot(project: Path, destination: Path) -> None:
    """Preserve source needed to recover a failed in-place refinement edit."""
    if destination.is_dir() and _snapshot_valid(destination):
        return
    _project_manifest(project)  # fail closed before copytree can follow a link
    if destination.exists():
        incomplete = destination.with_name(
            destination.name + f".incomplete-{uuid.uuid4().hex[:8]}"
        )
        os.replace(destination, incomplete)
    temporary = destination.with_name(
        destination.name + f".tmp-{uuid.uuid4().hex[:8]}"
    )
    shutil.copytree(
        project,
        temporary,
        ignore=_snapshot_ignore,
    )
    manifest = _project_manifest(temporary)
    _atomic_json(temporary / ".snapshot_complete.json", manifest)
    os.replace(temporary, destination)


def _snapshot_valid(destination: Path) -> bool:
    marker = destination / ".snapshot_complete.json"
    try:
        expected = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    expected_files = expected.get("files", [])
    for item in expected_files:
        path = destination / item.get("path", "")
        if not path.is_file() or _file_sha(path) != item.get("sha256"):
            return False
    try:
        actual = {
            item["path"]: item["sha256"]
            for item in _project_manifest(destination).get("files", [])
            if item["path"] != ".snapshot_complete.json"
        }
    except RefinementError:
        return False
    return actual == {item["path"]: item["sha256"] for item in expected_files}


_REQUIRED_BROWSER_SCREENSHOTS = {
    "desktop.png": 1440,
    "desktop_1024.png": 1024,
    "tablet.png": 768,
    "mobile.png": 390,
    "mobile_360.png": 360,
    "reduced_motion.png": 390,
    "interaction_desktop_1440.png": 1440,
    "interaction_desktop_1024.png": 1024,
    "interaction_tablet_768.png": 768,
    "interaction_mobile_390.png": 390,
    "interaction_mobile_360.png": 360,
}


def _browser_screenshot_matrix_valid(browser_dir: Path, route_count: int) -> bool:
    try:
        route_dirs = sorted(path for path in browser_dir.iterdir() if path.is_dir())
    except OSError:
        return False
    if len(route_dirs) != route_count:
        return False
    for route_dir in route_dirs:
        for name, expected_width in _REQUIRED_BROWSER_SCREENSHOTS.items():
            path = route_dir / name
            try:
                with Image.open(path) as capture:
                    capture.verify()
                with Image.open(path) as capture:
                    width, height = capture.size
                if width != expected_width or height <= 0:
                    return False
            except (OSError, UnidentifiedImageError):
                return False
    return True


def _unsafe_project_link(path: Path) -> bool:
    is_junction = getattr(path, "is_junction", None)
    return path.is_symlink() or bool(is_junction and is_junction())


def _secret_like(relative: Path) -> bool:
    patterns = (
        ".env", ".env.*", "*.pem", "*.key", "*.pfx", "*.p12", "*.crt",
        "credentials.json", "credentials.*.json", "secrets.json", "secrets.*.json",
        "token.json", "tokens.json",
    )
    lowered = relative.name.lower()
    return any(fnmatch.fnmatch(lowered, pattern) for pattern in patterns)


def _snapshot_ignore(directory: str, names: list[str]) -> set[str]:
    excluded_dirs = {
        ".git", "node_modules", ".venv", "__pycache__", ".siteagent",
        ".next", ".cache", "dist", "build", ".wrangler",
    }
    ignored = {name for name in names if name in excluded_dirs}
    ignored.update(name for name in names if _secret_like(Path(name)))
    return ignored


class SiteRefinementOrchestrator:
    """Coordinate one persistent existing-site refinement session."""

    def __init__(self, *, runs_dir: Path | None = None,
                 executor: RefinementExecutor | None = None,
                 reviewer: RefinementReviewer | None = None,
                 inspector: TechnicalInspector | None = None,
                 command_runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run) -> None:
        self.runs_dir = (runs_dir or settings.runs_dir).resolve()
        self.executor = executor or CodexRefinementExecutor()
        self.reviewer = reviewer or CodexRefinementReviewer()
        self.inspector = inspector or TechnicalInspector(viewport_profile="refinement")
        self.command_runner = command_runner

    def start(self, request: RefinementRequest, *, session_id: str = "",
              execute: bool = True) -> RefinementSession:
        if not request.project.strip():
            raise RefinementError("refinement-start requires an existing project path or run ID.")
        project = self.resolve_project(request.project)
        sid = session_id.strip() or self._new_session_id(project)
        if (self.session_dir(sid) / "session.json").exists():
            raise RefinementError(f"Refinement session already exists: {sid}")
        goal = request.goal.strip() or (request.feedback[0].strip() if request.feedback else "")
        if not goal:
            raise RefinementError("refinement-start requires a user goal or feedback.")
        now = _now()
        session = RefinementSession(
            session_id=sid, project_id=project.name, project_path=str(project),
            user_goal=goal, created_at=now, updated_at=now,
        )
        self._merge_request(session, request, initial=True, session_dir=self.session_dir(sid))
        self._save(session)
        return self.run_iteration(sid) if execute else session

    def continue_session(self, session_id: str, request: RefinementRequest,
                         *, execute: bool = True) -> RefinementSession:
        session = self.load(session_id)
        with self._project_lock(session):
            session = self.load(session_id)
            if session.status is RefinementStatus.USER_ACCEPTED:
                raise RefinementError("An accepted session is immutable; start a new session.")
            session.iteration += 1
            self._merge_request(session, request, initial=False,
                                session_dir=self.session_dir(session_id))
            self._transition(session, RefinementStatus.IMPLEMENTING,
                             "new user feedback resumes refinement")
            self._save(session)
        return self.run_iteration(session_id) if execute else session

    def accept(self, session_id: str) -> RefinementSession:
        session = self.load(session_id)
        with self._project_lock(session):
            return self._accept_locked(session_id)

    def _accept_locked(self, session_id: str) -> RefinementSession:
        session = self.load(session_id)
        if session.status is not RefinementStatus.CANDIDATE_READY:
            raise RefinementError("USER_ACCEPTED requires CANDIDATE_READY.")
        if _project_manifest(Path(session.project_path))["tree_sha256"] != session.candidate_tree_sha256:
            raise RefinementError("Candidate project changed after QA; start another refinement iteration.")
        requirement_sha = _brief_checksum(session)
        if requirement_sha != session.candidate_requirement_sha256:
            raise RefinementError("Candidate brief changed after QA; start another iteration.")
        baseline_path = self.session_dir(session_id) / session.baseline_path
        if (not baseline_path.is_file() or not session.candidate_baseline_sha256
                or _file_sha(baseline_path) != session.candidate_baseline_sha256):
            raise RefinementError("Candidate baseline evidence changed after QA.")
        baseline_dir = baseline_path.parent
        if (_project_manifest(baseline_dir)["tree_sha256"]
                != session.candidate_baseline_tree_sha256):
            raise RefinementError("Candidate baseline artifact tree changed after QA.")
        snapshot = (self.session_dir(session_id) / "iterations" /
                    f"{session.candidate_iteration:03d}" / "pre_change_snapshot")
        marker = snapshot / ".snapshot_complete.json"
        if (not _snapshot_valid(snapshot) or not marker.is_file()
                or _file_sha(marker) != session.candidate_snapshot_sha256):
            raise RefinementError("Candidate recovery snapshot changed after QA.")
        self._validated_attachment_paths(session)
        iteration_dir = self.session_dir(session_id) / "iterations" / f"{session.candidate_iteration:03d}"
        for relative, expected in {
            **{f"browser_qa/{name}": value for name, value in session.candidate_screenshot_sha256.items()},
            **session.candidate_artifact_sha256,
        }.items():
            path = iteration_dir / relative
            if not path.is_file() or _file_sha(path) != expected:
                raise RefinementError("Candidate QA evidence changed after review.")
        self._transition(session, RefinementStatus.USER_ACCEPTED,
                         "explicit user acceptance")
        self._save(session)
        return session

    def load(self, session_id: str) -> RefinementSession:
        path = self.session_dir(session_id) / "session.json"
        if not path.is_file():
            raise RefinementError(f"Unknown refinement session: {session_id}")
        try:
            return RefinementSession.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValidationError, json.JSONDecodeError) as exc:
            raise RefinementError(f"Refinement session is unreadable: {session_id}") from exc

    def session_dir(self, session_id: str) -> Path:
        if (len(session_id) > 120 or not re.fullmatch(
                r"[A-Za-z0-9][A-Za-z0-9_-]*(?:\.[A-Za-z0-9_-]+)*", session_id)):
            raise RefinementError("Invalid refinement session ID.")
        root = (self.runs_dir / "refinement").resolve()
        candidate = (root / session_id).resolve()
        if candidate.parent != root:
            raise RefinementError("Refinement session path escapes the refinement runs directory.")
        return candidate

    def resolve_project(self, value: str) -> Path:
        candidate = Path(value).expanduser()
        for item in (candidate, self.runs_dir / value / "site", self.runs_dir / value):
            resolved = item.resolve()
            refinement_root = (self.runs_dir / "refinement").resolve()
            forbidden = {
                self.runs_dir.resolve(),
                refinement_root,
                Path.cwd().resolve(),
            }
            if refinement_root in resolved.parents:
                continue
            markers = (
                resolved / "index.html", resolved / "package.json",
                resolved / "pyproject.toml",
            )
            if resolved.is_dir() and resolved not in forbidden and any(path.is_file() for path in markers):
                return resolved
            if resolved.is_dir() and resolved not in forbidden and (resolved / "site" / "index.html").is_file():
                return (resolved / "site").resolve()
        raise RefinementError(f"Existing site project was not found: {value}")

    def run_iteration(self, session_id: str) -> RefinementSession:
        session = self.load(session_id)
        with self._project_lock(session):
            session = self.load(session_id)
            if session.status is RefinementStatus.USER_ACCEPTED:
                raise RefinementError("An accepted session is immutable; start a new session.")
            for attempt in range(settings.max_fix_iterations + 1):
                result = self._run_iteration_locked(session_id)
                if result.status is not RefinementStatus.IMPLEMENTING:
                    return result
                if attempt == settings.max_fix_iterations:
                    result.blockers = _unique(result.blockers + [
                        "Bounded refinement fixer iterations were exhausted; manual review is required."
                    ])
                    self._transition(result, RefinementStatus.BLOCKED,
                                     "bounded fixer loop exhausted")
                    self._save(result)
                    return result
                result.iteration += 1
                self._save(result)
            raise AssertionError("unreachable refinement loop")

    def _run_iteration_locked(self, session_id: str) -> RefinementSession:
        session, session_dir = self.load(session_id), self.session_dir(session_id)
        iteration_dir = session_dir / "iterations" / f"{session.iteration:03d}"
        iteration_dir.mkdir(parents=True, exist_ok=True)
        captured_now = False
        if not session.baseline_path:
            self._capture_baseline(session)
            captured_now = True
            self._transition(session, RefinementStatus.BASELINE_CAPTURED,
                             "baseline inventory and browser evidence recorded")
            self._save(session)
        if (not captured_now and not self._baseline_evidence_ready(session)
                and self._baseline_attempt_iteration(session) < session.iteration):
            self._recapture_incomplete_baseline(session)
        if not self._baseline_evidence_ready(session):
            session.blockers = _unique(session.blockers + [
                "A complete multi-route, five-width baseline browser capture is required before editing."
            ])
            self._transition(session, RefinementStatus.BLOCKED,
                             "baseline browser evidence is incomplete")
            self._save(session)
            return session
        self._validated_attachment_paths(session)
        self._analyze_unmapped_references(session, iteration_dir)
        self._save(session)
        plan = {
            "schema_version": 1, "iteration": session.iteration,
            "active_requirements": [item.model_dump(mode="json") for item in session.active_requirements],
            "immutable_constraints": session.immutable_constraints, "scope": session.scope,
            "reference_mappings": [item.model_dump(mode="json") for item in session.attachments
                                   if item.kind in {"reference", "screenshot"}],
        }
        _atomic_json(iteration_dir / "change_plan.json", plan)
        project = Path(session.project_path)
        current_before = _project_manifest(project)
        pre_manifest_path = iteration_dir / "pre_change_manifest.json"
        post_manifest_path = iteration_dir / "post_change_manifest.json"
        implementation_path = iteration_dir / "implementation_result.json"
        snapshot = iteration_dir / "pre_change_snapshot"
        if pre_manifest_path.is_file():
            try:
                pre_manifest = json.loads(pre_manifest_path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise RefinementError("Interrupted iteration has an unreadable pre-change manifest.") from exc
            if not _snapshot_valid(snapshot):
                raise RefinementError("Interrupted iteration has no checksum-valid recovery snapshot.")
        elif snapshot.exists() and _snapshot_valid(snapshot):
            pre_manifest = json.loads(
                (snapshot / ".snapshot_complete.json").read_text(encoding="utf-8")
            )
            _atomic_json(pre_manifest_path, pre_manifest)
        else:
            pre_manifest = current_before
            _copy_project_snapshot(project, snapshot)
            _atomic_json(pre_manifest_path, pre_manifest)
        session.open_tasks = [item.id for item in session.active_requirements]
        self._transition(session, RefinementStatus.IMPLEMENTING, "iteration plan recorded")
        self._save(session)
        attachments = self._validated_attachment_paths(session)
        resumed_implementation = False
        if current_before["tree_sha256"] != pre_manifest.get("tree_sha256"):
            try:
                post_manifest = json.loads(post_manifest_path.read_text(encoding="utf-8"))
                implementation = RefinementImplementationResult.model_validate_json(
                    implementation_path.read_text(encoding="utf-8")
                )
            except (OSError, ValueError, ValidationError, json.JSONDecodeError) as exc:
                raise RefinementError(
                    "Interrupted refinement left partial project edits. The preserved pre-change "
                    "snapshot requires explicit recovery before another implementation pass."
                ) from exc
            if current_before["tree_sha256"] != post_manifest.get("tree_sha256"):
                raise RefinementError(
                    "Project bytes no longer match either the pre-change snapshot or the completed "
                    "implementation checkpoint; refusing to overwrite unknown edits."
                )
            resumed_implementation = True
        if not resumed_implementation:
            implementation = self.executor.run(
                session=session, iteration_dir=iteration_dir,
                attachments=[path for path in attachments if path.is_file()
                             and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".gif"}],
            )
            current_manifest = _project_manifest(project)
            computed_diff = _manifest_diff(pre_manifest, current_manifest)
            implementation.changed_files = computed_diff["added"] + computed_diff["modified"] + [
                f"deleted:{path}" for path in computed_diff["deleted"]
            ]
            _atomic_json(iteration_dir / "computed_diff.json", computed_diff)
            _atomic_json(post_manifest_path, current_manifest)
            _atomic_json(implementation_path, implementation.model_dump(mode="json"))
        self._apply_result(session, implementation)
        commands = self._run_commands(session, iteration_dir)
        with self._managed_server(session, iteration_dir):
            targets = self._browser_targets(session)
            if not targets:
                session.blockers = _unique(session.blockers +
                                           ["No browser target found. Provide preview_url or entry_path."])
                self._transition(session, RefinementStatus.BLOCKED,
                                 "browser QA target is missing")
                self._write_report(session, iteration_dir, implementation, None, None, commands)
                self._save(session)
                return session
            self._transition(session, RefinementStatus.BROWSER_QA,
                             "independent five-width browser inspection started")
            self._save(session)
            browser_dir = iteration_dir / "browser_qa"
            gate, observations = self._inspect_targets(targets, browser_dir, project)
            self._transition(session, RefinementStatus.VISUAL_QA,
                             "rendered screenshots captured")
            reference_images = [session_dir / item.stored_path for item in session.attachments
                                if item.kind in {"reference", "screenshot"}]
            review = self.reviewer.review(
                session=session, iteration_dir=iteration_dir, implementation=implementation,
                gate=gate, screenshots=sorted(browser_dir.rglob("*.png")) +
                [path for path in reference_images if path.is_file()],
            )
        _atomic_json(iteration_dir / "independent_review.json", review.model_dump(mode="json"))
        self._transition(session, RefinementStatus.CONTENT_QA,
                         "content and business-data review recorded")
        self._transition(session, RefinementStatus.FUNCTIONAL_QA,
                         "functional and animation review recorded")
        review_passed = all((
            review.decision == "accept", review.visual_qa_passed,
            review.responsive_qa_passed, review.requirements_match,
            review.reference_comparison_passed, review.functional_qa_passed,
            review.content_qa_passed, review.animation_qa_passed,
            not any(issue.severity in {"p0", "p1"} for issue in review.issues),
        ))
        if review_passed:
            self._finalize_completed(session, implementation.completed_requirement_ids)
        else:
            self._materialize_review_tasks(session, review)
        session.last_qa_result = {
            "browser_reviewed": True, "target_widths": list(TARGET_WIDTHS),
            "observed_viewports": sorted(observations),
            "technical_gate": gate.model_dump(mode="json"),
            "implementation": implementation.model_dump(mode="json"),
            "independent_review": review.model_dump(mode="json"), "commands": commands,
        }
        candidate_rejection_reasons: list[str] = []
        if self._candidate_allowed(
                session, implementation, review, gate, observations, commands,
                browser_dir=browser_dir, route_count=len(targets), snapshot_dir=snapshot,
                rejection_reasons=candidate_rejection_reasons):
            session.candidate_summary = review.summary
            session.candidate_tree_sha256 = _project_manifest(Path(session.project_path))["tree_sha256"]
            session.candidate_requirement_sha256 = _brief_checksum(session)
            session.candidate_screenshot_sha256 = {
                path.relative_to(browser_dir).as_posix(): _file_sha(path)
                for path in sorted(browser_dir.rglob("*.png"))
            }
            session.candidate_iteration = session.iteration
            session.candidate_baseline_sha256 = _file_sha(session_dir / session.baseline_path)
            session.candidate_baseline_tree_sha256 = _project_manifest(
                (session_dir / session.baseline_path).parent
            )["tree_sha256"]
            session.candidate_snapshot_sha256 = _file_sha(snapshot / ".snapshot_complete.json")
            self._transition(session, RefinementStatus.CANDIDATE_READY,
                             "all deterministic refinement gates passed")
        elif session.blockers and not session.active_requirements:
            self._transition(session, RefinementStatus.BLOCKED,
                             "only external or missing-data blockers remain")
        else:
            self._transition(session, RefinementStatus.IMPLEMENTING,
                             "candidate gates require another material iteration")
        self._write_report(
            session, iteration_dir, implementation, review, gate, commands,
            candidate_rejection_reasons=candidate_rejection_reasons,
        )
        if session.status is RefinementStatus.CANDIDATE_READY:
            bound = [
                iteration_dir / relative for relative in (
                    "candidate_report.json", "independent_review.json",
                    "implementation_result.json", "command_evidence.json",
                    "computed_diff.json", "pre_change_manifest.json",
                    "post_change_manifest.json", "change_plan.json",
                )
            ] + sorted(browser_dir.rglob("*.json"))
            lifecycle = iteration_dir / "server_lifecycle.json"
            if lifecycle.is_file():
                bound.append(lifecycle)
            session.candidate_artifact_sha256 = {
                path.relative_to(iteration_dir).as_posix(): _file_sha(path)
                for path in bound if path.is_file()
            }
        self._save(session)
        return session

    def _merge_request(self, session: RefinementSession, request: RefinementRequest,
                       *, initial: bool, session_dir: Path) -> None:
        texts = [text.strip() for text in request.feedback if text.strip()]
        if initial and request.goal.strip() and request.goal.strip() not in texts:
            texts.insert(0, request.goal.strip())
        known = {item.id for item in session.requirements}
        missing = [item for item in request.supersedes if item not in known]
        if missing:
            raise RefinementError("Cannot supersede unknown requirement IDs: " + ", ".join(missing))
        for item in session.requirements:
            if item.id in request.supersedes:
                item.state, item.resolution = (
                    RequirementState.SUPERSEDED,
                    "Explicitly superseded by later user feedback.",
                )
        for text in texts:
            session.requirements.append(RefinementRequirement(
                id=f"req-{uuid.uuid4().hex[:10]}", text=text,
                scope=list(request.scope), created_at=_now(),
                iteration=session.iteration, supersedes=list(request.supersedes),
            ))
        for constraint in request.constraints + request.immutable_elements:
            if constraint.strip() and constraint.strip() not in session.immutable_constraints:
                session.immutable_constraints.append(constraint.strip())
        for blocker in request.resolve_blockers:
            if blocker in session.blockers:
                session.blockers.remove(blocker)
                session.resolved_blockers.append(blocker)
        session.scope = _unique(session.scope + [item for item in request.scope if item.strip()])
        session.preview_url = request.preview_url or session.preview_url
        session.entry_path = request.entry_path or session.entry_path
        session.build_command = request.build_command or session.build_command
        session.start_command = request.start_command or session.start_command
        session.test_commands = _unique(session.test_commands + request.test_commands)
        if request.business_data != RefinementBusinessData():
            session.business_data = _merge_business_data(session.business_data,
                                                         request.business_data)
            session.business_data_history.append(BusinessDataRevision(
                recorded_at=_now(), iteration=session.iteration, data=request.business_data,
            ))
        for incoming in request.attachments:
            stored = self._store_attachment(incoming, session_dir)
            session.attachments.append(stored)
            if stored.kind == "document" and not stored.extracted_text:
                session.blockers = _unique(session.blockers + [
                    f"Document {stored.id} is not a supported text/Markdown/JSON input."
                ])
        if not session.requirements:
            session.blockers = _unique(session.blockers +
                                       ["No actionable refinement requirement was provided."])
        session.updated_at = _now()

    def _store_attachment(self, incoming: RefinementAttachmentInput,
                          session_dir: Path) -> RefinementAttachment:
        source = Path(incoming.path).expanduser().resolve()
        if not source.is_file():
            raise RefinementError(f"Refinement attachment was not found: {incoming.path}")
        digest, attachment_id = _file_sha(source), ""
        attachment_id = f"asset-{digest[:12]}"
        safe_name = re.sub(r"[^A-Za-z0-9._-]+", "-", source.name).strip("-.") or "attachment"
        relative = Path("inputs") / f"{attachment_id}-{safe_name}"
        destination = session_dir / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            shutil.copy2(source, destination)
        extracted_text = ""
        if incoming.kind == "document" and source.suffix.lower() in {".txt", ".md", ".json"}:
            extracted_text = source.read_text(encoding="utf-8")[:20000]
        return RefinementAttachment(
            id=attachment_id, original_name=source.name,
            stored_path=relative.as_posix(), sha256=digest, kind=incoming.kind,
            target_page=incoming.target_page, target_section=incoming.target_section,
            match_kind=incoming.match_kind, interpretation=incoming.interpretation,
            transfer=_unique(incoming.transfer), extracted_text=extracted_text, added_at=_now(),
        )

    def _validated_attachment_paths(self, session: RefinementSession) -> list[Path]:
        session_dir = self.session_dir(session.session_id)
        inputs_root = (session_dir / "inputs").resolve()
        paths = []
        for attachment in session.attachments:
            path = (session_dir / attachment.stored_path).resolve()
            if path.parent != inputs_root and inputs_root not in path.parents:
                raise RefinementError("Stored refinement attachment escapes the session inputs directory.")
            if (not path.is_file() or _unsafe_project_link(path)
                    or _file_sha(path) != attachment.sha256):
                raise RefinementError(
                    f"Stored refinement attachment changed or is unreadable: {attachment.id}"
                )
            paths.append(path)
        return paths

    def _capture_baseline(self, session: RefinementSession) -> None:
        session_dir, project = self.session_dir(session.session_id), Path(session.project_path)
        baseline_dir = session_dir / "baseline"
        baseline_dir.mkdir(parents=True, exist_ok=True)
        commands = self._run_commands(session, baseline_dir)
        with self._managed_server(session, baseline_dir):
            manifest, targets = _project_manifest(project), self._browser_targets(session)
            report: dict[str, Any] = {
                "schema_version": 1, "captured_at": _now(), "iteration": session.iteration,
                "project_tree_sha256": manifest["tree_sha256"], "files": manifest["files"],
                "browser_targets": targets, "browser_captured": False, "known_issues": [],
                "commands": commands,
            }
            if targets:
                try:
                    gate, observations = self._inspect_targets(
                        targets, baseline_dir / "browser", project
                    )
                    first_route = next(
                        (path for path in sorted((baseline_dir / "browser").iterdir())
                         if path.is_dir()), None
                    )
                    if first_route is not None:
                        for canonical in ("desktop.png", "tablet.png", "mobile.png"):
                            source = first_route / canonical
                            if source.is_file():
                                shutil.copy2(source, baseline_dir / "browser" / canonical)
                    report.update(browser_captured=True,
                                  technical_gate=gate.model_dump(mode="json"),
                                  observations=observations)
                except Exception as exc:
                    report["known_issues"].append(
                        f"Baseline browser capture failed: {type(exc).__name__}: {exc}"
                    )
            else:
                report["known_issues"].append("No initial browser target was discoverable.")
        _atomic_json(baseline_dir / "baseline.json", report)
        session.baseline_path = "baseline/baseline.json"

    def _baseline_attempt_iteration(self, session: RefinementSession) -> int:
        try:
            report = json.loads(
                (self.session_dir(session.session_id) / session.baseline_path).read_text(
                    encoding="utf-8"
                )
            )
            return int(report.get("iteration", -1))
        except (OSError, TypeError, ValueError):
            return -1

    def _recapture_incomplete_baseline(self, session: RefinementSession) -> None:
        session_dir = self.session_dir(session.session_id)
        baseline_dir = session_dir / "baseline"
        baseline_path = session_dir / session.baseline_path
        try:
            report = json.loads(baseline_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise RefinementError("Incomplete baseline evidence is unreadable.") from exc
        current = _project_manifest(Path(session.project_path))
        if current["tree_sha256"] != report.get("project_tree_sha256"):
            raise RefinementError(
                "Project changed after the failed baseline attempt; start a new refinement "
                "session or explicitly recover those unknown edits."
            )
        attempts = session_dir / "baseline_attempts"
        attempts.mkdir(parents=True, exist_ok=True)
        archived = attempts / f"attempt-{session.iteration:03d}-{uuid.uuid4().hex[:8]}"
        if baseline_dir.resolve().parent != session_dir.resolve():
            raise RefinementError("Baseline archive path escapes the refinement session.")
        os.replace(baseline_dir, archived)
        blocker = "A complete multi-route, five-width baseline browser capture is required before editing."
        if blocker in session.blockers:
            session.blockers.remove(blocker)
            session.resolved_blockers.append(blocker)
        session.baseline_path = ""
        self._capture_baseline(session)
        self._transition(session, RefinementStatus.BASELINE_CAPTURED,
                         "incomplete baseline archived and recaptured")
        self._save(session)

    def _baseline_evidence_ready(self, session: RefinementSession) -> bool:
        path = self.session_dir(session.session_id) / session.baseline_path
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        targets = report.get("browser_targets") or []
        observations = report.get("observations") or {}
        routes: dict[str, set[int]] = {}
        for key, value in observations.items():
            try:
                width = int(str(json.loads(value).get("viewport", "0x0")).split("x", 1)[0])
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
            route = key.split(":", 1)[0] if ":" in key else "default"
            routes.setdefault(route, set()).add(width)
        return bool(report.get("browser_captured")) and bool(targets) and (
            len(routes) >= len(targets)
            and all(set(TARGET_WIDTHS).issubset(widths) for widths in routes.values())
        ) and _browser_screenshot_matrix_valid(
            path.parent / "browser", len(targets)
        )

    def _analyze_unmapped_references(self, session: RefinementSession,
                                     iteration_dir: Path) -> None:
        for attachment in session.attachments:
            if attachment.kind not in {"reference", "screenshot"}:
                continue
            if (attachment.target_page or attachment.target_section) and (
                attachment.interpretation or attachment.transfer
            ):
                continue
            path = self._validated_attachment_paths(session)[session.attachments.index(attachment)]
            prompt = f"""
Analyze this user-supplied visual reference for an existing-site refinement.
Using the user's live goal and requirements below, determine its page/section
scope, whether it is an exact target or visual direction, and only the visual
principles to transfer (composition, grid, typography, scale, spacing, component
shape, color, density, photography, interaction, animation, responsive behavior).
Do not copy a whole third-party site. Mark ambiguous only when the user context
cannot support a safe mapping.

Goal: {session.user_goal}
Requirements: {json.dumps([item.text for item in session.active_requirements], ensure_ascii=False)}
""".strip()
            analysis = _invoke_codex_model(
                project_dir=Path(session.project_path), prompt=prompt,
                schema=ReferenceAnalysisResult,
                output_dir=iteration_dir / "reference_analysis" / attachment.id,
                sandbox="read-only", images=[path],
                timeout=settings.codex_art_director_timeout_seconds,
            )
            if analysis.ambiguous:
                session.blockers = _unique(session.blockers + [
                    analysis.blocker or f"Reference {attachment.id} mapping is ambiguous."
                ])
                continue
            attachment.target_page = analysis.target_page
            attachment.target_section = analysis.target_section
            attachment.match_kind = analysis.match_kind
            attachment.interpretation = analysis.interpretation
            attachment.transfer = analysis.transfer

    def _browser_target(self, session: RefinementSession) -> str:
        if session.preview_url:
            if re.match(r"^https?://(localhost|127\.0\.0\.1)(:\d+)?(?:/|$)", session.preview_url):
                return session.preview_url
            raise RefinementError(
                "Candidate browser QA accepts only a local file or managed localhost URL."
            )
        project, candidates = Path(session.project_path), []
        if session.entry_path:
            entry = Path(session.entry_path)
            candidate = (entry if entry.is_absolute() else project / entry).resolve()
            if candidate != project.resolve() and project.resolve() not in candidate.parents:
                raise RefinementError("entry_path must stay inside the selected existing project.")
            candidates.append(candidate)
        candidates.extend(project / relative for relative in (
            "index.html", "dist/index.html", "build/index.html",
            "site/index.html", "public/index.html",
        ))
        for candidate in candidates:
            resolved = candidate.resolve()
            if resolved.is_file():
                if resolved != project.resolve() and project.resolve() not in resolved.parents:
                    raise RefinementError("Browser entry file escapes the selected existing project.")
                if _unsafe_project_link(candidate):
                    raise RefinementError("Browser entry files may not be symlinks or junctions.")
                return resolved.as_uri()
        return ""

    def _browser_targets(self, session: RefinementSession) -> list[str]:
        primary = self._browser_target(session)
        if not primary:
            return []
        targets = [primary]
        parsed = urlparse(primary)
        if parsed.scheme == "file":
            project = Path(session.project_path)
            for path in sorted(project.rglob("*.html")):
                if not {"node_modules", ".git"}.intersection(path.relative_to(project).parts):
                    targets.append(path.resolve().as_uri())
        else:
            for item in session.scope:
                route = item.strip()
                if route.startswith("/") or route.endswith(".html"):
                    candidate = urljoin(primary.rstrip("/") + "/", route.lstrip("/"))
                    parsed_candidate = urlparse(candidate)
                    if (parsed_candidate.scheme not in {"http", "https"}
                            or parsed_candidate.netloc != parsed.netloc
                            or parsed_candidate.hostname not in {"localhost", "127.0.0.1"}):
                        raise RefinementError("Refinement browser routes must stay on the managed localhost origin.")
                    targets.append(candidate)
        return list(dict.fromkeys(targets))

    def _inspect_targets(self, targets: list[str], browser_dir: Path,
                         project_root: Path) -> tuple[TechnicalGate, dict[str, str]]:
        gates, observations = [], {}
        for index, target in enumerate(targets):
            parsed = urlparse(target)
            label_source = Path(parsed.path).stem or "home"
            label = f"{index:02d}-{re.sub(r'[^A-Za-z0-9_-]+', '-', label_source)}"
            if isinstance(self.inspector, TechnicalInspector):
                gate, route_observations = self.inspector.inspect_url(
                    target, browser_dir / label, allowed_file_root=project_root
                )
            else:
                gate, route_observations = self.inspector.inspect_url(
                    target, browser_dir / label
                )
            gates.append(gate)
            observations.update({f"{label}:{key}": value
                                 for key, value in route_observations.items()})
        combined = _merge_technical_gates(gates)
        _atomic_json(browser_dir / "technical_gate.json", combined.model_dump(mode="json"))
        _atomic_json(browser_dir / "routes.json", {"targets": targets})
        return combined, observations

    def _run_commands(self, session: RefinementSession,
                      iteration_dir: Path) -> dict[str, Any]:
        commands = ([('build', session.build_command)] if session.build_command else [])
        commands += [(f"test_{index + 1}", command)
                     for index, command in enumerate(session.test_commands)]
        results = []
        for name, command in commands:
            _validate_local_command(command, Path(session.project_path))
            try:
                tokens = shlex.split(command, posix=os.name != "nt")
                if self.command_runner is subprocess.run:
                    tokens = _sandboxed_command(tokens, Path(session.project_path))
                    completed = CodexStudioRunner._run_subprocess_tree(
                        tokens, "", timeout=settings.codex_full_creative_build_timeout_seconds,
                        env=_safe_refinement_env(), cwd=session.project_path,
                    )
                else:
                    completed = self.command_runner(
                        tokens, cwd=session.project_path, shell=False, text=True,
                        encoding="utf-8", capture_output=True, check=False,
                        timeout=settings.codex_full_creative_build_timeout_seconds,
                        env=_safe_refinement_env(),
                    )
                results.append({"name": name, "command": command,
                                "passed": completed.returncode == 0,
                                "return_code": completed.returncode,
                                "sandboxed": self.command_runner is subprocess.run,
                                "network_access": "restricted" if self.command_runner is subprocess.run
                                                  else "injected_test_runner"})
            except (OSError, subprocess.SubprocessError, RefinementError) as exc:
                results.append({"name": name, "command": command,
                                "passed": False, "error_type": type(exc).__name__})
        project = Path(session.project_path)
        static_bundle = (project / "index.html").is_file() and not any(
            (project / name).is_file() for name in ("package.json", "pyproject.toml")
        )
        evidence = {
            "project_type": "static_bundle" if static_bundle else "source_project",
            "build": next((item for item in results if item["name"] == "build"), {
                "name": "build", "passed": static_bundle,
                "not_applicable": static_bundle,
                "reason": "Static HTML/CSS/JS bundle has no build step." if static_bundle
                          else "Source project requires an explicit build command.",
            }),
            "tests": [item for item in results if item["name"].startswith("test_")] or [{
                "name": "tests", "passed": static_bundle,
                "not_applicable": static_bundle,
                "reason": "Static bundle has no configured test command." if static_bundle
                          else "Source project requires at least one explicit test command.",
            }],
        }
        _atomic_json(iteration_dir / "command_evidence.json", evidence)
        return evidence

    def _start_server(self, session: RefinementSession,
                      evidence_dir: Path) -> subprocess.Popen | None:
        if not session.start_command:
            return None
        if not session.preview_url:
            raise RefinementError("start_command requires a localhost preview_url.")
        self._browser_target(session)  # validates the localhost boundary
        _validate_local_command(session.start_command, Path(session.project_path))
        if self.command_runner is not subprocess.run:
            raise RefinementError(
                "Managed start commands require the production Codex sandbox runner."
            )
        if _localhost_endpoint_open(session.preview_url):
            raise RefinementError(
                "Managed preview port already has a listener before start_command; "
                "refusing to certify an unrelated process."
            )
        evidence_dir.mkdir(parents=True, exist_ok=True)
        with (evidence_dir / "server.stdout.log").open("ab") as stdout, \
             (evidence_dir / "server.stderr.log").open("ab") as stderr:
            command = _sandboxed_command(
                shlex.split(session.start_command, posix=os.name != "nt"),
                Path(session.project_path),
            )
            process = subprocess.Popen(
                command,
                cwd=session.project_path,
                env=_safe_refinement_env(),
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=stderr,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
                start_new_session=os.name != "nt",
            )
        state = {
            "command": session.start_command, "pid": process.pid,
            "started_at": _now(), "preview_url": session.preview_url,
            "stdout": "server.stdout.log", "stderr": "server.stderr.log",
            "sandboxed": True, "network_access": "restricted",
        }
        try:
            _atomic_json(evidence_dir / "server_lifecycle.json", state)
            deadline = time.monotonic() + 45
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RefinementError("Managed preview server exited before browser QA.")
                try:
                    with urlopen(session.preview_url, timeout=2) as response:
                        final = urlparse(response.geturl())
                        expected = urlparse(session.preview_url)
                        if (final.hostname not in {"localhost", "127.0.0.1"}
                                or final.netloc != expected.netloc):
                            raise RefinementError(
                                "Managed preview redirected outside its localhost origin."
                            )
                        if response.status < 500:
                            state["ready_at"] = _now()
                            _atomic_json(evidence_dir / "server_lifecycle.json", state)
                            return process
                except OSError:
                    time.sleep(0.5)
            raise RefinementError("Managed preview server did not become ready within 45 seconds.")
        except Exception as exc:
            self._stop_server(process)
            cleanup_verified = self._server_cleanup_verified(process, session.preview_url)
            state["startup_failed_at"] = _now()
            state["return_code"] = process.poll()
            state["cleanup_verified"] = cleanup_verified
            _atomic_json(evidence_dir / "server_lifecycle.json", state)
            if not cleanup_verified:
                raise RefinementError(
                    "Managed preview startup failed and its process/socket cleanup "
                    "could not be verified."
                ) from exc
            raise

    @contextmanager
    def _managed_server(self, session: RefinementSession, evidence_dir: Path):
        """Guarantee cleanup and durable lifecycle evidence for local preview servers."""
        process: subprocess.Popen | None = None
        try:
            process = self._start_server(session, evidence_dir)
            yield process
        finally:
            self._stop_server(process)
            cleanup_verified = self._server_cleanup_verified(
                process, session.preview_url if session.start_command else ""
            )
            if session.start_command:
                lifecycle_path = evidence_dir / "server_lifecycle.json"
                try:
                    state = json.loads(lifecycle_path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    state = {"command": session.start_command,
                             "preview_url": session.preview_url}
                state["stopped_at"] = _now()
                state["cleanup_verified"] = cleanup_verified
                if process is not None:
                    state["return_code"] = process.poll()
                _atomic_json(lifecycle_path, state)
                if not cleanup_verified:
                    raise RefinementError(
                        "Managed preview process or localhost socket survived cleanup; "
                        "candidate certification is blocked."
                    )

    @staticmethod
    def _stop_server(process: subprocess.Popen | None) -> None:
        if process is not None and process.poll() is None:
            CodexStudioRunner._terminate_process_tree(process)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)

    @staticmethod
    def _server_cleanup_verified(process: subprocess.Popen | None, preview_url: str) -> bool:
        if process is not None and process.poll() is None:
            return False
        if not preview_url:
            return True
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if not _localhost_endpoint_open(preview_url):
                return True
            time.sleep(0.1)
        return False

    def _apply_result(self, session: RefinementSession,
                      result: RefinementImplementationResult) -> None:
        by_id = {item.id: item for item in session.requirements}
        for requirement_id, reason in result.rejected_requirements.items():
            item = by_id.get(requirement_id)
            if item and item.state is RequirementState.ACTIVE and reason.strip():
                item.state, item.resolution = RequirementState.REJECTED, reason.strip()
                session.rejected_tasks[requirement_id] = reason.strip()
        session.open_tasks = [item.id for item in session.active_requirements]
        session.blockers = _unique(session.blockers + result.blockers)

    def _finalize_completed(self, session: RefinementSession,
                            requirement_ids: list[str]) -> None:
        by_id = {item.id: item for item in session.requirements}
        for requirement_id in requirement_ids:
            item = by_id.get(requirement_id)
            if item and item.state is RequirementState.ACTIVE:
                item.state, item.resolution = (
                    RequirementState.COMPLETED,
                    "Implemented and independently verified in browser QA.",
                )
        session.completed_tasks = _unique(session.completed_tasks + requirement_ids)
        session.open_tasks = [item.id for item in session.active_requirements]

    def _materialize_review_tasks(self, session: RefinementSession,
                                  review: RefinementReviewResult) -> None:
        existing = {item.text for item in session.requirements if item.state is RequirementState.ACTIVE}
        for issue in review.issues:
            text = f"QA {issue.severity.upper()} [{issue.area}]: {issue.problem} Fix: {issue.required_fix}"
            if text not in existing:
                session.requirements.append(RefinementRequirement(
                    id=f"qa-{uuid.uuid4().hex[:10]}", text=text,
                    scope=[issue.area], created_at=_now(), iteration=session.iteration,
                ))
                existing.add(text)
        session.open_tasks = [item.id for item in session.active_requirements]

    def _candidate_allowed(self, session: RefinementSession,
                           implementation: RefinementImplementationResult,
                           review: RefinementReviewResult, gate: TechnicalGate,
                           observations: dict[str, str], commands: dict[str, Any],
                           *, browser_dir: Path | None = None,
                           route_count: int = 1,
                           snapshot_dir: Path | None = None,
                           rejection_reasons: list[str] | None = None) -> bool:
        observed_by_route: dict[str, set[int]] = {}
        for key, value in observations.items():
            try:
                width = int(str(json.loads(value).get("viewport", "0x0")).split("x", 1)[0])
            except (ValueError, TypeError, json.JSONDecodeError):
                continue
            route = key.split(":", 1)[0] if ":" in key else "default"
            observed_by_route.setdefault(route, set()).add(width)
        viewport_matrix_passes = bool(observed_by_route) and all(
            set(TARGET_WIDTHS).issubset(widths) for widths in observed_by_route.values()
        ) and len(observed_by_route) >= route_count
        screenshot_matrix_passes = (
            browser_dir is None
            or _browser_screenshot_matrix_valid(browser_dir, route_count)
        )
        blocking_review = any(issue.severity in {"p0", "p1"} for issue in review.issues)
        commands_pass = bool(commands["build"].get("passed")) and all(
            item.get("passed") for item in commands["tests"]
        )
        active_requirement_ids = [item.id for item in session.active_requirements]
        rejected_requirement_ids = [
            item.id for item in session.requirements
            if item.state is RequirementState.REJECTED
        ]
        implementation_differences = _normalized_nonempty(
            implementation.remaining_differences
        )
        review_differences = _normalized_nonempty(review.remaining_differences)
        has_business_data = bool(_business_values(session.business_data))
        business_data_matches = _business_data_matches(
            session, observations, self.session_dir(session.session_id)
        )
        numeric_claims_safe = _numeric_claims_safe(
            session, observations, self.session_dir(session.session_id)
        )
        functional_coverage_passes = _functional_coverage_passes(
            implementation, observations
        )
        snapshot_passes = snapshot_dir is None or _snapshot_valid(snapshot_dir)
        checks = (
            (not active_requirement_ids,
             "Active requirements remain: " + ", ".join(active_requirement_ids)),
            (not session.open_tasks,
             "Session open tasks remain: " + ", ".join(session.open_tasks)),
            (not implementation.open_requirement_ids,
             "Implementation open requirement IDs remain: " +
             ", ".join(implementation.open_requirement_ids)),
            (not rejected_requirement_ids,
             "Rejected requirements remain: " + ", ".join(rejected_requirement_ids)),
            (not session.blockers,
             "Session blockers remain: " + "; ".join(session.blockers)),
            (not has_business_data or implementation.business_data_applied,
             "Confirmed business data exists, but the implementation did not confirm it was applied."),
            (not implementation_differences,
             "Implementation remaining differences: " + "; ".join(implementation_differences)),
            (not review_differences,
             "Review remaining differences: " + "; ".join(review_differences)),
            (gate.passed, "The technical browser gate did not pass."),
            (viewport_matrix_passes,
             "The browser evidence does not cover every required route and target width."),
            (screenshot_matrix_passes,
             "The browser screenshot matrix is incomplete or invalid."),
            (snapshot_passes,
             "The pre-change recovery snapshot is incomplete or checksum-invalid."),
            (implementation.browser_review_performed,
             "The implementation did not confirm browser review."),
            (implementation.functional_qa_passed,
             "The implementation functional QA did not pass."),
            (functional_coverage_passes,
             "The implementation functional-scenario evidence is incomplete."),
            (implementation.content_qa_passed,
             "The implementation content QA did not pass."),
            (implementation.animation_qa_passed,
             "The implementation animation QA did not pass."),
            (business_data_matches,
             "Confirmed business data is not fully present in rendered evidence."),
            (numeric_claims_safe,
             "Rendered numeric claims are not supported by the refinement evidence."),
            (implementation.placeholders_absent,
             "The implementation did not confirm that placeholders are absent."),
            (review.decision == "accept",
             f"Independent review decision is {review.decision!r}, not 'accept'."),
            (review.visual_qa_passed, "Independent visual QA did not pass."),
            (review.responsive_qa_passed, "Independent responsive QA did not pass."),
            (review.requirements_match,
             "Independent review did not confirm that requirements match."),
            (review.reference_comparison_passed,
             "Independent reference comparison did not pass."),
            (review.functional_qa_passed, "Independent functional QA did not pass."),
            (review.content_qa_passed, "Independent content QA did not pass."),
            (review.animation_qa_passed, "Independent animation QA did not pass."),
            (not blocking_review,
             "Independent review contains a P0 or P1 issue."),
            (commands_pass, "A required local build or test command did not pass."),
            (bool(implementation.changed_files),
             "No authored project change was recorded for this iteration."),
        )
        reasons = [message for passed, message in checks if not passed]
        if rejection_reasons is not None:
            rejection_reasons[:] = reasons
        return not reasons

    def _write_report(self, session: RefinementSession, iteration_dir: Path,
                      implementation: RefinementImplementationResult,
                      review: RefinementReviewResult | None,
                      gate: TechnicalGate | None,
                      commands: dict[str, Any],
                      *, candidate_rejection_reasons: list[str] | None = None) -> None:
        implementation_differences = _normalized_nonempty(
            implementation.remaining_differences
        )
        review_differences = _normalized_nonempty(
            review.remaining_differences if review else []
        )
        remaining_differences = _unique(
            implementation_differences + review_differences
        )
        candidate_readiness_evaluated = candidate_rejection_reasons is not None
        candidate_rejection_reasons = list(candidate_rejection_reasons or [])
        payload = {
            "what_changed": implementation.changed_files,
            "what_verified": {
                "target_widths": list(TARGET_WIDTHS),
                "browser_gate": gate.model_dump(mode="json") if gate else None,
                "commands": commands,
            },
            "requirements_comparison": {
                state.value: [item.model_dump(mode="json") for item in session.requirements
                              if item.state is state]
                for state in RequirementState
            },
            "remaining_differences": remaining_differences,
            "remaining_differences_by_source": {
                "implementation": implementation_differences,
                "review": review_differences,
            },
            "candidate_readiness": {
                "evaluated": candidate_readiness_evaluated,
                "allowed": candidate_readiness_evaluated and not candidate_rejection_reasons,
                "rejection_reasons": candidate_rejection_reasons,
            },
            "blockers": session.blockers,
            "current_status": session.status.value,
            "independent_review": review.model_dump(mode="json") if review else None,
        }
        _atomic_json(iteration_dir / "candidate_report.json", payload)
        changed = implementation.changed_files or ["No file change was reported."]
        remaining = payload["remaining_differences"] or ["None recorded."]
        readiness = candidate_rejection_reasons or [
            "None recorded." if candidate_readiness_evaluated
            else "Not evaluated because the iteration stopped before the complete candidate gate."
        ]
        blockers = session.blockers or ["None recorded."]
        lines = [
            "# Refinement iteration report", "", "## What changed",
            *(f"- {item}" for item in changed), "", "## What was verified",
            f"- Responsive widths: {', '.join(str(width) for width in TARGET_WIDTHS)}",
            f"- Browser gate: {'passed' if gate and gate.passed else 'not passed'}",
            "", "## Remaining differences", *(f"- {item}" for item in remaining),
            "", "## Candidate rejection reasons", *(f"- {item}" for item in readiness),
            "", "## Blockers", *(f"- {item}" for item in blockers),
            "", "## Current status", f"- {session.status.value}",
        ]
        (iteration_dir / "candidate_report.md").write_text(
            "\n".join(lines) + "\n", encoding="utf-8"
        )

    def _transition(self, session: RefinementSession,
                    target: RefinementStatus, reason: str) -> None:
        if session.status is target:
            return
        session.status_history.append(StatusTransition(
            from_status=session.status.value, to_status=target.value,
            at=_now(), reason=reason,
        ))
        session.status, session.updated_at = target, _now()

    @contextmanager
    def _project_lock(self, session: RefinementSession):
        lock_dir = self.runs_dir / "refinement" / ".locks"
        lock_dir.mkdir(parents=True, exist_ok=True)
        name = hashlib.sha256(str(Path(session.project_path).resolve()).encode("utf-8")).hexdigest()
        path = lock_dir / f"{name}.lock"
        handle = path.open("a+b")
        try:
            handle.seek(0)
            if handle.read(1) == b"":
                handle.write(b"0"); handle.flush()
            handle.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            handle.close()
            raise RefinementError(
                "Another refinement iteration is already editing this project."
            ) from exc
        try:
            yield
        finally:
            try:
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
            handle.close()

    def _save(self, session: RefinementSession) -> None:
        session.updated_at = _now()
        _atomic_json(self.session_dir(session.session_id) / "session.json",
                     session.model_dump(mode="json"))

    @staticmethod
    def _new_session_id(project: Path) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", project.name.lower()).strip("-") or "site"
        return f"{slug}-{uuid.uuid4().hex[:10]}"
