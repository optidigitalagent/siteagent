from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Literal
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field

from site_agent.config import Settings, settings
from site_agent.identifiers import cloudflare_project_name, stable_business_id
from site_agent.json_io import write_json
from site_agent.publisher import (
    CloudflarePagesPublisher,
    LiveVerificationError,
    PublisherConfigurationError,
    PublisherError,
    SiteValidationError,
    validate_site_directory,
)


PREVIEW_PROJECT_PREFIX = "siteagent-preview"
PREVIEW_PRODUCTION_BRANCH = "production-disabled"
PREVIEW_BRANCH_PREFIX = "preview"
ROBOTS_CONTENT = "noindex,nofollow,noarchive,nosnippet"
X_ROBOTS_CONTENT = "noindex, nofollow, noarchive, nosnippet"


class PreviewDeploymentResult(BaseModel):
    provider: Literal["cloudflare_pages_preview"] = "cloudflare_pages_preview"
    project_name: str
    preview_url: str
    deployment_url: str
    deployment_id: str = ""
    branch: str
    environment: Literal["preview"] = "preview"
    status: Literal["success"] = "success"
    deployed_at: str
    verification_status: Literal["verified"] = "verified"
    staging_dir: str
    checks: dict[str, Any] = Field(default_factory=dict)

    @property
    def site_url(self) -> str:
        return self.preview_url


class PreviewPublisher(CloudflarePagesPublisher):
    """Publish an accepted site to an isolated, crawler-blocked Pages preview.

    This publisher deliberately has no production URL, custom-domain, queue, or
    Telegram integration. A distinct project and a non-production branch are
    derived from the run identity, and only the direct deployment URL is
    returned as the review URL.
    """

    def __init__(
        self,
        config: Settings | None = None,
        *,
        runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
        which: Callable[[str], str | None] = shutil.which,
        http_get: Callable[..., Any] = requests.get,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        super().__init__(
            config or settings,
            runner=runner,
            which=which,
            http_get=http_get,
            sleep=sleep,
        )

    def publish(
        self,
        *,
        run_dir: Path,
        site_dir: Path,
        source_url: str,
        run_id: str,
    ) -> PreviewDeploymentResult:
        metadata_path = run_dir / "preview_deployment.json"
        preserve_verified_metadata = False
        if metadata_path.is_file():
            try:
                existing = json.loads(metadata_path.read_text(encoding="utf-8"))
                preserve_verified_metadata = (
                    existing.get("status") == "success"
                    and existing.get("verification_status") == "verified"
                    and existing.get("environment") == "preview"
                )
            except (OSError, ValueError, AttributeError):
                preserve_verified_metadata = False
        branch = preview_branch_name(run_id)
        provider = "cloudflare_pages_preview"
        try:
            expected_marker = stable_business_id(source_url)
            staging_dir, local_checks = prepare_preview_staging(
                run_dir=run_dir,
                site_dir=site_dir,
                expected_marker=expected_marker,
            )
            if not _has_business_marker(staging_dir / "index.html", expected_marker):
                raise SiteValidationError(
                    "Preview index.html does not contain the expected SiteAgent business marker."
                )

            project_name = preview_project_name(source_url, run_id)
            self._validate_configuration()
            self._check_toolchain()
            self._ensure_preview_project(project_name)
            deploy_result = self._run_wrangler(
                [
                    "pages",
                    "deploy",
                    str(staging_dir),
                    "--project-name",
                    project_name,
                    "--branch",
                    branch,
                ],
                purpose="isolated preview upload",
            )
            upload_url = self._deployment_url_from_output(deploy_result.stdout)
            deployment = self._latest_preview_deployment(project_name, upload_url, branch)
            deployment_url = self._deployment_url(deployment) or upload_url
            if not deployment_url:
                raise PublisherError(
                    "Wrangler completed the preview upload but returned no direct deployment URL."
                )
            self._assert_direct_preview_url(deployment_url, project_name)
            live_checks = PreviewLiveVerifier(
                http_get=self.http_get,
                sleep=self.sleep,
                retries=self.config.cloudflare_live_retries,
                backoff_seconds=self.config.cloudflare_live_backoff_seconds,
                timeout_seconds=self.config.cloudflare_live_timeout_seconds,
            ).verify(
                deployment_url,
                site_dir=staging_dir,
                expected_marker=expected_marker,
            )
            result = PreviewDeploymentResult(
                project_name=project_name,
                preview_url=deployment_url,
                deployment_url=deployment_url,
                deployment_id=self._deployment_id(deployment, deployment_url),
                branch=branch,
                deployed_at=self._deployment_timestamp(deployment) or _now(),
                staging_dir=str(staging_dir),
                checks={
                    **local_checks,
                    **live_checks,
                    "dedicated_project": project_name.startswith("siteagent-preview-"),
                    "non_production_branch": branch != PREVIEW_PRODUCTION_BRANCH,
                    "custom_domain_changed": False,
                    "telegram_delivery_sent": False,
                    "production_deployment_started": False,
                },
            )
            write_json(metadata_path, result)
            return result
        except Exception as exc:
            safe_message = self._redact(str(exc))
            write_json(
                (
                    metadata_path.with_name("preview_deployment_failure.json")
                    if preserve_verified_metadata
                    else metadata_path
                ),
                {
                    "provider": provider,
                    "status": "failed",
                    "verification_status": "failed",
                    "environment": "preview",
                    "branch": branch,
                    "error": safe_message,
                    "failed_at": _now(),
                    "production_deployment_started": False,
                    "custom_domain_changed": False,
                    "telegram_delivery_sent": False,
                },
            )
            if isinstance(exc, PublisherError) and safe_message == str(exc):
                raise
            raise PublisherError(safe_message) from exc

    def _validate_configuration(self) -> None:
        if not self.config.cloudflare_api_token.strip():
            raise PublisherConfigurationError(
                "CLOUDFLARE_API_TOKEN is required for Cloudflare Pages publishing."
            )
        if not self.config.cloudflare_account_id.strip():
            raise PublisherConfigurationError(
                "CLOUDFLARE_ACCOUNT_ID is required for Cloudflare Pages publishing."
            )
        super()._validate_configuration()

    def _ensure_preview_project(self, project_name: str) -> None:
        projects = self._list_projects()
        if any(self._project_name(project) == project_name for project in projects):
            return
        self._run_wrangler(
            [
                "pages",
                "project",
                "create",
                project_name,
                "--production-branch",
                PREVIEW_PRODUCTION_BRANCH,
            ],
            purpose="isolated preview project creation",
        )

    def _latest_preview_deployment(
        self,
        project_name: str,
        upload_url: str,
        branch: str,
    ) -> dict[str, Any]:
        result = self._run_wrangler(
            [
                "pages",
                "deployment",
                "list",
                "--project-name",
                project_name,
                "--environment",
                "preview",
                "--json",
            ],
            purpose="preview deployment listing",
        )
        deployments = self._as_object_list(
            self._parse_json(result.stdout, "preview deployment list"),
            "deployments",
        )
        candidates = [
            item
            for item in deployments
            if _deployment_environment(item) == "preview"
            and _deployment_branch(item) in ("", branch)
        ]
        if upload_url:
            matches = [item for item in candidates if self._deployment_url(item) == upload_url]
            if matches:
                return matches[0]
        if not candidates:
            raise PublisherError(
                "Cloudflare Pages did not report a preview-environment deployment after upload."
            )
        return max(candidates, key=lambda item: self._deployment_timestamp(item) or "")

    def _deployment_url(self, deployment: dict[str, Any]) -> str:
        value = super()._deployment_url(deployment)
        if value:
            return value
        human = deployment.get("Deployment")
        return self._as_https_url(str(human)) if human else ""

    def _deployment_id(self, deployment: dict[str, Any], deployment_url: str) -> str:
        human = deployment.get("Id")
        return str(human) if human else super()._deployment_id(deployment, deployment_url)

    def _assert_direct_preview_url(self, value: str, project_name: str) -> None:
        parsed = urlsplit(value)
        host = parsed.hostname or ""
        if host == f"{project_name}.pages.dev":
            raise PublisherError(
                "The stable project domain is not an acceptable preview deliverable."
            )
        if parsed.scheme != "https" or not host.endswith(f".{project_name}.pages.dev"):
            raise PublisherError(
                "Cloudflare did not return an isolated direct preview deployment URL."
            )


class PreviewLiveVerifier:
    def __init__(
        self,
        *,
        http_get: Callable[..., Any] = requests.get,
        sleep: Callable[[float], None] = time.sleep,
        retries: int = 5,
        backoff_seconds: float = 2.0,
        timeout_seconds: float = 15.0,
    ) -> None:
        self.http_get = http_get
        self.sleep = sleep
        self.retries = max(1, retries)
        self.backoff_seconds = max(0.0, backoff_seconds)
        self.timeout_seconds = timeout_seconds

    def verify(
        self,
        url: str,
        *,
        site_dir: Path,
        expected_marker: str,
    ) -> dict[str, Any]:
        if not url.startswith("https://"):
            raise LiveVerificationError("Preview URL must use https://.")
        last_error = "unknown preview verification error"
        for attempt in range(self.retries):
            try:
                return self._verify_once(
                    url,
                    site_dir=site_dir,
                    expected_marker=expected_marker,
                )
            except (LiveVerificationError, requests.RequestException) as exc:
                last_error = str(exc)
                if attempt + 1 < self.retries:
                    self.sleep(self.backoff_seconds * (2**attempt))
        raise LiveVerificationError(
            f"Cloudflare preview verification failed after {self.retries} attempts: "
            f"{last_error}"
        )

    def _verify_once(
        self,
        url: str,
        *,
        site_dir: Path,
        expected_marker: str,
    ) -> dict[str, Any]:
        root, _ = validate_site_directory(site_dir)
        html_paths = sorted(root.rglob("*.html"))
        checked_urls: list[str] = []
        for html_path in html_paths:
            route = _html_route(root, html_path)
            page_url = urljoin(url.rstrip("/") + "/", route)
            response = self.http_get(
                page_url,
                timeout=self.timeout_seconds,
                allow_redirects=True,
            )
            if response.status_code != 200:
                raise LiveVerificationError(
                    f"Preview page {route!r} returned HTTP {response.status_code}."
                )
            if "noindex" not in _header_value(response.headers, "x-robots-tag").lower():
                raise LiveVerificationError(
                    f"Preview page {route!r} is missing the X-Robots-Tag noindex header."
                )
            body = response.text or ""
            soup = BeautifulSoup(body, "html.parser")
            robots = soup.find("meta", attrs={"name": re.compile(r"^robots$", re.I)})
            if robots is None or "noindex" not in str(robots.get("content", "")).lower():
                raise LiveVerificationError(
                    f"Preview page {route!r} is missing noindex robots metadata."
                )
            if html_path == root / "index.html":
                marker = soup.find("meta", attrs={"name": "siteagent-business-id"})
                if marker is None or marker.get("content") != expected_marker:
                    raise LiveVerificationError(
                        "Preview HTML does not contain the expected SiteAgent business marker."
                    )
            checked_urls.append(page_url)

        robots_response = self.http_get(
            urljoin(url.rstrip("/") + "/", "robots.txt"),
            timeout=self.timeout_seconds,
            allow_redirects=True,
        )
        if robots_response.status_code != 200 or "Disallow: /" not in (robots_response.text or ""):
            raise LiveVerificationError("Preview robots.txt does not block all crawlers.")
        return {
            "live_http_verified": True,
            "live_html_pages_checked": len(html_paths),
            "live_page_urls": checked_urls,
            "live_x_robots_tag_verified": True,
            "live_robots_txt_verified": True,
        }


def prepare_preview_staging(
    *, run_dir: Path, site_dir: Path, expected_marker: str = ""
) -> tuple[Path, dict[str, Any]]:
    source, _ = validate_site_directory(site_dir)
    run_root = run_dir.expanduser().resolve()
    run_root.mkdir(parents=True, exist_ok=True)
    target = (run_root / "preview_publish").resolve()
    if not target.is_relative_to(run_root) or target == run_root:
        raise SiteValidationError("Preview staging path must stay inside the run directory.")
    if source == target or source.is_relative_to(target) or target.is_relative_to(source):
        raise SiteValidationError("Accepted site cannot be the preview staging directory.")
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)

    html_paths = sorted(target.rglob("*.html"))
    if not html_paths:
        raise SiteValidationError("Preview staging contains no HTML files.")
    for html_path in html_paths:
        _protect_html(
            html_path,
            expected_marker=expected_marker if html_path == target / "index.html" else "",
        )
    (target / "robots.txt").write_text(
        "User-agent: *\nDisallow: /\n",
        encoding="utf-8",
    )
    _write_preview_headers(target / "_headers")
    validate_site_directory(target)
    return target, {
        "local_html_pages_protected": len(html_paths),
        "local_robots_meta_verified": all(_has_noindex(path) for path in html_paths),
        "local_robots_txt_verified": True,
        "local_x_robots_headers_configured": True,
    }


def preview_project_name(source_url: str, run_id: str) -> str:
    # Remove tracking/query components before adding the run identity; appending
    # directly to a URL containing `?igsh=` would put the run id inside the
    # discarded query and accidentally reuse one project across preview runs.
    parsed = urlsplit(source_url if "://" in source_url else "https://" + source_url)
    source_base = f"https://{parsed.hostname or 'instagram.com'}{parsed.path.rstrip('/')}"
    identity_url = source_base + "/preview-run/" + _slug(run_id, fallback="run")
    name = cloudflare_project_name(PREVIEW_PROJECT_PREFIX, identity_url)
    if not name.startswith("siteagent-preview-"):
        raise ValueError("Preview project naming invariant failed.")
    return name


def preview_branch_name(run_id: str) -> str:
    return f"{PREVIEW_BRANCH_PREFIX}-{_slug(run_id, fallback='run')[:36]}"


def _protect_html(path: Path, *, expected_marker: str = "") -> None:
    raw = path.read_text(encoding="utf-8")
    soup = BeautifulSoup(raw, "html.parser")
    if soup.html is None:
        raise SiteValidationError(f"Preview HTML is not a document: {path.name}")
    if soup.head is None:
        head = soup.new_tag("head")
        soup.html.insert(0, head)
    else:
        head = soup.head
    for existing in soup.find_all("meta", attrs={"name": re.compile(r"^robots$", re.I)}):
        existing.decompose()
    robots = soup.new_tag("meta")
    robots["name"] = "robots"
    robots["content"] = ROBOTS_CONTENT
    head.append(robots)
    if expected_marker:
        for existing in soup.find_all("meta", attrs={"name": "siteagent-business-id"}):
            existing.decompose()
        marker = soup.new_tag("meta")
        marker["name"] = "siteagent-business-id"
        marker["content"] = expected_marker
        head.append(marker)
    rendered = str(soup)
    if raw.lstrip().lower().startswith("<!doctype") and not rendered.lstrip().lower().startswith(
        "<!doctype"
    ):
        rendered = "<!doctype html>\n" + rendered
    path.write_text(rendered, encoding="utf-8")


def _write_preview_headers(path: Path) -> None:
    existing = path.read_text(encoding="utf-8") if path.is_file() else ""
    preview_rule = (
        "/*\n"
        f"  X-Robots-Tag: {X_ROBOTS_CONTENT}\n"
        "  Cache-Control: no-store\n"
    )
    if existing and not existing.endswith("\n"):
        existing += "\n"
    for line in existing.splitlines():
        if "x-robots-tag:" in line.lower() and "noindex" not in line.lower():
            raise SiteValidationError("Existing _headers contains an unsafe X-Robots-Tag rule.")
    if X_ROBOTS_CONTENT.lower() not in existing.lower():
        existing += preview_rule
    path.write_text(existing or preview_rule, encoding="utf-8")


def _has_noindex(path: Path) -> bool:
    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    robots = soup.find("meta", attrs={"name": re.compile(r"^robots$", re.I)})
    return robots is not None and "noindex" in str(robots.get("content", "")).lower()


def _has_business_marker(path: Path, expected_marker: str) -> bool:
    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    marker = soup.find("meta", attrs={"name": "siteagent-business-id"})
    return marker is not None and marker.get("content") == expected_marker


def _html_route(root: Path, path: Path) -> str:
    relative = path.relative_to(root).as_posix()
    if relative == "index.html":
        return ""
    if relative.endswith("/index.html"):
        return relative[: -len("index.html")]
    return relative


def _deployment_environment(deployment: dict[str, Any]) -> str:
    environment = deployment.get("environment", deployment.get("Environment", ""))
    if isinstance(environment, dict):
        environment = environment.get("name", "")
    return str(environment).lower()


def _deployment_branch(deployment: dict[str, Any]) -> str:
    for key in ("branch", "Branch", "source_branch", "sourceBranch"):
        value = deployment.get(key)
        if value:
            return str(value)
    source = deployment.get("source")
    if isinstance(source, dict):
        return str(source.get("branch", ""))
    return ""


def _header_value(headers: Any, name: str) -> str:
    if hasattr(headers, "get"):
        value = headers.get(name)
        if value is None:
            value = headers.get(name.title())
        if value is not None:
            return str(value)
    return ""


def _slug(value: str, *, fallback: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or fallback


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
