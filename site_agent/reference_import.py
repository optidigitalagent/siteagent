"""Resumable screenshot-led importer for the approved reference library."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from playwright.sync_api import sync_playwright
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from site_agent.config import settings
from site_agent.llm import LLMClient, StructuredOutputError
from site_agent.reference_discovery import ReferenceDiscoveryAgent, write_decisions
from site_agent.workflow import checksum

SEED_URLS = (
    "https://optidigitalagent.github.io/eliz-de-fleur-site-20260711095843/", "http://belladentclinik.kr.ua/", "https://optidigitalagent.github.io/orange-beauty-studio/", "https://optidigitalagent.github.io/atmosfera-site/", "https://optidigitalagent.github.io/drivepark/", "https://optidigitalagent.github.io/yourdental1/", "https://optidigitalagent.github.io/yourdental2/", "https://optidigitalagent.github.io/hollywood2/", "https://optidigitalagent.github.io/hollywood1/", "https://optidigitalagent.github.io/kafespeka2/", "https://uniquerabbitstudios.com/", "https://optidigitalagent.github.io/kirkovsky/", "https://newartem855-netizen.github.io/-ZVD/", "https://defolixx.github.io/SunSity/", "https://optidigitalagent.github.io/hereta/", "https://optidigitalagent.github.io/orange2/", "https://optidigitalagent.github.io/orange1/", "https://optidigitalagent.github.io/dentistry_kievskaya2/", "https://optidigitalagent.github.io/dentistry_kievskaya1/", "https://newartem855-netizen.github.io/auratop1/", "https://newartem855-netizen.github.io/Panem-Digital-Agency/", "https://eurozet.ua/", "https://webgoalz.com/", "https://zaffiraxis.github.io/status1/", "https://zaffiraxis.github.io/silk-road-rent-car/index.html#why", "https://zaffiraxis.github.io/margo-salon/", "https://iodent.dental/", "https://parkrestaurant.kyiv.ua/",
)
ANALYSIS_PROMPT_VERSION = "reference-analyst-v2"
RAW_RESPONSE_FILE = "analysis_raw_responses.json"


def normalize_url(url: str) -> str:
    parts = urlsplit(url)
    query = urlencode([(key, value) for key, value in parse_qsl(parts.query) if not key.lower().startswith(("utm_", "fbclid", "gclid"))])
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path or "/", query, ""))


def reference_id(url: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", urlsplit(url).netloc + urlsplit(url).path).strip("-")[:80]


class ReferenceAnalysis(BaseModel):
    """The exact screenshot-analysis contract; unrecognised fields are invalid."""

    model_config = ConfigDict(extra="forbid")

    business_context: str = Field(min_length=1)
    audience: str = Field(min_length=1)
    conversion_goal: str = Field(min_length=1)
    first_viewport_logic: str = Field(min_length=1)
    information_architecture: list[str] = Field(min_length=1)
    narrative_storytelling: str = Field(min_length=1)
    composition_grid: str = Field(min_length=1)
    spacing_rhythm: str = Field(min_length=1)
    typography: str = Field(min_length=1)
    palette_contrast: str = Field(min_length=1)
    media_treatment: str = Field(min_length=1)
    motion_interaction: str = Field(min_length=1)
    cta_strategy: str = Field(min_length=1)
    desktop_behavior: str = Field(min_length=1)
    mobile_behavior: str = Field(min_length=1)
    learn: list[str] = Field(min_length=1)
    do_not_copy: list[str] = Field(min_length=1)
    reusable_cross_category_traits: list[str] = Field(min_length=3)
    traits: list[str] = Field(min_length=3)

    @field_validator("*", mode="after")
    @classmethod
    def reject_empty_or_placeholder_values(cls, value: Any) -> Any:
        forbidden = {"", "-", "n/a", "na", "unknown", "not available", "placeholder", "to be inferred", "requires visual review"}
        values = value if isinstance(value, list) else [value]
        for item in values:
            if not isinstance(item, str) or item.strip().lower() in forbidden:
                raise ValueError("ReferenceAnalysis fields must contain concrete screenshot observations.")
        return value


class ScreenshotAnalyst(Protocol):
    def analyze(self, *, desktop: Path, mobile: Path, url: str, title: str) -> tuple[dict[str, Any], dict[str, Any]]: ...


class ReferenceAnalysisError(RuntimeError):
    def __init__(self, message: str, *, raw_responses: list[str], repair_count: int) -> None:
        super().__init__(message)
        self.raw_responses = raw_responses
        self.repair_count = repair_count


class BrowserDisconnected(RuntimeError):
    pass


class OpenAIReferenceAnalyst:
    system = """You are the screenshot-led Reference Analyst for a bespoke web studio. Analyse the supplied desktop and mobile captures as visual evidence, not DOM metadata. Fill every field with a concrete observation. Do not use placeholders such as 'requires visual review', 'to be inferred', or 'inspect visible CTA'. References teach transferable principles only: explicitly state what must not be copied."""

    def __init__(self, llm: LLMClient | None = None) -> None:
        self.llm = llm or LLMClient(provider=settings.reference_analyst_provider)

    def analyze(self, *, desktop: Path, mobile: Path, url: str, title: str) -> tuple[dict[str, Any], dict[str, Any]]:
        user = f"Reference URL: {url}\nPage title: {title}\nThe first image is desktop and the second is mobile. Return a complete visual analysis."
        try:
            structured = self.llm.multimodal_structured_with_debug(
                system=self.system, user=user, image_paths=[desktop, mobile], schema=ReferenceAnalysis,
                max_repair_attempts=1,
            )
        except StructuredOutputError as exc:
            raise ReferenceAnalysisError(
                str(exc), raw_responses=exc.responses, repair_count=exc.repair_count
            ) from exc
        output = structured.value.model_dump()
        provenance = {
            "role": "Reference Analyst", "provider": self.llm.provider, "model": self.llm.model,
            "prompt_version": ANALYSIS_PROMPT_VERSION,
            "prompt_checksum": checksum({"system": self.system, "user": user}),
            "input_checksum": checksum({"url": url, "title": title, "desktop_sha256": _file_hash(desktop), "mobile_sha256": _file_hash(mobile)}),
            "output_checksum": checksum(output), "timestamp": _timestamp(), "used": True,
            "repair_count": structured.repair_count, "_raw_responses": structured.responses,
        }
        return output, provenance


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json_atomic(path: Path, payload: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def _safe_error(value: object, *, limit: int = 500) -> str:
    message = str(value).replace("\x00", " ")
    message = re.sub(r"\bsk-[A-Za-z0-9_-]+", "[REDACTED_SECRET]", message)
    message = re.sub(r"(?i)(authorization|api[_-]?key|bearer)\s*[:= ]\s*[^\s,;]+", r"\1=[REDACTED_SECRET]", message)
    return message[:limit]


def _is_browser_disconnect(exc: BaseException) -> bool:
    message = str(exc).lower()
    return any(marker in message for marker in (
        "connection closed while reading from the driver", "browser has been closed",
        "target page, context or browser has been closed", "playwright driver", "connection closed",
    ))


class ReferenceImporter:
    def __init__(
        self, root: Path = Path("references/site_designs"), *, analyst: ScreenshotAnalyst | None = None,
        seeds: tuple[str, ...] = SEED_URLS, max_browser_restarts: int = 3,
        discovery: ReferenceDiscoveryAgent | None = None, refresh_discovery: bool = False, discovery_limit_per_source: int = 8,
    ) -> None:
        self.root, self.analyst, self.seeds = root, analyst, seeds
        self.max_browser_restarts = max_browser_restarts
        self.discovery, self.refresh_discovery, self.discovery_limit_per_source = discovery, refresh_discovery, discovery_limit_per_source
        self._discovery_by_original: dict[str, dict[str, Any]] = {}

    def run(self) -> dict:
        self.root.mkdir(parents=True, exist_ok=True)
        sources = self._sources_for_run()
        warnings: list[dict[str, str]] = []
        restart_counts: dict[str, int] = {}
        browser_restarts = 0
        browser = None
        try:
            with sync_playwright() as playwright:
                for source in sources:
                    url = normalize_url(source)
                    item_id = reference_id(url)
                    while True:
                        try:
                            if self._needs_capture(url) and browser is None:
                                browser = playwright.chromium.launch()
                            result = self._import_one(browser, url, cleanup_warnings=warnings, discovery=self._discovery_by_original.get(url))
                            self._checkpoint(warnings=warnings, restart_counts=restart_counts)
                            break
                        except BrowserDisconnected as exc:
                            restart_counts[item_id] = restart_counts.get(item_id, 0) + 1
                            browser_restarts += 1
                            warnings.append({"stage": "browser_restart", "message": _safe_error(exc), "reference_id": item_id})
                            self._safe_close(browser, warnings, "browser_close_after_disconnect")
                            browser = None
                            if browser_restarts <= self.max_browser_restarts:
                                continue
                            result = self._capture_failure(url, _safe_error(exc), "browser_restart_limit")
                            self._checkpoint(warnings=warnings, restart_counts=restart_counts)
                            break
                self._safe_close(browser, warnings, "browser_close")
                browser = None
        except Exception as exc:
            # Playwright's own context cleanup can fail after all durable record
            # writes. Keep that failure diagnostic-only and still build the catalog.
            warnings.append({"stage": "playwright_lifecycle", "message": _safe_error(exc)})
        finally:
            self._safe_close(browser, warnings, "browser_close_finally")
            catalog = self._finalize_catalog(warnings=warnings, restart_counts=restart_counts)
        return catalog

    def _sources_for_run(self) -> tuple[str, ...]:
        """Refresh award discovery without ever replacing saved raw records."""
        sources = list(self.seeds)
        if not self.refresh_discovery:
            return tuple(sources)
        discovery = self.discovery or ReferenceDiscoveryAgent()
        findings = discovery.discover(limit_per_source=self.discovery_limit_per_source)
        _write_json_atomic(self.root / "discovery_candidates.json", {
            "schema_version": 1, "generated_at": _timestamp(), "candidates": findings,
        })
        for item in findings:
            if item.get("status") == "resolved" and item.get("original_url"):
                original = normalize_url(str(item["original_url"]))
                self._discovery_by_original[original] = item
                sources.append(original)
        return tuple(dict.fromkeys(normalize_url(item) for item in sources))

    def _safe_close(self, resource: Any, warnings: list[dict[str, str]], stage: str) -> None:
        if resource is None:
            return
        try:
            resource.close()
        except Exception as exc:  # cleanup must never discard durable work
            warnings.append({"stage": stage, "message": _safe_error(exc)})

    def _needs_capture(self, url: str) -> bool:
        folder = self.root / reference_id(url)
        record = folder / "reference.json"
        if not record.is_file():
            return True
        try:
            prior = json.loads(record.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return True
        return not self._capture_intact(prior, folder)

    def _checkpoint(self, *, warnings: list[dict[str, str]], restart_counts: dict[str, int]) -> None:
        records = self._saved_records()
        state = self._state(records)
        payload = {
            "schema_version": 2, "updated_at": _timestamp(), "seed_count": len(self.seeds),
            "processed": len(records), **state, "cleanup_warnings": warnings,
            "browser_restart_counts": restart_counts,
        }
        _write_json_atomic(self.root / "import_checkpoints.json", payload)

    def _saved_records(self) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for record_path in sorted(self.root.glob("*/reference.json")):
            try:
                records.append(json.loads(record_path.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError) as exc:
                records.append({"id": record_path.parent.name, "capture_status": "failed", "analysis_status": "not_started", "failure": {"stage": "record_read", "message": _safe_error(exc)}})
        return records

    def _state(self, records: list[dict[str, Any]]) -> dict[str, Any]:
        completed = [item["id"] for item in records if self._complete_and_intact(item, self.root / item["id"])]
        analysis_failed = [item["id"] for item in records if item.get("capture_status") == "captured" and item.get("analysis_status") == "failed"]
        capture_failed = [item["id"] for item in records if item.get("capture_status") == "failed"]
        started = {item.get("id") for item in records}
        not_started = [reference_id(normalize_url(source)) for source in self.seeds if reference_id(normalize_url(source)) not in started]
        failures = [
            {"id": item.get("id"), "stage": item.get("failure", {}).get("stage"), "message": _safe_error(item.get("failure", {}).get("message", ""))}
            for item in records if item.get("failure")
        ]
        retry_counts = {item.get("id", "unknown"): int(item.get("failure", {}).get("attempt", 0)) for item in records if item.get("failure")}
        return {
            "completed": completed, "analysis_failed": analysis_failed, "capture_failed": capture_failed,
            "not_started": not_started, "failures": failures, "retry_counts": retry_counts,
        }

    def _finalize_catalog(self, *, warnings: list[dict[str, str]], restart_counts: dict[str, int]) -> dict:
        records = self._saved_records()
        state = self._state(records)
        decisions = write_decisions(self.root, records)
        active_ids = {item["reference_id"] for item in decisions["decisions"] if item["decision"] == "active"}
        excluded_ids = {item["reference_id"] for item in decisions["decisions"] if item["decision"] == "excluded"}
        catalog = {
            "schema_version": 3, "generated_at": _timestamp(), "references": records, **state,
            "cleanup_warnings": warnings, "browser_restart_counts": restart_counts,
            "decision_artifact": "reference_decisions.json", "active_reference_ids": sorted(active_ids),
            "excluded_reference_ids": sorted(excluded_ids), "active_reference_count": len(active_ids),
            "excluded_reference_count": len(excluded_ids),
            "status": decisions["status"],
        }
        catalog["catalog_checksum"] = checksum(catalog)
        _write_json_atomic(self.root / "catalog.json", catalog)
        report = {
            "generated_at": _timestamp(), "completed": state["completed"], "analysis_failed": state["analysis_failed"],
            "capture_failed": state["capture_failed"], "not_started": state["not_started"],
            "cleanup_warnings": warnings, "browser_restart_counts": restart_counts,
            "retry_counts": state["retry_counts"], "failures": state["failures"], "status": catalog["status"],
            "active_reference_count": len(active_ids), "excluded_reference_count": len(excluded_ids),
        }
        _write_json_atomic(self.root / "import_report.json", report)
        return catalog

    def _complete_and_intact(self, prior: dict, folder: Path) -> bool:
        if prior.get("capture_status") != "captured" or prior.get("analysis_status") != "completed":
            return False
        artifacts = prior.get("capture", {}).get("screenshots", {})
        if set(artifacts) != {"desktop.png", "mobile.png"}:
            return False
        try:
            if not all((folder / name).is_file() and _file_hash(folder / name) == digest for name, digest in artifacts.items()):
                return False
            analysis = prior.get("analysis", {})
            ReferenceAnalysis.model_validate(analysis)
            return prior.get("content_hash") == checksum({"capture": prior.get("capture"), "analysis": analysis})
        except (OSError, ValidationError, TypeError):
            return False

    def _capture_intact(self, prior: dict, folder: Path) -> bool:
        artifacts = prior.get("capture", {}).get("screenshots", {})
        try:
            return prior.get("capture_status") == "captured" and set(artifacts) == {"desktop.png", "mobile.png"} and all(
                (folder / name).is_file() and _file_hash(folder / name) == digest for name, digest in artifacts.items()
            )
        except OSError:
            return False

    def _capture_failure(self, url: str, message: str, stage: str = "capture") -> dict:
        folder = self.root / reference_id(url)
        folder.mkdir(parents=True, exist_ok=True)
        record = folder / "reference.json"
        prior = self._load_prior(record)
        result = {
            "id": folder.name, "title": prior.get("title", folder.name), "source_url": url, "normalized_url": url,
            "capture_status": "failed", "analysis_status": "not_started",
            "failure": {"stage": stage, "message": _safe_error(message), "timestamp": _timestamp(), "attempt": int(prior.get("failure", {}).get("attempt", 0)) + 1},
            "traits": [], "learn": [], "do_not_copy": ["The source is unavailable and cannot be used as a template."],
        }
        _write_json_atomic(record, result)
        return result

    def _load_prior(self, record: Path) -> dict[str, Any]:
        try:
            return json.loads(record.read_text(encoding="utf-8")) if record.is_file() else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _capture(self, browser: Any, url: str, desktop_path: Path, mobile_path: Path, warnings: list[dict[str, str]]) -> tuple[str, str, dict[str, Any]]:
        desktop = mobile = None
        failed_assets: list[dict[str, str]] = []
        def observe_failure(request: Any) -> None:
            try:
                kind = str(request.resource_type)
                if kind in {"document", "stylesheet", "script", "image", "font"}:
                    failed_assets.append({"resource_type": kind, "url": _safe_error(str(request.url), limit=300)})
            except Exception:
                return
        try:
            desktop = browser.new_page(viewport={"width": 1440, "height": 1100})
            mobile = browser.new_page(viewport={"width": 390, "height": 844}, is_mobile=True)
            if callable(getattr(desktop, "on", None)):
                desktop.on("requestfailed", observe_failure)
            if callable(getattr(mobile, "on", None)):
                mobile.on("requestfailed", observe_failure)
            desktop_response = desktop.goto(url, wait_until="domcontentloaded", timeout=45_000)
            if callable(getattr(desktop, "wait_for_timeout", None)):
                desktop.wait_for_timeout(1500)
            title = desktop.title() or desktop_path.parent.name
            desktop.screenshot(path=str(desktop_path), full_page=True)
            mobile_response = mobile.goto(url, wait_until="domcontentloaded", timeout=45_000)
            if callable(getattr(mobile, "wait_for_timeout", None)):
                mobile.wait_for_timeout(1500)
            mobile.screenshot(path=str(mobile_path), full_page=True)
            capture = {
                "captured_at": _timestamp(), "final_url": desktop.url,
                "http_status": {"desktop": getattr(desktop_response, "status", None), "mobile": getattr(mobile_response, "status", None)},
                "failed_critical_assets": failed_assets[:30],
                "screenshots": {"desktop.png": _file_hash(desktop_path), "mobile.png": _file_hash(mobile_path)},
                "browser_viewports": {"desktop": [1440, 1100], "mobile": [390, 844]},
            }
            return title, desktop.url, capture
        except Exception as exc:
            if _is_browser_disconnect(exc):
                raise BrowserDisconnected(_safe_error(exc)) from exc
            raise
        finally:
            self._safe_close(mobile, warnings, "mobile_page_close")
            self._safe_close(desktop, warnings, "desktop_page_close")

    def _write_raw_responses(self, folder: Path, responses: list[str], repair_count: int) -> dict[str, Any]:
        payload = {
            "schema_version": 1, "saved_at": _timestamp(), "repair_count": repair_count,
            "responses": [_safe_error(response, limit=12_000) for response in responses],
        }
        path = folder / RAW_RESPONSE_FILE
        _write_json_atomic(path, payload)
        return {"path": RAW_RESPONSE_FILE, "sha256": _file_hash(path), "repair_count": repair_count}

    def _import_one(self, browser: Any, url: str, *, cleanup_warnings: list[dict[str, str]] | None = None, discovery: dict[str, Any] | None = None) -> dict:
        warnings = cleanup_warnings if cleanup_warnings is not None else []
        folder = self.root / reference_id(url)
        folder.mkdir(parents=True, exist_ok=True)
        record = folder / "reference.json"
        prior = self._load_prior(record)
        if self._complete_and_intact(prior, folder):
            return prior

        desktop_path, mobile_path = folder / "desktop.png", folder / "mobile.png"
        if self._capture_intact(prior, folder):
            title = prior.get("title", folder.name)
            capture = prior["capture"]
        else:
            if browser is None:
                raise RuntimeError("Browser is required to capture an unfinished reference.")
            try:
                title, _, capture = self._capture(browser, url, desktop_path, mobile_path, warnings)
            except BrowserDisconnected:
                raise
            except Exception as exc:
                return self._capture_failure(url, _safe_error(exc))

        try:
            analyst = self.analyst or OpenAIReferenceAnalyst()
            analysis, provenance = analyst.analyze(desktop=desktop_path, mobile=mobile_path, url=url, title=title)
            raw_responses = provenance.pop("_raw_responses", [])
            if raw_responses:
                provenance["raw_response_debug"] = self._write_raw_responses(folder, raw_responses, int(provenance.get("repair_count", 0)))
            result = {
                "id": folder.name, "title": title, "source_url": url, "normalized_url": url,
                "screenshot_paths": ["desktop.png", "mobile.png"], "capture_status": "captured", "analysis_status": "completed",
                "capture": capture, "analysis": analysis, "analysis_provenance": provenance, **analysis,
            }
            if discovery:
                result["discovery"] = {key: value for key, value in discovery.items() if key not in {"reason"}}
            result["content_hash"] = checksum({"capture": capture, "analysis": analysis})
        except ReferenceAnalysisError as exc:
            debug = self._write_raw_responses(folder, exc.raw_responses, exc.repair_count)
            result = self._analysis_failure(url, title, capture, prior, str(exc), debug)
        except Exception as exc:
            result = self._analysis_failure(url, title, capture, prior, _safe_error(exc), None)
        _write_json_atomic(record, result)
        return result

    def _analysis_failure(self, url: str, title: str, capture: dict[str, Any], prior: dict[str, Any], message: str, debug: dict[str, Any] | None) -> dict:
        result = {
            "id": reference_id(url), "title": title, "source_url": url, "normalized_url": url,
            "screenshot_paths": ["desktop.png", "mobile.png"], "capture_status": "captured", "analysis_status": "failed",
            "capture": capture,
            "failure": {"stage": "analysis", "message": _safe_error(message), "timestamp": _timestamp(), "attempt": int(prior.get("failure", {}).get("attempt", 0)) + 1},
            "traits": [], "learn": [], "do_not_copy": ["Captured source must not be selected until screenshot analysis completes."],
        }
        if debug:
            result["analysis_debug"] = debug
        return result


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Import and autonomously curate screenshot-led web references.")
    parser.add_argument("--refresh-discovery", action="store_true", help="Fetch award sources, resolve original live sites, and resume their import.")
    options = parser.parse_args()
    print(json.dumps(ReferenceImporter(refresh_discovery=options.refresh_discovery).run(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
