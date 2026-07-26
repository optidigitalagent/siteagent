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
import signal
import shlex
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
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
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from site_agent.config import settings
from site_agent.critic import TechnicalInspector
from site_agent.models import TechnicalGate
from site_agent.studio import CodexStudioRunner


REFINEMENT_MODE = "site_refinement"
TARGET_WIDTHS = (1440, 1024, 768, 390, 360)
ReferenceProperty = Literal[
    "composition", "grid", "typography", "scale", "spacing", "shape",
    "color", "density", "photography", "interaction", "animation",
    "responsive_behavior",
]
_REFERENCE_PROPERTIES = {
    "composition", "grid", "typography", "scale", "spacing", "shape",
    "color", "density", "photography", "interaction", "animation",
    "responsive_behavior",
}
_REFERENCE_PROPERTY_ALIASES = {
    "component_shape": "shape",
    "responsive": "responsive_behavior",
    "responsive_behaviour": "responsive_behavior",
    "colour": "color",
}


def _normalize_reference_property(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    normalized = re.sub(r"[\s-]+", "_", value.strip().casefold())
    return _REFERENCE_PROPERTY_ALIASES.get(normalized, normalized)


def _normalize_reference_properties(values: Any) -> Any:
    if values is None:
        return []
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, (list, tuple, set)):
        return values
    normalized: list[Any] = []
    for value in values:
        item = _normalize_reference_property(value)
        if item == "" or item in normalized:
            continue
        normalized.append(item)
    return normalized


def _migrate_reference_property_payload(value: Any) -> Any:
    """Load pre-component/property reference records without widening them."""
    if not isinstance(value, dict):
        return value
    payload = dict(value)
    if "target_properties_explicit" not in payload:
        payload["target_properties_explicit"] = "target_properties" in payload
    if "target_properties" in payload:
        explicit = _normalize_reference_properties(payload.get("target_properties"))
    else:
        legacy = _normalize_reference_properties(payload.get("transfer"))
        explicit = [item for item in legacy if item in _REFERENCE_PROPERTIES]
    payload["target_properties"] = explicit
    return payload


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class RefinementError(RuntimeError):
    pass


class RefinementRuntimeError(RefinementError):
    """Controlled fail-closed error from the executor/reviewer runtime."""

    def __init__(self, role: str, reason: str, *, evidence_path: str = "") -> None:
        self.role = role
        self.reason = reason
        self.evidence_path = evidence_path
        super().__init__(f"Refinement {role} runtime failed: {reason}")


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
    target_component: str = ""
    target_locator: str = ""
    target_properties: list[ReferenceProperty] = Field(default_factory=list)
    target_properties_explicit: bool = False
    match_kind: Literal["exact", "visual_direction"] = "visual_direction"
    interpretation: str = ""
    transfer: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_properties(cls, value: Any) -> Any:
        return _migrate_reference_property_payload(value)

    @field_validator("target_properties", mode="before")
    @classmethod
    def normalize_properties(cls, value: Any) -> Any:
        return _normalize_reference_properties(value)


class RefinementAttachment(BaseModel):
    id: str
    original_name: str
    stored_path: str
    sha256: str
    kind: str
    target_page: str = ""
    target_section: str = ""
    target_component: str = ""
    target_locator: str = ""
    target_properties: list[ReferenceProperty] = Field(default_factory=list)
    target_properties_explicit: bool = False
    match_kind: str = "visual_direction"
    interpretation: str = ""
    transfer: list[str] = Field(default_factory=list)
    extracted_text: str = ""
    added_at: str

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_properties(cls, value: Any) -> Any:
        return _migrate_reference_property_payload(value)

    @field_validator("target_properties", mode="before")
    @classmethod
    def normalize_properties(cls, value: Any) -> Any:
        return _normalize_reference_properties(value)


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
    current_change_plan_sha256: str = ""
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
    session_id: str = ""
    iteration: int = -1
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
    reference_scope_evidence: list["ReferenceScopeEvidence"] = Field(default_factory=list)
    requirement_change_evidence: list["RequirementChangeEvidence"] = Field(
        default_factory=list
    )


class FunctionalScenarioEvidence(BaseModel):
    kind: Literal["navigation", "cta", "form", "menu", "accordion", "modal", "slider", "map", "video", "other"]
    target: str
    states_checked: list[str] = Field(default_factory=list)
    passed: bool
    evidence: str


class RequirementSourceVerification(BaseModel):
    changed_file: str
    target_locator: str
    before: str
    after: str
    verifiable: bool = False

    @model_validator(mode="after")
    def normalize_evidence(self) -> "RequirementSourceVerification":
        self.changed_file = self.changed_file.strip().replace("\\", "/")
        self.target_locator = " ".join(self.target_locator.split())
        return self


class RequirementChangeEvidence(BaseModel):
    requirement_id: str
    changed_files: list[str] = Field(default_factory=list)
    scope: list[str] = Field(default_factory=list)
    source_verifications: list[RequirementSourceVerification] = Field(
        default_factory=list
    )
    evidence: str

    @model_validator(mode="after")
    def normalize_evidence(self) -> "RequirementChangeEvidence":
        self.requirement_id = " ".join(self.requirement_id.split())
        self.changed_files = list(dict.fromkeys(
            normalized for value in self.changed_files
            if (normalized := value.strip().replace("\\", "/"))
        ))
        self.scope = list(dict.fromkeys(
            normalized for value in self.scope
            if (normalized := " ".join(value.split()))
        ))
        self.evidence = " ".join(self.evidence.split())
        return self


class ReferencePropertyVerification(BaseModel):
    property: ReferenceProperty
    target_component: str
    changed_files: list[str] = Field(default_factory=list)
    target_locator: str
    before: str
    after: str
    verifiable: bool = False

    @field_validator("property", mode="before")
    @classmethod
    def normalize_property(cls, value: Any) -> Any:
        return _normalize_reference_property(value)

    @model_validator(mode="after")
    def normalize_evidence(self) -> "ReferencePropertyVerification":
        self.target_component = " ".join(self.target_component.split())
        self.target_locator = " ".join(self.target_locator.split())
        self.changed_files = list(dict.fromkeys(
            normalized for value in self.changed_files
            if (normalized := value.strip().replace("\\", "/"))
        ))
        return self


class ReferenceScopeEvidence(BaseModel):
    attachment_id: str
    target_page: str
    target_section: str
    target_component: str
    target_locator: str
    properties: list[ReferenceProperty]
    changed_files: list[str] = Field(default_factory=list)
    evidence: str
    property_verifications: list[ReferencePropertyVerification] = Field(
        default_factory=list
    )
    scope_isolated: bool = False

    @field_validator("properties", mode="before")
    @classmethod
    def normalize_properties(cls, value: Any) -> Any:
        return _normalize_reference_properties(value)

    @field_validator("changed_files", mode="after")
    @classmethod
    def normalize_changed_files(cls, values: list[str]) -> list[str]:
        return list(dict.fromkeys(
            normalized for value in values
            if (normalized := value.strip().replace("\\", "/"))
        ))


RefinementImplementationResult.model_rebuild()


class RefinementReviewIssue(BaseModel):
    severity: Literal["p0", "p1", "p2", "p3"]
    area: str
    problem: str
    required_fix: str


class RefinementReviewResult(BaseModel):
    session_id: str = ""
    iteration: int = -1
    decision: Literal["accept", "revise", "blocked"]
    visual_qa_passed: bool
    responsive_qa_passed: bool
    requirements_match: bool
    reference_comparison_passed: bool
    functional_qa_passed: bool
    content_qa_passed: bool
    animation_qa_passed: bool
    reference_property_scope_verified: bool = True
    issues: list[RefinementReviewIssue] = Field(default_factory=list)
    remaining_differences: list[str] = Field(default_factory=list)
    summary: str

    @model_validator(mode="after")
    def enforce_acceptance_invariants(self) -> "RefinementReviewResult":
        blocking = any(issue.severity in {"p0", "p1"} for issue in self.issues)
        mandatory_gates = (
            self.visual_qa_passed, self.responsive_qa_passed,
            self.requirements_match, self.reference_comparison_passed,
            self.functional_qa_passed, self.content_qa_passed,
            self.animation_qa_passed, self.reference_property_scope_verified,
        )
        if self.decision == "accept" and (
                not all(mandatory_gates) or blocking
                or bool(_normalized_nonempty(self.remaining_differences))):
            self.decision = "revise"
        return self


class ReferenceAnalysisResult(BaseModel):
    target_page: str
    target_section: str
    target_component: str
    target_locator: str
    target_properties: list[ReferenceProperty] = Field(default_factory=list)
    match_kind: Literal["exact", "visual_direction"]
    interpretation: str
    transfer: list[str]
    ambiguous: bool = False
    blocker: str = ""

    @field_validator("target_properties", mode="before")
    @classmethod
    def normalize_properties(cls, value: Any) -> Any:
        return _normalize_reference_properties(value)

    @model_validator(mode="after")
    def reject_broad_scope(self) -> "ReferenceAnalysisResult":
        self.target_page = " ".join(self.target_page.split())
        self.target_section = " ".join(self.target_section.split())
        self.target_component = " ".join(self.target_component.split())
        self.target_locator = " ".join(self.target_locator.split())
        self.interpretation = " ".join(self.interpretation.split())
        self.target_properties = list(dict.fromkeys(self.target_properties))
        if self.ambiguous:
            if not self.blocker.strip():
                raise ValueError("An ambiguous reference mapping requires a blocker reason.")
            return self
        if not all((
            _specific_reference_scope(self.target_page),
            _specific_reference_scope(self.target_section),
            _specific_reference_scope(self.target_component),
            _specific_reference_scope(self.target_locator),
            self.interpretation,
            self.target_properties,
        )):
            raise ValueError(
                "Reference scope must identify a specific page, section, component, "
                "target locator, property allowlist, and interpretation."
            )
        return self


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
        self.timeout = (
            settings.refinement_executor_timeout_seconds
            if timeout is None else timeout
        )

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
For every visual reference, record reference_scope_evidence with the exact
attachment ID, page, section, component and property allowlist from the session.
Use the mapping's exact target_locator in every property verification.
Do not report a broader target or additional transferred property. Include one
structured property_verification per transferred property, bound to the exact
component, changed file, target locator, and distinct before/after evidence.
Set scope_isolated=true only when the changed region is verifiably free of other
material changes. Attribute every other changed file to a concrete active user
requirement in requirement_change_evidence, copy that requirement's exact scope,
and include exact source before/after replacement evidence whenever a requirement
also changes a reference-touched file. Never use a reference as authority for an
unrelated change.

Accumulated session contract:
{session.model_dump_json(indent=2)}
""".strip()
        return _invoke_codex_model(
            project_dir=Path(session.project_path), prompt=prompt,
            schema=RefinementImplementationResult,
            output_dir=iteration_dir / "implementation", sandbox="workspace-write",
            images=attachments, timeout=self.timeout,
            session=session, role="executor",
        )


class CodexRefinementReviewer:
    """Independent screenshot-led critic that cannot edit the project."""

    def __init__(self, *, timeout: int | None = None) -> None:
        self.timeout = (
            settings.refinement_reviewer_timeout_seconds
            if timeout is None else timeout
        )

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
Set reference_property_scope_verified=true only after the structured property
evidence and rendered/source comparison prove that every reference-driven
change stayed inside its component and property allowlist.

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
            session=session, role="reviewer",
        )


def load_refinement_request(path: Path) -> RefinementRequest:
    try:
        return RefinementRequest.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError, json.JSONDecodeError) as exc:
        raise RefinementError(f"Invalid refinement input JSON: {path}") from exc


def _invoke_codex_model(*, project_dir: Path, prompt: str, schema: type[BaseModel],
                        output_dir: Path, sandbox: Literal["workspace-write", "read-only"],
                        images: list[Path], timeout: int,
                        session: RefinementSession | None = None,
                        role: Literal["executor", "reviewer"] | None = None) -> Any:
    if session is not None and role is not None:
        return _invoke_refinement_codex_runtime(
            project_dir=project_dir,
            prompt=prompt,
            schema=schema,
            output_dir=output_dir,
            sandbox=sandbox,
            images=images,
            timeout=timeout,
            session=session,
            role=role,
        )

    # Reference analysis is intentionally outside the executor/reviewer
    # lifecycle hardened by this checkpoint. Preserve its existing behavior.
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


def _atomic_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _secret_environment_values() -> list[str]:
    markers = ("TOKEN", "SECRET", "PASSWORD", "PASSWD", "API_KEY", "PRIVATE_KEY", "CREDENTIAL")
    return sorted(
        {
            value for key, value in os.environ.items()
            if value and len(value) >= 4 and any(marker in key.upper() for marker in markers)
        },
        key=len,
        reverse=True,
    )


def _redact_runtime_text(value: str) -> str:
    redacted = value
    for secret in _secret_environment_values():
        redacted = redacted.replace(secret, "[REDACTED]")
    redacted = re.sub(
        r"(?i)(token|secret|password|passwd|api[_-]?key|credential)(\s*[=:]\s*)[^\s,;]+",
        r"\1\2[REDACTED]",
        redacted,
    )
    return redacted


def _redacted_stream_bytes(raw: bytes, maximum: int) -> bytes:
    text = raw[:maximum].decode("utf-8", errors="replace")
    content = _redact_runtime_text(text).encode("utf-8")
    if len(content) > maximum:
        content = content[:maximum]
    return content


def _drain_bounded_pipe(pipe: Any, maximum: int,
                        result: dict[str, tuple[bytes, bool]], key: str) -> None:
    captured = bytearray()
    truncated = False
    try:
        while True:
            chunk = pipe.read(64 * 1024)
            if not chunk:
                break
            available = max(0, maximum - len(captured))
            if available:
                captured.extend(chunk[:available])
            if len(chunk) > available:
                truncated = True
    except (OSError, ValueError):
        truncated = True
    result[key] = (_redacted_stream_bytes(bytes(captured), maximum), truncated)


def _write_prompt_pipe(pipe: Any, payload: bytes,
                       result: dict[str, str]) -> None:
    try:
        pipe.write(payload)
        pipe.flush()
        result["status"] = "completed"
    except (BrokenPipeError, OSError, ValueError) as exc:
        result["status"] = type(exc).__name__
    finally:
        try:
            pipe.close()
        except OSError:
            pass


_WINDOWS_JOB_SUPERVISOR = (
    "import os,subprocess,sys; "
    "gate=os.read(sys.stdin.fileno(),1); "
    "sys.exit(125) if gate != b'\\x00' else None; "
    "child=subprocess.Popen(sys.argv[1:]); "
    "sys.exit(child.wait())"
)


def _resolved_refinement_executable() -> tuple[str, list[str]]:
    override = settings.refinement_codex_executable.strip()
    if not override:
        native = str(_codex_sandbox_executable())
        return native, [native]
    configured = override
    located = shutil.which(configured)
    if not located:
        candidate = Path(configured).expanduser()
        if candidate.is_file():
            located = str(candidate.resolve())
    if not located:
        raise RefinementError("refinement Codex executable not found")
    resolved = str(Path(located).resolve())
    # A Python script is a convenient deterministic Codex-compatible executable
    # for tests on Windows and POSIX. Production binaries remain direct argv[0].
    if Path(resolved).suffix.lower() in {".py", ".pyw"}:
        return str(Path(sys.executable).resolve()), [str(Path(sys.executable).resolve()), resolved]
    if Path(resolved).suffix.lower() in {".cmd", ".bat"}:
        if Path(resolved).stem.lower() == "codex":
            native = str(_codex_sandbox_executable())
            return native, [native]
        raise RefinementError(
            "REFINEMENT_CODEX_EXECUTABLE must be a native executable, not a shell wrapper."
        )
    return resolved, [resolved]


def _runtime_artifact_path(path: Path, iteration_root: Path) -> str:
    # Use the lexical in-root location for evidence. Resolving a malicious
    # result symlink here would itself escape and prevent failure evidence.
    return path.absolute().relative_to(iteration_root.absolute()).as_posix()


def _posix_process_group_exists(process_group: int) -> bool:
    try:
        os.killpg(process_group, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _assign_windows_kill_job(process: subprocess.Popen[Any]) -> int:
    """Put the subprocess tree in a kill-on-close Windows Job Object."""
    import ctypes
    from ctypes import wintypes

    class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_longlong),
            ("PerJobUserTimeLimit", ctypes.c_longlong),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class IO_COUNTERS(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", ctypes.c_ulonglong),
            ("WriteOperationCount", ctypes.c_ulonglong),
            ("OtherOperationCount", ctypes.c_ulonglong),
            ("ReadTransferCount", ctypes.c_ulonglong),
            ("WriteTransferCount", ctypes.c_ulonglong),
            ("OtherTransferCount", ctypes.c_ulonglong),
        ]

    class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
            ("IoInfo", IO_COUNTERS),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.SetInformationJobObject.argtypes = [
        wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD,
    ]
    kernel32.SetInformationJobObject.restype = wintypes.BOOL
    kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        raise OSError(ctypes.get_last_error(), "CreateJobObjectW failed")
    information = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
    information.BasicLimitInformation.LimitFlags = 0x00002000  # KILL_ON_JOB_CLOSE
    if not kernel32.SetInformationJobObject(
            job, 9, ctypes.byref(information), ctypes.sizeof(information)):
        error = ctypes.get_last_error()
        kernel32.CloseHandle(job)
        raise OSError(error, "SetInformationJobObject failed")
    if not kernel32.AssignProcessToJobObject(job, wintypes.HANDLE(int(process._handle))):
        error = ctypes.get_last_error()
        kernel32.CloseHandle(job)
        raise OSError(error, "AssignProcessToJobObject failed")
    return int(job)


def _close_windows_job(job_handle: int | None) -> bool:
    if job_handle is None:
        return False
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    return bool(kernel32.CloseHandle(wintypes.HANDLE(job_handle)))


def _terminate_refinement_process_tree(
        process: subprocess.Popen[Any], graceful_timeout: int,
        *, windows_job: int | None = None) -> tuple[str, bool]:
    """Bounded best-effort tree termination with an explicit confirmation."""
    if os.name == "nt":
        taskkill_confirmed = False
        try:
            graceful = subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T"],
                capture_output=True, text=True, timeout=graceful_timeout, check=False,
            )
            taskkill_confirmed = graceful.returncode == 0
        except (OSError, subprocess.SubprocessError):
            pass
        try:
            process.wait(timeout=graceful_timeout)
        except subprocess.TimeoutExpired:
            try:
                forced = subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    capture_output=True, text=True, timeout=graceful_timeout, check=False,
                )
                taskkill_confirmed = forced.returncode == 0
            except (OSError, subprocess.SubprocessError):
                taskkill_confirmed = False
            try:
                process.wait(timeout=graceful_timeout)
            except subprocess.TimeoutExpired:
                try:
                    process.kill()
                    process.wait(timeout=graceful_timeout)
                except (OSError, subprocess.SubprocessError):
                    pass
        job_closed = _close_windows_job(windows_job)
        if process.poll() is None:
            try:
                process.wait(timeout=graceful_timeout)
            except subprocess.TimeoutExpired:
                pass
        remaining = process.poll() is None or not (taskkill_confirmed or job_closed)
        return ("confirmed" if not remaining else "unconfirmed", remaining)

    process_group = process.pid
    try:
        os.killpg(process_group, signal.SIGTERM)
    except ProcessLookupError:
        pass
    deadline = time.monotonic() + graceful_timeout
    while time.monotonic() < deadline and _posix_process_group_exists(process_group):
        time.sleep(0.05)
    if _posix_process_group_exists(process_group):
        try:
            os.killpg(process_group, signal.SIGKILL)
        except ProcessLookupError:
            pass
        deadline = time.monotonic() + graceful_timeout
        while time.monotonic() < deadline and _posix_process_group_exists(process_group):
            time.sleep(0.05)
    try:
        process.wait(timeout=graceful_timeout)
    except subprocess.TimeoutExpired:
        try:
            process.kill()
            process.wait(timeout=graceful_timeout)
        except (OSError, subprocess.SubprocessError):
            pass
    remaining = process.poll() is None or _posix_process_group_exists(process_group)
    return ("confirmed" if not remaining else "unconfirmed", remaining)


def _invoke_refinement_codex_runtime(
        *, project_dir: Path, prompt: str, schema: type[BaseModel], output_dir: Path,
        sandbox: Literal["workspace-write", "read-only"], images: list[Path],
        timeout: int, session: RefinementSession,
        role: Literal["executor", "reviewer"]) -> Any:
    def persist_setup_failure(reason: str) -> str:
        evidence_relative = ""
        try:
            iteration_root = output_dir.parent.resolve()
            output_dir.mkdir(parents=True, exist_ok=True)
            if _unsafe_project_link(output_dir) or output_dir.resolve().parent != iteration_root:
                raise OSError("runtime artifact directory is unsafe")
            stdout_path = output_dir / "stdout.log"
            stderr_path = output_dir / "stderr.log"
            evidence_path = output_dir / "runtime.json"
            for path in (stdout_path, stderr_path, evidence_path):
                if path.exists() and _unsafe_project_link(path):
                    raise OSError("runtime failure artifact path is unsafe")
            _atomic_bytes(stdout_path, b"")
            _atomic_bytes(stderr_path, b"")
            try:
                manifest = _project_manifest(
                    project_dir.resolve(), include_all=role == "reviewer"
                )
                tree_hash = manifest["tree_sha256"]
            except (OSError, RefinementError):
                tree_hash = ""
            configured = (
                settings.refinement_codex_executable.strip()
                or settings.codex_command.strip()
                or "codex"
            )
            _atomic_json(evidence_path, {
                "schema_version": 1,
                "role": role,
                "session_id": session.session_id,
                "iteration": session.iteration,
                "command_executable": _redact_runtime_text(configured),
                "command_arguments": [],
                "working_directory": str(project_dir.resolve()),
                "sandbox_mode": sandbox,
                "network_mode": "restricted",
                "started_at": _now(),
                "ended_at": _now(),
                "duration_seconds": 0.0,
                "timeout_seconds": timeout,
                "timed_out": False,
                "return_code": None,
                "stdout_artifact_path": _runtime_artifact_path(stdout_path, iteration_root),
                "stderr_artifact_path": _runtime_artifact_path(stderr_path, iteration_root),
                "stdout_sha256": _file_sha(stdout_path),
                "stderr_sha256": _file_sha(stderr_path),
                "stdout_truncated": False,
                "stderr_truncated": False,
                "result_artifact_path": _runtime_artifact_path(
                    output_dir / "result.json", iteration_root
                ),
                "result_artifact_sha256": "",
                "result_parsing_status": "setup_failed",
                "cleanup_status": "not_started",
                "detected_remaining_processes": False,
                "project_tree_hash_before": tree_hash,
                "project_tree_hash_after": tree_hash,
                "project_modified_by_reviewer": False,
                "project_manifest_diff": {"added": [], "modified": [], "deleted": []},
                "failure_reason": reason,
            })
            evidence_relative = _runtime_artifact_path(evidence_path, iteration_root)
        except (OSError, ValueError, RefinementError):
            evidence_relative = ""
        return evidence_relative

    try:
        return _invoke_refinement_codex_runtime_inner(
            project_dir=project_dir, prompt=prompt, schema=schema,
            output_dir=output_dir, sandbox=sandbox, images=images,
            timeout=timeout, session=session, role=role,
        )
    except RefinementRuntimeError as exc:
        if exc.evidence_path:
            raise
        evidence_relative = persist_setup_failure(exc.reason)
        raise RefinementRuntimeError(
            role, exc.reason, evidence_path=evidence_relative
        ) from exc
    except (OSError, ValueError, RefinementError, subprocess.SubprocessError) as exc:
        if isinstance(exc, RefinementError) and "executable not found" in str(exc).lower():
            reason = "refinement Codex executable not found"
        else:
            reason = f"runtime setup or evidence failed: {type(exc).__name__}"
        evidence_relative = persist_setup_failure(reason)
        raise RefinementRuntimeError(
            role, reason, evidence_path=evidence_relative
        ) from exc


def _invoke_refinement_codex_runtime_inner(
        *, project_dir: Path, prompt: str, schema: type[BaseModel], output_dir: Path,
        sandbox: Literal["workspace-write", "read-only"], images: list[Path],
        timeout: int, session: RefinementSession,
        role: Literal["executor", "reviewer"]) -> Any:
    """Run one Codex role and always leave bounded, redacted runtime evidence."""
    project = project_dir.resolve()
    iteration_root = output_dir.parent.resolve()
    if iteration_root == project or project in iteration_root.parents:
        raise RefinementRuntimeError(
            role, "runtime artifacts must be outside the editable project workspace"
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    if _unsafe_project_link(output_dir) or output_dir.resolve().parent != iteration_root:
        raise RefinementRuntimeError(role, "runtime artifact directory escapes the iteration root")

    schema_path = output_dir / "schema.json"
    result_path = output_dir / "result.json"
    stdout_path = output_dir / "stdout.log"
    stderr_path = output_dir / "stderr.log"
    evidence_path = output_dir / "runtime.json"
    for path in (schema_path, result_path, stdout_path, stderr_path, evidence_path):
        if path.exists() and _unsafe_project_link(path):
            raise RefinementRuntimeError(role, "runtime artifact path is a link or junction")
    # A prior interrupted attempt may not satisfy this attempt's output contract.
    result_path.unlink(missing_ok=True)
    _atomic_json(schema_path, _strict_schema(schema.model_json_schema()))

    command_executable, prefix = _resolved_refinement_executable()
    command = [*prefix, "exec", "--disable", "code_mode_host",
               "-c", "sandbox_workspace_write.network_access=false", "-C", str(project),
               "--sandbox", sandbox, "--output-schema", str(schema_path),
               "-o", str(result_path), "-"]
    for image in images:
        if image.is_file():
            command[len(prefix) + 1:len(prefix) + 1] = ["--image", str(image.resolve())]
    model = settings.refinement_codex_model.strip() or settings.codex_model.strip()
    if model:
        command[len(prefix) + 1:len(prefix) + 1] = ["-m", model]

    started_at = _now()
    started_monotonic = time.monotonic()
    timed_out = False
    return_code: int | None = None
    cleanup_status = "not_started"
    remaining_processes: bool | None = False
    parsing_status = "not_attempted"
    result_sha256 = ""
    failure_reason = ""
    typed_result: Any = None
    project_before = _project_manifest(project, include_all=role == "reviewer")
    project_after = project_before
    stdout_content = b""
    stderr_content = b""
    stdout_truncated = False
    stderr_truncated = False

    process: subprocess.Popen[Any] | None = None
    windows_job: int | None = None
    stream_results: dict[str, tuple[bytes, bool]] = {}
    stream_threads: list[threading.Thread] = []
    prompt_result: dict[str, str] = {}
    prompt_thread: threading.Thread | None = None
    try:
        launch_command = (
            [str(Path(sys.executable).resolve()), "-c", _WINDOWS_JOB_SUPERVISOR, *command]
            if os.name == "nt" else command
        )
        process = subprocess.Popen(
            launch_command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False,
            bufsize=0,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
            start_new_session=os.name != "nt",
            env=_safe_refinement_env(),
            cwd=str(project),
            shell=False,
        )
        if process.stdout is None or process.stderr is None or process.stdin is None:
            raise OSError("subprocess pipes were not created")
        stream_threads = [
            threading.Thread(
                target=_drain_bounded_pipe,
                args=(process.stdout, settings.refinement_max_stdout_bytes,
                      stream_results, "stdout"),
                daemon=True,
            ),
            threading.Thread(
                target=_drain_bounded_pipe,
                args=(process.stderr, settings.refinement_max_stderr_bytes,
                      stream_results, "stderr"),
                daemon=True,
            ),
        ]
        for thread in stream_threads:
            thread.start()
        if os.name == "nt":
            windows_job = _assign_windows_kill_job(process)
        prompt_payload = (b"\x00" if os.name == "nt" else b"") + prompt.encode("utf-8")
        prompt_thread = threading.Thread(
            target=_write_prompt_pipe,
            args=(process.stdin, prompt_payload, prompt_result),
            daemon=True,
        )
        prompt_thread.start()
        try:
            remaining_timeout = max(0.001, timeout - (time.monotonic() - started_monotonic))
            return_code = process.wait(timeout=remaining_timeout)
            if os.name == "nt":
                job_closed = _close_windows_job(windows_job)
                windows_job = None
                cleanup_status = "confirmed" if job_closed else "unconfirmed"
                remaining_processes = not job_closed
            else:
                remaining_processes = _posix_process_group_exists(process.pid)
                if remaining_processes:
                    cleanup_status, remaining_processes = _terminate_refinement_process_tree(
                        process, settings.refinement_graceful_termination_timeout_seconds
                    )
                else:
                    cleanup_status = "confirmed"
            if cleanup_status != "confirmed":
                failure_reason = "process-tree cleanup was not confirmed after process exit"
        except subprocess.TimeoutExpired:
            timed_out = True
            cleanup_status, remaining_processes = _terminate_refinement_process_tree(
                process,
                settings.refinement_graceful_termination_timeout_seconds,
                windows_job=windows_job,
            )
            windows_job = None
            return_code = process.returncode
            failure_reason = f"timeout after {timeout} seconds"
            if cleanup_status != "confirmed":
                failure_reason += "; process-tree cleanup was not confirmed"
    except FileNotFoundError:
        failure_reason = f"executable not found: {command_executable}"
        cleanup_status = "not_started"
    except (OSError, subprocess.SubprocessError) as exc:
        failure_reason = f"subprocess launch or communication failed: {type(exc).__name__}"
        if process is not None and process.poll() is None:
            cleanup_status, remaining_processes = _terminate_refinement_process_tree(
                process,
                settings.refinement_graceful_termination_timeout_seconds,
                windows_job=windows_job,
            )
            windows_job = None
        elif windows_job is not None:
            job_closed = _close_windows_job(windows_job)
            windows_job = None
            cleanup_status = "confirmed" if job_closed else "unconfirmed"
            remaining_processes = not job_closed
        return_code = process.returncode if process is not None else None
    finally:
        if windows_job is not None:
            job_closed = _close_windows_job(windows_job)
            windows_job = None
            if not job_closed:
                cleanup_status = "unconfirmed"
                remaining_processes = True
                failure_reason = failure_reason or "Windows process job cleanup was not confirmed"
        join_timeout = settings.refinement_graceful_termination_timeout_seconds
        if prompt_thread is not None:
            prompt_thread.join(timeout=join_timeout)
            if prompt_thread.is_alive() and process is not None and process.stdin is not None:
                try:
                    process.stdin.close()
                except OSError:
                    pass
                prompt_thread.join(timeout=join_timeout)
            if prompt_thread.is_alive():
                cleanup_status = "unconfirmed"
                remaining_processes = True
                failure_reason = failure_reason or "runtime prompt cleanup was not confirmed"
        for thread in stream_threads:
            thread.join(timeout=join_timeout)
        alive_threads = [thread for thread in stream_threads if thread.is_alive()]
        if alive_threads and process is not None:
            for pipe in (process.stdout, process.stderr):
                try:
                    if pipe is not None:
                        pipe.close()
                except OSError:
                    pass
            for thread in alive_threads:
                thread.join(timeout=join_timeout)
        if any(thread.is_alive() for thread in stream_threads):
            cleanup_status = "unconfirmed"
            remaining_processes = True
            failure_reason = failure_reason or "runtime stream cleanup was not confirmed"
        if process is not None:
            for pipe in (process.stdout, process.stderr):
                try:
                    if pipe is not None:
                        pipe.close()
                except OSError:
                    pass
        stdout_content, stdout_truncated = stream_results.get("stdout", (b"", False))
        stderr_content, stderr_truncated = stream_results.get("stderr", (b"", False))

    try:
        _atomic_bytes(stdout_path, stdout_content)
        _atomic_bytes(stderr_path, stderr_content)
    except OSError as exc:
        raise RefinementRuntimeError(
            role, f"runtime streams could not be persisted: {type(exc).__name__}"
        ) from exc

    try:
        project_after = _project_manifest(project, include_all=role == "reviewer")
    except RefinementError as exc:
        failure_reason = failure_reason or f"project manifest failed: {exc}"
    project_modified = project_before["tree_sha256"] != project_after["tree_sha256"]
    project_diff = _manifest_diff(project_before, project_after)

    if not failure_reason and return_code != 0:
        failure_reason = f"non-zero exit code: {return_code}"
        parsing_status = "not_attempted_nonzero_exit"
    if not failure_reason:
        try:
            if not result_path.exists():
                parsing_status = "missing"
                raise RefinementRuntimeError(role, "result artifact is missing")
            if _unsafe_project_link(result_path):
                parsing_status = "artifact_escape"
                raise RefinementRuntimeError(role, "result artifact is a link or junction")
            resolved_result = result_path.resolve()
            if resolved_result.parent != output_dir.resolve() or iteration_root not in resolved_result.parents:
                parsing_status = "artifact_escape"
                raise RefinementRuntimeError(role, "result artifact escapes the iteration root")
            if result_path.stat().st_size == 0:
                parsing_status = "empty"
                raise RefinementRuntimeError(role, "result artifact is empty")
            result_sha256 = _file_sha(result_path)
            try:
                raw_result = json.loads(result_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
                parsing_status = "malformed_json"
                raise RefinementRuntimeError(role, "result artifact contains malformed JSON") from exc
            if not isinstance(raw_result, dict):
                parsing_status = "schema_invalid"
                raise RefinementRuntimeError(role, "result artifact is not a JSON object")
            if str(raw_result.get("session_id", "")) != session.session_id:
                parsing_status = "session_mismatch"
                raise RefinementRuntimeError(
                    role, "result artifact is missing or has another session binding"
                )
            try:
                result_iteration = int(raw_result.get("iteration"))
            except (TypeError, ValueError) as exc:
                parsing_status = "iteration_mismatch"
                raise RefinementRuntimeError(
                    role, "result artifact has an invalid iteration binding"
                ) from exc
            if result_iteration != session.iteration:
                parsing_status = "iteration_mismatch"
                raise RefinementRuntimeError(
                    role, "result artifact belongs to another iteration"
                )
            try:
                typed_result = schema.model_validate(raw_result)
            except (ValidationError, ValueError, TypeError) as exc:
                parsing_status = "schema_invalid"
                raise RefinementRuntimeError(
                    role, f"result artifact failed {schema.__name__} validation"
                ) from exc
            parsing_status = "validated"
        except RefinementRuntimeError as exc:
            failure_reason = exc.reason

    if role == "reviewer" and project_modified:
        failure_reason = "reviewer modified the project"
        parsing_status = parsing_status if parsing_status != "validated" else "validated_but_project_modified"

    ended_at = _now()
    evidence = {
        "schema_version": 1,
        "role": role,
        "session_id": session.session_id,
        "iteration": session.iteration,
        "command_executable": _redact_runtime_text(command[0]),
        "command_arguments": [_redact_runtime_text(value) for value in command[1:]],
        "working_directory": str(project),
        "sandbox_mode": sandbox,
        "network_mode": "restricted",
        "started_at": started_at,
        "ended_at": ended_at,
        "duration_seconds": round(time.monotonic() - started_monotonic, 6),
        "timeout_seconds": timeout,
        "timed_out": timed_out,
        "return_code": return_code,
        "stdout_artifact_path": _runtime_artifact_path(stdout_path, iteration_root),
        "stderr_artifact_path": _runtime_artifact_path(stderr_path, iteration_root),
        "stdout_sha256": _file_sha(stdout_path),
        "stderr_sha256": _file_sha(stderr_path),
        "stdout_truncated": stdout_truncated,
        "stderr_truncated": stderr_truncated,
        "result_artifact_path": _runtime_artifact_path(result_path, iteration_root),
        "result_artifact_sha256": result_sha256,
        "result_parsing_status": parsing_status,
        "cleanup_status": cleanup_status,
        "detected_remaining_processes": remaining_processes,
        "project_tree_hash_before": project_before["tree_sha256"],
        "project_tree_hash_after": project_after["tree_sha256"],
        "project_modified_by_reviewer": role == "reviewer" and project_modified,
        "project_manifest_diff": project_diff,
        "failure_reason": failure_reason,
    }
    try:
        _atomic_json(evidence_path, evidence)
    except OSError as exc:
        raise RefinementRuntimeError(
            role, f"runtime evidence could not be persisted: {type(exc).__name__}"
        ) from exc
    if failure_reason:
        raise RefinementRuntimeError(
            role,
            failure_reason,
            evidence_path=_runtime_artifact_path(evidence_path, iteration_root),
        )
    return typed_result


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


def _payload_sha(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _normalized_nonempty(values: list[str]) -> list[str]:
    return _unique([" ".join(value.split()) for value in values if value and value.strip()])


def _scope_locators(values: list[str]) -> set[str]:
    locators: set[str] = set()
    for value in _normalized_nonempty(values):
        _, separator, fragment = value.partition("#")
        if separator and fragment:
            locators.add("#" + fragment.strip())
        elif value.startswith(("#", ".")):
            locators.add(value)
    return locators


_BROAD_REFERENCE_SCOPE = {
    "*", "all", "global", "site", "sitewide", "whole page", "entire page",
    "whole site", "entire site", "all pages", "every page", "any page",
    "all sections", "every section", "any section", "all components",
    "every component", "any component", "site wide", "whole component",
    "entire component", "everything", "body", "html", ":root", "document",
    "window", "main", "header", "footer",
}


def _specific_reference_scope(value: str) -> bool:
    normalized = " ".join(re.sub(r"[_-]+", " ", value).split()).casefold()
    tokens = set(normalized.split())
    broad_tokens = {
        "all", "every", "any", "whole", "entire", "global", "globally",
        "everything", "sitewide", "pagewide", "websitewide",
    }
    broad_full = "full" in tokens and bool(tokens & {"site", "page", "website"})
    global_selector = bool(re.match(
        r"^(?:body|html|:root)(?:\b|[#.:\[])", normalized
    ))
    return bool(normalized) and normalized not in _BROAD_REFERENCE_SCOPE \
        and not bool(tokens & broad_tokens) and not broad_full and not global_selector


def _canonical_locator_identity(locator: str) -> str:
    """Return a conservative component identity for an id/class locator."""
    normalized = " ".join(locator.split())
    selector_tokens = re.sub(r"\[[^\]]*\]", "", normalized)
    id_match = re.search(r"#([A-Za-z][\w-]*)", selector_tokens)
    if not id_match:
        id_match = re.search(
            r"(?:^|[\s\[])id\s*=\s*[\"']?([A-Za-z][\w-]*)[\"']?\]?",
            normalized, flags=re.IGNORECASE,
        )
    if id_match:
        return "id:" + id_match.group(1).casefold()
    class_match = re.search(r"\.([A-Za-z][\w-]*)", selector_tokens)
    if class_match:
        return "class:" + class_match.group(1).casefold()
    return ""


def _merge_reference_analysis_without_widening(
        attachment: RefinementAttachment,
        analysis: ReferenceAnalysisResult) -> tuple[RefinementAttachment | None, list[str]]:
    """Fill legacy gaps while preserving every explicit user scope boundary."""
    conflicts: list[str] = []
    for field in ("target_page", "target_section", "target_component", "target_locator"):
        explicit = " ".join(str(getattr(attachment, field)).split())
        proposed = " ".join(str(getattr(analysis, field)).split())
        if explicit and explicit.casefold() != proposed.casefold():
            conflicts.append(field)
    explicit_properties = set(attachment.target_properties)
    proposed_properties = set(analysis.target_properties)
    if (
        attachment.target_properties_explicit
        and not explicit_properties
        and proposed_properties
    ) or (explicit_properties and not proposed_properties.issubset(explicit_properties)):
        conflicts.append("target_properties")
    if conflicts:
        return None, conflicts

    merged = attachment.model_copy(deep=True)
    for field in ("target_page", "target_section", "target_component", "target_locator"):
        if not str(getattr(merged, field)).strip():
            setattr(merged, field, getattr(analysis, field))
    if not merged.target_properties and not merged.target_properties_explicit:
        merged.target_properties = list(analysis.target_properties)
    if not merged.interpretation.strip():
        merged.interpretation = analysis.interpretation
    if not merged.transfer:
        merged.transfer = list(analysis.transfer)
    return merged, []


def _reference_scope_rejection_reasons(
        session: RefinementSession,
        implementation: RefinementImplementationResult | None = None) -> list[str]:
    """Validate exact reference boundaries independently of model self-ratings."""
    reasons: list[str] = []
    mappings = [
        item for item in session.attachments
        if item.kind in {"reference", "screenshot"}
    ]
    explicit_page_sections: list[tuple[str, str]] = []
    for value in session.scope:
        page, separator, section = value.partition("#")
        if separator and page.strip() and section.strip():
            explicit_page_sections.append((page.strip().casefold(), section.strip().casefold()))

    evidence_by_id: dict[str, list[ReferenceScopeEvidence]] = {}
    if implementation is not None:
        for item in implementation.reference_scope_evidence:
            evidence_by_id.setdefault(item.attachment_id, []).append(item)

    mapping_ids = {item.id for item in mappings}
    for attachment in mappings:
        missing = [
            label for label, value in (
                ("page", attachment.target_page),
                ("section", attachment.target_section),
                ("component", attachment.target_component),
                ("target locator", attachment.target_locator),
                ("interpretation", attachment.interpretation),
            ) if not _specific_reference_scope(value)
        ]
        if missing:
            reasons.append(
                f"Reference {attachment.id} lacks a specific " + ", ".join(missing) + "."
            )
        properties = list(dict.fromkeys(attachment.target_properties))
        if not properties:
            reasons.append(f"Reference {attachment.id} has no property-level transfer scope.")
        elif len(properties) != len(attachment.target_properties):
            reasons.append(f"Reference {attachment.id} repeats property-level scope values.")
        if explicit_page_sections and _specific_reference_scope(attachment.target_page) \
                and _specific_reference_scope(attachment.target_section):
            target = (
                attachment.target_page.strip().casefold(),
                attachment.target_section.strip().casefold(),
            )
            if target not in explicit_page_sections:
                reasons.append(
                    f"Reference {attachment.id} page/section scope is outside the requested scope."
                )
            else:
                expected_locator = _canonical_locator_identity("#" + target[1])
                actual_locator = _canonical_locator_identity(attachment.target_locator)
                if not actual_locator or actual_locator != expected_locator:
                    reasons.append(
                        f"Reference {attachment.id} target locator does not match "
                        "its requested page/section scope."
                    )
        if implementation is None:
            continue
        evidence = evidence_by_id.get(attachment.id, [])
        if len(evidence) != 1:
            reasons.append(
                f"Reference {attachment.id} requires exactly one implementation scope record."
            )
            continue
        record = evidence[0]
        if (
            record.target_page.strip().casefold() != attachment.target_page.strip().casefold()
            or record.target_section.strip().casefold()
            != attachment.target_section.strip().casefold()
            or record.target_component.strip().casefold()
            != attachment.target_component.strip().casefold()
            or record.target_locator.strip().casefold()
            != attachment.target_locator.strip().casefold()
            or set(record.properties) != set(properties)
        ):
            reasons.append(
                f"Reference {attachment.id} implementation scope does not exactly match its mapping."
            )
        if len(set(record.properties)) != len(record.properties):
            reasons.append(
                f"Reference {attachment.id} implementation repeats property scope values."
            )
        if not record.changed_files or not record.evidence.strip():
            reasons.append(
                f"Reference {attachment.id} implementation scope evidence is incomplete."
            )
        elif not set(record.changed_files).issubset(set(implementation.changed_files)):
            reasons.append(
                f"Reference {attachment.id} scope evidence names an unrecorded changed file."
            )
        verifications_by_property: dict[str, list[ReferencePropertyVerification]] = {}
        verified_changed_files: set[str] = set()
        for verification in record.property_verifications:
            verifications_by_property.setdefault(verification.property, []).append(verification)
            verified_changed_files.update(verification.changed_files)
        if set(verifications_by_property) != set(properties) or any(
                len(items) != 1 for items in verifications_by_property.values()):
            reasons.append(
                f"Reference {attachment.id} lacks exact per-property verification coverage."
            )
        if verified_changed_files != set(record.changed_files):
            reasons.append(
                f"Reference {attachment.id} lacks exact changed-file verification coverage."
            )
        for property_name, verifications in verifications_by_property.items():
            for verification in verifications:
                if property_name not in properties:
                    reasons.append(
                        f"Reference {attachment.id} verifies a property outside its allowlist."
                    )
                if (
                    not verification.verifiable
                    or not _specific_reference_scope(verification.target_component)
                    or verification.target_component.strip().casefold()
                    != attachment.target_component.strip().casefold()
                    or verification.target_locator.strip().casefold()
                    != attachment.target_locator.strip().casefold()
                    or not verification.changed_files
                    or not verification.target_locator.strip()
                    or not verification.before.strip()
                    or not verification.after.strip()
                    or verification.before == verification.after
                ):
                    reasons.append(
                        f"Reference {attachment.id} property {property_name!r} "
                        "has unverifiable change evidence."
                    )
                elif not set(verification.changed_files).issubset(
                        set(record.changed_files)):
                    reasons.append(
                        f"Reference {attachment.id} property verification escapes "
                        "its recorded changed files."
                    )
        if not record.scope_isolated:
            reasons.append(
                f"Reference {attachment.id} property changes were not proven isolated "
                "from out-of-scope material changes."
            )
    if implementation is not None:
        for attachment_id in evidence_by_id.keys() - mapping_ids:
            reasons.append(
                f"Implementation reported scope for unknown reference {attachment_id}."
            )
    return _unique(reasons)


def _requirement_change_rejection_reasons(
        session: RefinementSession,
        implementation: RefinementImplementationResult,
        *, authorized_requirement_ids: set[str] | None = None) -> list[str]:
    """Require every computed file change to have a user-authorized cause."""
    reasons: list[str] = []
    changed_files = set(implementation.changed_files)
    known_requirements = {item.id: item for item in session.requirements}
    if authorized_requirement_ids is None:
        reasons.append(
            "Requirement change attribution cannot be verified without the current change plan."
        )
        authorized_requirement_ids = set()
    attributed_files: set[str] = set()
    for record in implementation.reference_scope_evidence:
        attributed_files.update(record.changed_files)
    for record in implementation.requirement_change_evidence:
        requirement = known_requirements.get(record.requirement_id)
        if requirement is None:
            reasons.append(
                f"Change attribution names unknown requirement {record.requirement_id!r}."
            )
        elif requirement.state not in {RequirementState.ACTIVE, RequirementState.COMPLETED}:
            reasons.append(
                f"Change attribution uses non-authorizing requirement "
                f"{record.requirement_id!r} in state {requirement.state.value!r}."
            )
        if (
            record.requirement_id not in authorized_requirement_ids
            or record.requirement_id not in implementation.completed_requirement_ids
        ):
            reasons.append(
                f"Change attribution uses requirement {record.requirement_id!r} "
                "outside the current implementation plan."
            )
        if requirement is not None:
            expected_scope = set(_normalized_nonempty(requirement.scope))
            actual_scope = set(_normalized_nonempty(record.scope))
            if expected_scope and actual_scope != expected_scope:
                reasons.append(
                    f"Requirement {record.requirement_id!r} change attribution does "
                    "not match its recorded scope."
                )
            expected_locators = _scope_locators(requirement.scope)
        else:
            expected_locators = set()
        if not record.changed_files or not record.evidence.strip():
            reasons.append(
                f"Requirement {record.requirement_id!r} change attribution is incomplete."
            )
        elif not set(record.changed_files).issubset(changed_files):
            reasons.append(
                f"Requirement {record.requirement_id!r} attribution names an "
                "unrecorded changed file."
            )
        else:
            attributed_files.update(record.changed_files)
        for verification in record.source_verifications:
            if (
                not verification.verifiable
                or not verification.changed_file
                or verification.changed_file not in record.changed_files
                or not verification.target_locator
                or not verification.before
                or not verification.after
                or verification.before == verification.after
            ):
                reasons.append(
                    f"Requirement {record.requirement_id!r} has unverifiable "
                    "source-change evidence."
                )
            if expected_locators and verification.target_locator not in expected_locators:
                reasons.append(
                    f"Requirement {record.requirement_id!r} source locator does not "
                    "match its recorded scope."
                )
    unexplained = sorted(changed_files - attributed_files)
    if unexplained:
        reasons.append(
            "Computed changes lack reference or requirement attribution: "
            + ", ".join(unexplained) + "."
        )
    return _unique(reasons)


def _planned_requirement_ids(
        snapshot_dir: Path | None,
        session: RefinementSession) -> set[str] | None:
    if snapshot_dir is None:
        return None
    try:
        plan = json.loads(
            (snapshot_dir.parent / "change_plan.json").read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        return set()
    if (
        plan.get("schema_version") != 2
        or plan.get("session_id") != session.session_id
        or plan.get("project_id") != session.project_id
        or plan.get("iteration") != session.iteration
        or plan.get("requirements_authority_sha256")
        != _requirement_authority_checksum(session.requirements)
        or not session.current_change_plan_sha256
        or _payload_sha(plan) != session.current_change_plan_sha256
    ):
        return set()
    return {
        str(item.get("id", "")) for item in plan.get("active_requirements", [])
        if isinstance(item, dict) and item.get("id")
    }


def _inferred_css_reference_properties(before: str, after: str) -> set[str]:
    """Conservatively classify changed CSS declarations in one exact hunk."""
    declaration = re.compile(r"(?P<name>--[\w-]+|[A-Za-z][\w-]*)\s*:\s*(?P<value>[^;{}]+)")

    def isolated_rule(source: str) -> bool:
        if "<" in source or ">" in source:
            return False
        rule = re.fullmatch(r"\s*([^{}]+)\{([^{}]*)\}\s*", source, re.DOTALL)
        if not rule:
            return False
        residue = declaration.sub("", rule.group(2))
        residue = re.sub(r"/\*.*?\*/", "", residue, flags=re.DOTALL)
        return not residue.replace(";", "").strip()

    if not isolated_rule(before) or not isolated_rule(after):
        return {"unverifiable"}

    def values(source: str) -> dict[str, list[str]]:
        result: dict[str, list[str]] = {}
        for match in declaration.finditer(source):
            result.setdefault(match.group("name").casefold(), []).append(
                " ".join(match.group("value").split())
            )
        return result

    before_values, after_values = values(before), values(after)
    changed = {
        name for name in before_values.keys() | after_values.keys()
        if before_values.get(name) != after_values.get(name)
    }
    inferred: set[str] = set()
    for name in changed:
        if name.startswith("--"):
            inferred.add("color" if "color" in name or "colour" in name else "unverifiable")
            if any(
                marker in value.casefold()
                for value in before_values.get(name, []) + after_values.get(name, [])
                for marker in ("url(", "image-set(", "cross-fade(")
            ):
                inferred.add("photography")
        elif name in {"color", "background", "background-color", "fill", "stroke",
                      "border-color", "outline-color", "box-shadow", "text-shadow"}:
            inferred.add("color")
            if name == "background" and any(
                marker in value.casefold()
                for value in before_values.get(name, []) + after_values.get(name, [])
                for marker in ("url(", "image-set(", "cross-fade(")
            ):
                inferred.add("photography")
        elif name.startswith("grid-"):
            inferred.update({"grid", "composition"})
        elif name in {"display", "position", "inset", "top", "right", "bottom", "left",
                      "order", "place-items", "align-items", "justify-content",
                      "flex", "flex-flow", "flex-direction", "flex-wrap"}:
            inferred.add("composition")
        elif name in {"gap", "row-gap", "column-gap", "margin", "margin-top",
                      "margin-right", "margin-bottom", "margin-left", "padding",
                      "padding-top", "padding-right", "padding-bottom", "padding-left"}:
            inferred.add("spacing")
        elif name in {"font-size", "line-height", "width", "height", "min-width",
                      "min-height", "max-width", "max-height"}:
            inferred.add("scale")
        elif name == "transform":
            transform_functions = {
                function.casefold()
                for value in before_values.get(name, []) + after_values.get(name, [])
                for function in re.findall(r"([A-Za-z][\w-]*)\s*\(", value)
            }
            for function in transform_functions:
                if function.startswith("scale"):
                    inferred.add("scale")
                elif function.startswith("translate"):
                    inferred.add("composition")
                else:
                    inferred.add("unverifiable")
            if not transform_functions:
                inferred.add("unverifiable")
        elif name.startswith("font") or name in {"letter-spacing", "text-transform",
                                                  "text-align"}:
            inferred.add("typography")
        elif name in {"border-radius", "clip-path"}:
            inferred.add("shape")
        elif name.startswith("animation") or name in {"transition", "transition-property",
                                                       "transition-duration"}:
            inferred.add("animation")
        elif name in {"cursor", "pointer-events", "touch-action", "scroll-behavior"}:
            inferred.add("interaction")
        elif name.startswith("object-") or name in {"filter", "mix-blend-mode",
                                                     "background-position", "background-size"}:
            inferred.add("photography")
        else:
            inferred.add("unverifiable")
    if before != after and not inferred:
        inferred.add("unverifiable")
    return inferred


def _source_replacement_targets_locator(before: str, after: str, locator: str) -> bool:
    """Reject broad/multi-selector hunks masquerading as component evidence."""
    locator_identity = _canonical_locator_identity(locator)
    if (not locator_identity or not _specific_reference_scope(locator)
            or len(before) > 4096 or len(after) > 4096):
        return False
    if locator not in before or locator not in after:
        return False
    if "{" in before or "{" in after:
        selector_pattern = re.compile(r"(?:^|})\s*([^{}]+)\{")
        selectors = selector_pattern.findall(before) + selector_pattern.findall(after)
        if not selectors:
            return False
        for selector in selectors:
            normalized = " ".join(selector.split())
            selector_without_attributes = re.sub(r"\[[^\]]*\]", "", normalized)
            if (
                "," in normalized
                or re.search(r"[>+~]", selector_without_attributes)
                or " " in selector_without_attributes
                or _canonical_locator_identity(normalized) != locator_identity
            ):
                return False
    return True


def _reference_source_verification_reasons(
        session: RefinementSession,
        implementation: RefinementImplementationResult,
        snapshot_dir: Path | None) -> list[str]:
    """Bind property assertions to exact UTF-8 source before/after evidence."""
    mappings = {
        item.id for item in session.attachments
        if item.kind in {"reference", "screenshot"}
    }
    if not mappings:
        return []
    if snapshot_dir is None:
        return ["Reference property verification requires the pre-change snapshot."]
    snapshot_root = snapshot_dir.resolve()
    project_root = Path(session.project_path).resolve()
    reasons: list[str] = []
    reference_changed_files: set[str] = set()
    for record in implementation.reference_scope_evidence:
        if record.attachment_id not in mappings:
            continue
        for verification in record.property_verifications:
            for changed_file in verification.changed_files:
                reference_changed_files.add(changed_file)
                if changed_file.startswith("deleted:"):
                    reasons.append(
                        f"Reference {record.attachment_id} property "
                        f"{verification.property!r} cannot verify a deleted source file."
                    )
                    continue
                relative = Path(changed_file)
                before_path = (snapshot_root / relative).resolve()
                after_path = (project_root / relative).resolve()
                if (
                    relative.is_absolute()
                    or (before_path != snapshot_root and snapshot_root not in before_path.parents)
                    or (after_path != project_root and project_root not in after_path.parents)
                ):
                    reasons.append(
                        f"Reference {record.attachment_id} property verification escapes "
                        "the project or recovery snapshot."
                    )
                    continue
                try:
                    before_source = before_path.read_text(encoding="utf-8")
                    after_source = after_path.read_text(encoding="utf-8")
                except (OSError, UnicodeError):
                    reasons.append(
                        f"Reference {record.attachment_id} property "
                        f"{verification.property!r} is not verifiable in UTF-8 source."
                    )
                    continue
                if (
                    before_source == after_source
                    or verification.target_locator not in before_source
                    or verification.target_locator not in after_source
                    or verification.before not in before_source
                    or verification.after not in after_source
                    or not _source_replacement_targets_locator(
                        verification.before, verification.after,
                        verification.target_locator,
                    )
                ):
                    reasons.append(
                        f"Reference {record.attachment_id} property "
                        f"{verification.property!r} before/after evidence does not "
                        "match the computed source change."
                    )
    for changed_file in sorted(reference_changed_files):
        if changed_file.startswith("deleted:"):
            continue
        relative = Path(changed_file)
        before_path = (snapshot_root / relative).resolve()
        after_path = (project_root / relative).resolve()
        try:
            before_source = before_path.read_text(encoding="utf-8")
            after_source = after_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue  # The specific unreadable-source reason is recorded above.
        replacements: list[tuple[str, str, str]] = []
        reference_properties: dict[tuple[str, str, str], set[str]] = {}
        for record in implementation.reference_scope_evidence:
            for verification in record.property_verifications:
                if changed_file in verification.changed_files:
                    replacement = (
                        verification.before, verification.after,
                        verification.target_locator,
                    )
                    replacements.append(replacement)
                    reference_properties.setdefault(replacement, set()).add(
                        verification.property
                    )
        for record in implementation.requirement_change_evidence:
            for verification in record.source_verifications:
                if verification.changed_file == changed_file:
                    replacements.append((
                        verification.before, verification.after,
                        verification.target_locator,
                    ))
        working = before_source
        for before, after, locator in list(dict.fromkeys(replacements)):
            if (
                not before or not after or before == after
                or working.count(before) != 1
                or not _source_replacement_targets_locator(before, after, locator)
            ):
                reasons.append(
                    f"Changed file {changed_file!r} has ambiguous or unverifiable "
                    "source replacement evidence."
                )
                continue
            inferred = _inferred_css_reference_properties(before, after)
            allowed = reference_properties.get((before, after, locator))
            if allowed is not None and (
                    "unverifiable" in inferred or not inferred.issubset(allowed)):
                reasons.append(
                    f"Changed file {changed_file!r} contains CSS properties outside "
                    "the verified reference property allowlist."
                )
                continue
            working = working.replace(before, after, 1)
        if working != after_source:
            reasons.append(
                f"Changed file {changed_file!r} contains material changes outside "
                "its verified reference and requirement replacements."
            )
    return _unique(reasons)


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


def _requirement_authority_checksum(
        requirements: list[RefinementRequirement]) -> str:
    payload = [{
        "id": item.id,
        "text": item.text,
        "scope": item.scope,
        "iteration": item.iteration,
        "supersedes": item.supersedes,
    } for item in requirements]
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


def _project_manifest(project: Path, *, include_all: bool = False) -> dict[str, Any]:
    excluded = (
        set() if include_all
        else {".git", "node_modules", ".venv", "__pycache__", ".siteagent"}
    )
    records, digest = [], hashlib.sha256()
    files = []
    for item in project.rglob("*"):
        relative = item.relative_to(project)
        if excluded.intersection(relative.parts):
            continue
        if _unsafe_project_link(item):
            if not include_all:
                raise RefinementError(
                    f"Refinement projects and recovery snapshots may not contain links: {relative.as_posix()}"
                )
            try:
                link_target = os.readlink(item)
            except OSError:
                link_target = str(item.resolve(strict=False))
            link_digest = hashlib.sha256(
                ("link\0" + link_target).encode("utf-8", errors="surrogatepass")
            ).hexdigest()
            records.append({
                "path": relative.as_posix(),
                "sha256": link_digest,
                "size": 0,
            })
            continue
        if item.is_file():
            files.append(item)
    for path in sorted(files):
        relative, file_digest = path.relative_to(project).as_posix(), _file_sha(path)
        records.append({"path": relative, "sha256": file_digest, "size": path.stat().st_size})
    records.sort(key=lambda item: item["path"])
    for record in records:
        digest.update(record["path"].encode("utf-8"))
        digest.update(record["sha256"].encode("ascii"))
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
    if not gates:
        raise RefinementError("Technical readiness requires at least one browser gate result.")
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
        passed=all(gate.passed for gate in gates),
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


_BROWSER_EVIDENCE_FILES = {
    "desktop.png": ("normal", "desktop_1440", 1440, 1100),
    "desktop_1024.png": ("normal", "desktop_1024", 1024, 900),
    "tablet.png": ("normal", "tablet_768", 768, 1024),
    "mobile.png": ("normal", "mobile_390", 390, 844),
    "mobile_360.png": ("normal", "mobile_360", 360, 800),
    "reduced_motion.png": ("reduced-motion", "reduced_motion", 390, 844),
    "interaction_desktop_1440.png": ("interaction", "desktop_1440", 1440, 1100),
    "interaction_desktop_1024.png": ("interaction", "desktop_1024", 1024, 900),
    "interaction_tablet_768.png": ("interaction", "tablet_768", 768, 1024),
    "interaction_mobile_390.png": ("interaction", "mobile_390", 390, 844),
    "interaction_mobile_360.png": ("interaction", "mobile_360", 360, 800),
}
_REQUIRED_BROWSER_SCREENSHOTS = {
    name: definition[2] for name, definition in _BROWSER_EVIDENCE_FILES.items()
}
_BROWSER_EVIDENCE_MANIFEST = "browser_evidence_manifest.json"


def _route_label(index: int, target: str) -> str:
    label_source = Path(urlparse(target).path).stem or "home"
    return f"{index:02d}-{re.sub(r'[^A-Za-z0-9_-]+', '-', label_source)}"


def _route_url_identity(value: str) -> tuple[str, str, str, str, str]:
    parsed = urlparse(value)
    scheme = parsed.scheme.casefold()
    authority = parsed.netloc.casefold()
    path = parsed.path.replace("\\", "/") or "/"
    path = path.rstrip("/") or "/"
    if scheme == "file" and os.name == "nt":
        path = path.casefold()
    return scheme, authority, path, parsed.query, parsed.fragment


def _manifest_artifact_path(root: Path, relative: str) -> Path | None:
    if root.exists() and _unsafe_project_link(root):
        return None
    candidate_relative = Path(str(relative))
    if candidate_relative.is_absolute() or not candidate_relative.parts:
        return None
    if any(part in {"", ".", ".."} for part in candidate_relative.parts):
        return None
    root_resolved = root.resolve()
    candidate = root / candidate_relative
    current = root
    for part in candidate_relative.parts:
        current = current / part
        if current.exists() and _unsafe_project_link(current):
            return None
    try:
        resolved = candidate.resolve()
    except OSError:
        return None
    if resolved != root_resolved and root_resolved not in resolved.parents:
        return None
    return resolved


def _artifact_chain_has_link(path: Path, boundary: Path) -> bool:
    try:
        relative = path.relative_to(boundary)
    except ValueError:
        return True
    current = boundary
    if current.exists() and _unsafe_project_link(current):
        return True
    for part in relative.parts:
        current = current / part
        if current.exists() and _unsafe_project_link(current):
            return True
    return False


def _png_dimensions(path: Path) -> tuple[int, int]:
    with Image.open(path) as capture:
        if capture.format != "PNG":
            raise UnidentifiedImageError("Browser evidence is not a PNG.")
        capture.verify()
    with Image.open(path) as capture:
        return capture.size


def _write_browser_evidence_manifest(
        browser_dir: Path, *, session_id: str, iteration: int,
        source_tree_sha256: str, targets: list[str]) -> Path:
    captured_at = _now()
    entries: list[dict[str, Any]] = []
    for index, target in enumerate(targets):
        route_id = _route_label(index, target)
        route_dir = browser_dir / route_id
        observations_path = route_dir / "observations.json"
        observations_sha256 = (
            _file_sha(observations_path) if observations_path.is_file() else ""
        )
        try:
            observations_document = json.loads(
                observations_path.read_text(encoding="utf-8")
            )
        except (OSError, ValueError):
            observations_document = {}
        if not isinstance(observations_document, dict):
            observations_document = {}
        for filename, definition in _BROWSER_EVIDENCE_FILES.items():
            evidence_type, profile, viewport_width, viewport_height = definition
            profile_observation: dict[str, Any] = {}
            try:
                raw_profile = observations_document.get(profile, "")
                parsed_profile = (
                    json.loads(raw_profile) if isinstance(raw_profile, str)
                    else raw_profile
                )
                if isinstance(parsed_profile, dict):
                    profile_observation = parsed_profile
            except (TypeError, ValueError, json.JSONDecodeError):
                profile_observation = {}
            actual_url_field = (
                "interactionActualUrl" if evidence_type == "interaction"
                else "actualUrl"
            )
            if str(profile_observation.get(actual_url_field, "")).strip():
                actual_url = str(profile_observation[actual_url_field])
                actual_url_source = "profile_observation"
            elif str(observations_document.get("url", "")).strip():
                actual_url = str(observations_document["url"])
                actual_url_source = "route_observation"
            else:
                actual_url = target
                actual_url_source = "requested_url_fallback"
            screenshot = route_dir / filename
            try:
                png_width, png_height = _png_dimensions(screenshot)
            except (OSError, UnidentifiedImageError):
                png_width, png_height = 0, 0
            entries.append({
                "route_id": route_id,
                "requested_url": target,
                "actual_url": actual_url,
                "actual_url_source": actual_url_source,
                "viewport_width": viewport_width,
                "viewport_height": viewport_height,
                "evidence_type": evidence_type,
                "screenshot_path": screenshot.relative_to(browser_dir).as_posix(),
                "screenshot_sha256": _file_sha(screenshot) if screenshot.is_file() else "",
                "png_width": png_width,
                "png_height": png_height,
                "observations_path": observations_path.relative_to(browser_dir).as_posix(),
                "observations_sha256": observations_sha256,
                "capture_timestamp": captured_at,
            })
    manifest = {
        "schema_version": 1,
        "session_id": session_id,
        "iteration": iteration,
        "source_tree_sha256": source_tree_sha256,
        "captured_at": captured_at,
        "entries": entries,
    }
    path = browser_dir / _BROWSER_EVIDENCE_MANIFEST
    _atomic_json(path, manifest)
    return path


def _browser_evidence_rejection_reasons(
        browser_dir: Path, *, artifact_root: Path, session_id: str,
        iteration: int, source_tree_sha256: str) -> list[str]:
    reasons: list[str] = []

    expected_browser_dir = artifact_root / "browser_qa"
    session_root = artifact_root.parents[1]
    if (_artifact_chain_has_link(artifact_root, session_root)
            or _artifact_chain_has_link(browser_dir, session_root)):
        return [
            "browser evidence symlink/junction escapes the current iteration artifact root."
        ]
    try:
        if browser_dir.resolve() != expected_browser_dir.resolve():
            return [
                "browser evidence belongs outside the current session/iteration artifact root."
            ]
    except OSError:
        return ["browser evidence belongs outside the current session/iteration artifact root."]

    manifest_path = browser_dir / _BROWSER_EVIDENCE_MANIFEST
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ["browser evidence manifest is missing or invalid."]
    if not isinstance(manifest, dict):
        return ["browser evidence manifest is missing or invalid."]
    if manifest.get("schema_version") != 1:
        reasons.append("browser evidence manifest schema version is invalid.")
    if manifest.get("session_id") != session_id:
        reasons.append("browser evidence belongs to a different refinement session.")
    if manifest.get("iteration") != iteration:
        reasons.append("browser evidence belongs to a different iteration.")
    if manifest.get("source_tree_sha256") != source_tree_sha256:
        reasons.extend([
            "browser evidence source tree mismatch.",
            "stale browser evidence after source change.",
        ])

    try:
        routes_document = json.loads(
            (browser_dir / "routes.json").read_text(encoding="utf-8")
        )
        targets = (
            routes_document.get("targets") or []
            if isinstance(routes_document, dict) else []
        )
    except (OSError, ValueError):
        targets = []
    if not isinstance(targets, list):
        targets = []
    expected_routes = {
        _route_label(index, target): target for index, target in enumerate(targets)
        if isinstance(target, str) and target
    }
    if not expected_routes:
        reasons.append("missing route/viewport browser evidence.")

    entries = manifest.get("entries")
    if not isinstance(entries, list):
        return _unique(reasons + ["browser evidence manifest entries are invalid."])

    seen_screenshots: set[str] = set()
    seen_slots: set[tuple[str, str, int]] = set()
    normal_widths: dict[str, set[int]] = {route: set() for route in expected_routes}
    expected_files = {
        (route_id, filename)
        for route_id in expected_routes for filename in _BROWSER_EVIDENCE_FILES
    }
    recorded_files: set[tuple[str, str]] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            reasons.append("browser evidence manifest entries are invalid.")
            continue
        route_id = str(entry.get("route_id", ""))
        requested_url = str(entry.get("requested_url", ""))
        actual_url = str(entry.get("actual_url", ""))
        actual_url_source = str(entry.get("actual_url_source", ""))
        evidence_type = str(entry.get("evidence_type", ""))
        try:
            viewport_width = int(entry.get("viewport_width", 0))
            viewport_height = int(entry.get("viewport_height", 0))
            recorded_png_width = int(entry.get("png_width", 0))
            recorded_png_height = int(entry.get("png_height", 0))
        except (TypeError, ValueError):
            viewport_width = viewport_height = recorded_png_width = recorded_png_height = 0
        screenshot_relative = str(entry.get("screenshot_path", ""))
        observations_relative = str(entry.get("observations_path", ""))
        if ("baseline" in Path(screenshot_relative).parts
                or ".." in Path(screenshot_relative).parts):
            reasons.append(
                "baseline or previous-iteration screenshot cannot satisfy candidate browser evidence."
            )
        screenshot = _manifest_artifact_path(browser_dir, screenshot_relative)
        observations = _manifest_artifact_path(browser_dir, observations_relative)

        if route_id not in expected_routes or expected_routes.get(route_id) != requested_url:
            reasons.append("missing route/viewport browser evidence.")
        if not actual_url:
            reasons.append("browser evidence actual URL is missing.")
        elif actual_url_source not in {"profile_observation", "route_observation"}:
            reasons.append("browser evidence actual URL is missing.")
        elif _route_url_identity(actual_url) != _route_url_identity(requested_url):
            reasons.append("browser evidence belongs to a different route.")
        screenshot_name = Path(screenshot_relative).name
        definition = _BROWSER_EVIDENCE_FILES.get(screenshot_name)
        observation_profile = ""
        if definition is None:
            reasons.append("browser evidence manifest references an unexpected screenshot.")
        else:
            expected_type, observation_profile, expected_width, expected_height = definition
            if (evidence_type != expected_type or viewport_width != expected_width
                    or viewport_height != expected_height):
                reasons.append("viewport width mismatch in browser evidence.")
            expected_relative = f"{route_id}/{screenshot_name}"
            if screenshot_relative != expected_relative:
                reasons.append("browser screenshot belongs to a different route or artifact root.")
            recorded_files.add((route_id, screenshot_name))
        if screenshot_relative in seen_screenshots:
            reasons.append("duplicate screenshot reuse in browser evidence.")
        seen_screenshots.add(screenshot_relative)
        slot = (route_id, evidence_type, viewport_width)
        if slot in seen_slots:
            reasons.append("duplicate screenshot reuse in browser evidence.")
        seen_slots.add(slot)
        if evidence_type == "normal" and route_id in normal_widths:
            normal_widths[route_id].add(viewport_width)

        if screenshot is None or not screenshot.is_file():
            reasons.append("browser screenshot is missing or outside the current iteration.")
        else:
            try:
                actual_width, actual_height = _png_dimensions(screenshot)
            except (OSError, UnidentifiedImageError):
                reasons.append("invalid PNG in browser evidence.")
            else:
                if (actual_width != viewport_width or actual_width != recorded_png_width
                        or actual_height != recorded_png_height or actual_height <= 0):
                    reasons.append("viewport width mismatch in browser evidence.")
            try:
                screenshot_sha256 = _file_sha(screenshot)
            except OSError:
                reasons.append("browser screenshot is missing or outside the current iteration.")
            else:
                if screenshot_sha256 != entry.get("screenshot_sha256"):
                    reasons.append("screenshot checksum mismatch in browser evidence.")

        expected_observations = f"{route_id}/observations.json"
        if observations_relative != expected_observations:
            reasons.append("observations belong to a different route or iteration.")
        if observations is None or not observations.is_file():
            reasons.append("observations JSON is missing from current iteration.")
        else:
            try:
                observations_sha256 = _file_sha(observations)
            except OSError:
                reasons.append("observations JSON is missing from current iteration.")
            else:
                if observations_sha256 != entry.get("observations_sha256"):
                    reasons.append("observations checksum mismatch in browser evidence.")
            try:
                observations_document = json.loads(
                    observations.read_text(encoding="utf-8")
                )
            except (OSError, ValueError):
                reasons.append("observations JSON is invalid.")
            else:
                if not isinstance(observations_document, dict):
                    reasons.append("observations JSON is invalid.")
                else:
                    raw_profile = observations_document.get(observation_profile, "")
                    try:
                        profile_observation = (
                            json.loads(raw_profile) if isinstance(raw_profile, str)
                            else raw_profile
                        )
                    except (TypeError, ValueError, json.JSONDecodeError):
                        profile_observation = {}
                    actual_url_field = (
                        "interactionActualUrl" if evidence_type == "interaction"
                        else "actualUrl"
                    )
                    observed_url = str(
                        (profile_observation.get(actual_url_field)
                         if isinstance(profile_observation, dict) else "")
                        or observations_document.get("url") or requested_url
                    )
                    if observed_url != actual_url:
                        reasons.append(
                            "browser evidence actual URL does not match observations."
                        )
        if not str(entry.get("capture_timestamp", "")).strip():
            reasons.append("browser evidence capture timestamp is missing.")

    if recorded_files != expected_files:
        reasons.append("missing route/viewport browser evidence.")
    if any(not set(TARGET_WIDTHS).issubset(widths)
           for widths in normal_widths.values()):
        reasons.append("missing route/viewport browser evidence.")
    return _unique(reasons)


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
            reasons = [
                "browser evidence source tree mismatch.",
                "stale browser evidence after source change.",
            ]
            self._invalidate_candidate(session, reasons)
            raise RefinementError(
                "Candidate project changed after QA; new browser QA is required."
            )
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
        browser_evidence_reasons = _browser_evidence_rejection_reasons(
            iteration_dir / "browser_qa", artifact_root=iteration_dir,
            session_id=session.session_id, iteration=session.candidate_iteration,
            source_tree_sha256=session.candidate_tree_sha256,
        )
        if browser_evidence_reasons:
            self._invalidate_candidate(session, browser_evidence_reasons)
            raise RefinementError(
                "Candidate browser evidence is invalid: " +
                "; ".join(browser_evidence_reasons)
            )
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

    def _invalidate_candidate(self, session: RefinementSession,
                              reasons: list[str]) -> None:
        reasons = _unique(reasons)
        candidate_iteration = session.candidate_iteration
        self._transition(
            session, RefinementStatus.IMPLEMENTING,
            "candidate browser evidence is stale; new browser QA is required",
        )
        invalidation = {
            "at": _now(),
            "reasons": reasons,
            "new_browser_qa_required": True,
        }
        session.last_qa_result["candidate_invalidation"] = invalidation
        iteration_dir = (
            self.session_dir(session.session_id) / "iterations" /
            f"{candidate_iteration:03d}"
        )
        report_path = iteration_dir / "candidate_report.json"
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            report = {}
        report["candidate_readiness"] = {
            "evaluated": True,
            "allowed": False,
            "rejection_reasons": reasons,
        }
        report["candidate_invalidation"] = invalidation
        report["current_status"] = session.status.value
        _atomic_json(report_path, report)
        markdown_path = iteration_dir / "candidate_report.md"
        if markdown_path.is_file():
            markdown = markdown_path.read_text(encoding="utf-8")
            markdown += "\n\n## Candidate invalidation\n\n"
            markdown += "\n".join(f"- {reason}" for reason in reasons)
            markdown += "\n- New browser QA is required.\n"
            markdown_path.write_text(markdown, encoding="utf-8")
        session.candidate_summary = ""
        session.candidate_tree_sha256 = ""
        session.candidate_requirement_sha256 = ""
        session.candidate_screenshot_sha256 = {}
        session.candidate_artifact_sha256 = {}
        session.candidate_baseline_sha256 = ""
        session.candidate_baseline_tree_sha256 = ""
        session.candidate_snapshot_sha256 = ""
        session.candidate_iteration = -1
        self._save(session)

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
            "schema_version": 2, "session_id": session.session_id,
            "project_id": session.project_id, "iteration": session.iteration,
            "active_requirements": [item.model_dump(mode="json") for item in session.active_requirements],
            "requirements_authority_sha256": _requirement_authority_checksum(
                session.requirements
            ),
            "immutable_constraints": session.immutable_constraints, "scope": session.scope,
            "reference_mappings": [item.model_dump(mode="json") for item in session.attachments
                                   if item.kind in {"reference", "screenshot"}],
        }
        _atomic_json(iteration_dir / "change_plan.json", plan)
        session.current_change_plan_sha256 = _payload_sha(plan)
        self._save(session)
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
            try:
                implementation = self.executor.run(
                    session=session, iteration_dir=iteration_dir,
                    attachments=[path for path in attachments if path.is_file()
                                 and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".gif"}],
                )
            except RefinementRuntimeError as exc:
                self._block_runtime_failure(session, exc)
                return session
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
            browser_source_tree_sha256 = _project_manifest(project)["tree_sha256"]
            gate, observations = self._inspect_targets(
                targets, browser_dir, project,
                session_id=session.session_id, iteration=session.iteration,
                source_tree_sha256=browser_source_tree_sha256,
            )
            self._transition(session, RefinementStatus.VISUAL_QA,
                             "rendered screenshots captured")
            reference_images = [session_dir / item.stored_path for item in session.attachments
                                if item.kind in {"reference", "screenshot"}]
            try:
                review = self.reviewer.review(
                    session=session, iteration_dir=iteration_dir, implementation=implementation,
                    gate=gate, screenshots=sorted(browser_dir.rglob("*.png")) +
                    [path for path in reference_images if path.is_file()],
                )
            except RefinementRuntimeError as exc:
                self._block_runtime_failure(session, exc)
                return session
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
                browser_evidence_required=True,
                rejection_reasons=candidate_rejection_reasons):
            session.candidate_summary = review.summary
            session.candidate_tree_sha256 = browser_source_tree_sha256
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
            target_component=incoming.target_component,
            target_locator=incoming.target_locator,
            target_properties=list(dict.fromkeys(incoming.target_properties)),
            target_properties_explicit=incoming.target_properties_explicit,
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
                    baseline_source_tree_sha256 = _project_manifest(project)["tree_sha256"]
                    gate, observations = self._inspect_targets(
                        targets, baseline_dir / "browser", project,
                        session_id=session.session_id, iteration=session.iteration,
                        source_tree_sha256=baseline_source_tree_sha256,
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
            if not _reference_scope_rejection_reasons(
                    session.model_copy(update={"attachments": [attachment], "scope": []})):
                continue
            path = self._validated_attachment_paths(session)[session.attachments.index(attachment)]
            prompt = f"""
Analyze this user-supplied visual reference for an existing-site refinement.
Using the user's live goal and requirements below, determine its exact
page/section/component scope, a concrete selector/locator for that component,
whether it is an exact target or visual direction,
and a strict property allowlist plus only the visual
principles to transfer (composition, grid, typography, scale, spacing, component
shape, color, density, photography, interaction, animation, responsive behavior).
Do not copy a whole third-party site. Never change a non-empty page, section,
component, locator, or property allowlist already supplied by the user; property analysis
may only stay within that explicit allowlist. Mark ambiguous when the user
context cannot support a safe mapping without changing an explicit boundary.

Goal: {session.user_goal}
Requirements: {json.dumps([item.text for item in session.active_requirements], ensure_ascii=False)}
Existing mapping: {attachment.model_dump_json(indent=2)}
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
            merged, conflicts = _merge_reference_analysis_without_widening(
                attachment, analysis
            )
            if merged is None:
                session.blockers = _unique(session.blockers + [
                    f"Automatic analysis tried to widen or replace explicit scope for "
                    f"reference {attachment.id}: {', '.join(conflicts)}."
                ])
                continue
            proposed_session = session.model_copy(
                update={"attachments": [merged]}, deep=True
            )
            proposed_reasons = _reference_scope_rejection_reasons(proposed_session)
            if proposed_reasons:
                session.blockers = _unique(session.blockers + [
                    f"Automatic analysis could not produce a safe mapping for reference "
                    f"{attachment.id}: {'; '.join(proposed_reasons)}"
                ])
                continue
            attachment.target_page = merged.target_page
            attachment.target_section = merged.target_section
            attachment.target_component = merged.target_component
            attachment.target_locator = merged.target_locator
            attachment.target_properties = list(merged.target_properties)
            attachment.interpretation = merged.interpretation
            attachment.transfer = list(merged.transfer)

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
                         project_root: Path, *, session_id: str, iteration: int,
                         source_tree_sha256: str) -> tuple[TechnicalGate, dict[str, str]]:
        gates, observations = [], {}
        for index, target in enumerate(targets):
            if _project_manifest(project_root)["tree_sha256"] != source_tree_sha256:
                raise RefinementError(
                    "Project source changed while browser evidence was being captured."
                )
            label = _route_label(index, target)
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
            if _project_manifest(project_root)["tree_sha256"] != source_tree_sha256:
                raise RefinementError(
                    "Project source changed while browser evidence was being captured."
                )
        combined = _merge_technical_gates(gates)
        _atomic_json(browser_dir / "technical_gate.json", combined.model_dump(mode="json"))
        _atomic_json(browser_dir / "routes.json", {"targets": targets})
        _write_browser_evidence_manifest(
            browser_dir, session_id=session_id, iteration=iteration,
            source_tree_sha256=source_tree_sha256, targets=targets,
        )
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

    def _block_runtime_failure(self, session: RefinementSession,
                               error: RefinementRuntimeError) -> None:
        reason = f"{error.role} runtime failure: {error.reason}"
        session.blockers = _unique(session.blockers + [reason])
        session.last_qa_result = {
            "runtime_failure": {
                "role": error.role,
                "reason": error.reason,
                "evidence_path": error.evidence_path,
                "candidate_allowed": False,
            }
        }
        self._transition(
            session,
            RefinementStatus.BLOCKED,
            f"fail-closed {error.role} runtime failure",
        )
        self._save(session)

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
                           browser_evidence_required: bool = True,
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
        browser_evidence_reasons: list[str] = []
        if browser_dir is not None:
            artifact_root = (
                self.session_dir(session.session_id) / "iterations" /
                f"{session.iteration:03d}"
            )
            browser_evidence_reasons = _browser_evidence_rejection_reasons(
                browser_dir, artifact_root=artifact_root,
                session_id=session.session_id, iteration=session.iteration,
                source_tree_sha256=_project_manifest(
                    Path(session.project_path)
                )["tree_sha256"],
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
        snapshot_passes = (
            snapshot_dir is not None and _snapshot_valid(snapshot_dir)
            if browser_evidence_required else
            snapshot_dir is None or _snapshot_valid(snapshot_dir)
        )
        reference_scope_reasons = _reference_scope_rejection_reasons(
            session, implementation
        )
        planned_requirement_ids = _planned_requirement_ids(snapshot_dir, session)
        if planned_requirement_ids is None and not browser_evidence_required:
            # Focused model/candidate tests may intentionally omit artifact
            # directories; production candidate evaluation never does.
            planned_requirement_ids = set(implementation.completed_requirement_ids)
        requirement_change_reasons = _requirement_change_rejection_reasons(
            session, implementation,
            authorized_requirement_ids=planned_requirement_ids,
        )
        reference_source_reasons = _reference_source_verification_reasons(
            session, implementation, snapshot_dir
        )
        has_reference_mappings = any(
            item.kind in {"reference", "screenshot"} for item in session.attachments
        )
        checks = (
            (not session.last_qa_result.get("runtime_failure"),
             "A fail-closed executor or reviewer runtime failure is recorded."),
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
            (not gate.blocking_reasons,
             "The technical browser gate contains blocking evidence."),
            (not browser_evidence_required or browser_dir is not None,
             "Mandatory browser evidence is missing."),
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
            (not has_reference_mappings or review.reference_property_scope_verified,
             "Independent review did not verify reference property-scope isolation."),
            (review.functional_qa_passed, "Independent functional QA did not pass."),
            (review.content_qa_passed, "Independent content QA did not pass."),
            (review.animation_qa_passed, "Independent animation QA did not pass."),
            (not blocking_review,
             "Independent review contains a P0 or P1 issue."),
            (commands_pass, "A required local build or test command did not pass."),
            (bool(implementation.changed_files),
             "No authored project change was recorded for this iteration."),
        )
        reasons = _unique(
            [message for passed, message in checks if not passed] +
            browser_evidence_reasons + reference_scope_reasons +
            requirement_change_reasons + reference_source_reasons
        )
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
        browser_manifest_path = iteration_dir / "browser_qa" / _BROWSER_EVIDENCE_MANIFEST
        browser_manifest: dict[str, Any] = {}
        if browser_manifest_path.is_file():
            try:
                browser_manifest = json.loads(
                    browser_manifest_path.read_text(encoding="utf-8")
                )
            except (OSError, ValueError):
                browser_manifest = {}
        payload = {
            "what_changed": implementation.changed_files,
            "what_verified": {
                "target_widths": list(TARGET_WIDTHS),
                "browser_gate": gate.model_dump(mode="json") if gate else None,
                "browser_evidence_manifest": (
                    f"browser_qa/{_BROWSER_EVIDENCE_MANIFEST}"
                    if browser_manifest_path.is_file() else ""
                ),
                "browser_source_tree_sha256": browser_manifest.get(
                    "source_tree_sha256", ""
                ),
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
