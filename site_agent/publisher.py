from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from site_agent.config import Settings, settings
from site_agent.identifiers import cloudflare_project_name, stable_business_id
from site_agent.json_io import write_json
from site_agent.models import DeploymentResult
from site_agent.studio import StudioError, assert_production_promotion_allowed


MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024
MAX_FILE_COUNT = 20_000
PROJECT_CREATE_ATTEMPTS = 4


class PublisherError(RuntimeError):
    pass


class PublisherConfigurationError(PublisherError):
    pass


class SiteValidationError(PublisherError):
    pass


class PublisherCommandError(PublisherError):
    pass


class LiveVerificationError(PublisherError):
    pass


class Publisher:
    """Single provider dispatcher used by the generation pipeline."""

    def __init__(self, config: Settings | None = None, **cloudflare_dependencies: Any) -> None:
        self.config = config or settings
        self.cloudflare_dependencies = cloudflare_dependencies

    def publish(
        self,
        *,
        run_dir: Path,
        site_dir: Path,
        instagram_url: str,
        production: bool = False,
    ) -> DeploymentResult:
        provider = self.config.hosting_provider.strip().lower()
        try:
            # The orchestrator is the usual gate owner, but callers can invoke
            # this facade directly during recovery.  Recheck when this is a
            # Studio run so a resume cannot upload fixture media around it.
            studio_dir = run_dir / "studio"
            if production and (studio_dir / "input" / "media_manifest.json").is_file():
                try:
                    assert_production_promotion_allowed(studio_dir=studio_dir, site_dir=site_dir)
                except StudioError as exc:
                    raise PublisherConfigurationError(str(exc)) from exc
            if production and provider != "cloudflare_pages":
                raise PublisherConfigurationError(
                    "Telegram production jobs require HOSTING_PROVIDER=cloudflare_pages. "
                    "Local preview and the legacy Git publisher are not production fallbacks."
                )
            if provider == "cloudflare_pages":
                result = CloudflarePagesPublisher(
                    self.config, **self.cloudflare_dependencies
                ).publish(site_dir=site_dir, instagram_url=instagram_url)
            elif provider == "local":
                if self.config.publish_required or production:
                    raise PublisherConfigurationError(
                        "HOSTING_PROVIDER=local is allowed only with PUBLISH_REQUIRED=false "
                        "for explicit manual preview runs."
                    )
                result = LocalPublisher().publish(site_dir=site_dir)
            elif provider in {"git", "github_pages"}:
                result = GitPublisher(self.config).publish(run_dir=run_dir, site_dir=site_dir)
            else:
                raise PublisherConfigurationError(
                    f"Unsupported HOSTING_PROVIDER={provider!r}. Choose cloudflare_pages, local, or git."
                )
        except Exception as exc:
            safe_message = self._redact(str(exc))
            write_json(
                run_dir / "deployment.json",
                {
                    "provider": provider or "unknown",
                    "status": "failed",
                    "verification_status": "failed",
                    "error": safe_message,
                    "failed_at": _now(),
                },
            )
            if isinstance(exc, PublisherError) and safe_message == str(exc):
                raise
            raise PublisherError(safe_message) from exc
        write_json(run_dir / "deployment.json", result)
        return result

    def _redact(self, value: str) -> str:
        for secret in (
            self.config.cloudflare_api_token,
            self.config.cloudflare_account_id,
            self.config.publish_remote_url,
        ):
            if secret:
                value = value.replace(secret, "[REDACTED]")
        return re.sub(r"Bearer\s+\S+", "Bearer [REDACTED]", value, flags=re.IGNORECASE)


class LocalPublisher:
    def publish(self, *, site_dir: Path) -> DeploymentResult:
        validate_site_directory(site_dir)
        url = (site_dir / "index.html").resolve().as_uri()
        return DeploymentResult(
            provider="local",
            production_url=url,
            deployment_url=url,
            status="local_preview",
            deployed_at=_now(),
            verification_status="not_required",
        )


class GitPublisher:
    """Deprecated explicit provider retained for existing manual workflows."""

    def __init__(self, config: Settings) -> None:
        self.config = config

    def publish(self, *, run_dir: Path, site_dir: Path) -> DeploymentResult:
        validate_site_directory(site_dir)
        if not self.config.publish_remote_url:
            raise PublisherConfigurationError(
                "PUBLISH_REMOTE_URL is required when HOSTING_PROVIDER=git."
            )
        repo_dir = run_dir / "publish_repo"
        if repo_dir.exists():
            shutil.rmtree(repo_dir)
        repo_dir.mkdir(parents=True)
        self._copy_site(site_dir, repo_dir)
        self._copy_reports(run_dir, repo_dir)
        self._git(repo_dir, "init")
        self._git(repo_dir, "checkout", "-B", self.config.publish_branch)
        self._git(repo_dir, "remote", "add", "origin", self.config.publish_remote_url)
        self._git(repo_dir, "add", ".")
        self._git(repo_dir, "commit", "-m", "Publish generated site")
        self._git(repo_dir, "push", "-f", "origin", self.config.publish_branch)
        site_url = self._pages_url()
        return DeploymentResult(
            provider="git",
            project_name=Path(urlsplit(self.config.public_repo_url).path).name,
            production_url=site_url,
            deployment_url=site_url,
            status="success",
            deployed_at=_now(),
            verification_status="not_required",
            repo_url=self.config.public_repo_url or self.config.publish_remote_url,
        )

    def _copy_site(self, site_dir: Path, repo_dir: Path) -> None:
        for item in site_dir.iterdir():
            target = repo_dir / item.name
            if item.is_dir():
                shutil.copytree(item, target)
            else:
                shutil.copy2(item, target)

    def _copy_reports(self, run_dir: Path, repo_dir: Path) -> None:
        for name in ("generation_reports", "critique_reports"):
            source = run_dir / name
            if source.exists():
                shutil.copytree(source, repo_dir / name)

    def _git(self, cwd: Path, *args: str) -> None:
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=cwd,
                text=True,
                capture_output=True,
                check=False,
                timeout=self.config.cloudflare_command_timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            raise PublisherCommandError("Legacy Git publisher command timed out.") from exc
        if result.returncode != 0:
            output = result.stderr or result.stdout or "unknown git error"
            if self.config.publish_remote_url:
                output = output.replace(self.config.publish_remote_url, "[REDACTED]")
            raise PublisherCommandError(f"Legacy Git publisher failed: {output.strip()}")

    def _pages_url(self) -> str:
        if self.config.public_repo_url and "github.com" in self.config.public_repo_url:
            parts = self.config.public_repo_url.rstrip("/").split("/")
            if len(parts) >= 2:
                owner = parts[-2]
                repo = parts[-1].removesuffix(".git")
                return f"https://{owner}.github.io/{repo}/"
        return self.config.public_repo_url or self.config.publish_remote_url


class CloudflarePagesPublisher:
    def __init__(
        self,
        config: Settings,
        *,
        runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
        which: Callable[[str], str | None] = shutil.which,
        http_get: Callable[..., Any] = requests.get,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.config = config
        self.runner = runner
        self.which = which
        self.http_get = http_get
        self.sleep = sleep
        self.npx_path = ""

    def publish(self, *, site_dir: Path, instagram_url: str) -> DeploymentResult:
        root, _ = validate_site_directory(site_dir)
        self._validate_configuration()
        self._check_toolchain()
        expected_marker = stable_business_id(instagram_url)
        index_html = (root / "index.html").read_text(encoding="utf-8")
        if expected_marker not in index_html:
            raise SiteValidationError(
                "site/index.html does not contain the expected siteagent business marker; "
                "rebuild the site before publishing."
            )
        projects = self._list_projects()
        project = self._find_or_create_project(projects, instagram_url, expected_marker)
        project_name = self._project_name(project)
        deploy_result = self._run_wrangler(
            [
                "pages",
                "deploy",
                str(root),
                "--project-name",
                project_name,
                "--branch",
                self.config.cloudflare_pages_production_branch,
            ],
            purpose="site upload",
        )
        upload_url = self._deployment_url_from_output(deploy_result.stdout)
        deployment = self._latest_production_deployment(project_name, upload_url)
        deployment_url = self._deployment_url(deployment) or upload_url
        if not deployment_url:
            raise PublisherError(
                "Wrangler completed the upload but no deployment URL was returned or listed."
            )
        production_url = self._stable_production_url(project, project_name)
        LiveSiteVerifier(
            http_get=self.http_get,
            sleep=self.sleep,
            retries=self.config.cloudflare_live_retries,
            backoff_seconds=self.config.cloudflare_live_backoff_seconds,
            timeout_seconds=self.config.cloudflare_live_timeout_seconds,
        ).verify(production_url, site_dir=root, expected_marker=expected_marker)
        return DeploymentResult(
            provider="cloudflare_pages",
            project_name=project_name,
            production_url=production_url,
            deployment_url=deployment_url,
            deployment_id=self._deployment_id(deployment, deployment_url),
            status="success",
            deployed_at=self._deployment_timestamp(deployment) or _now(),
            verification_status="verified",
        )

    def _validate_configuration(self) -> None:
        if not self.config.cloudflare_api_token:
            raise PublisherConfigurationError(
                "CLOUDFLARE_API_TOKEN is required for Cloudflare Pages publishing."
            )
        if not self.config.cloudflare_account_id:
            raise PublisherConfigurationError(
                "CLOUDFLARE_ACCOUNT_ID is required for Cloudflare Pages publishing."
            )
        if not self.config.cloudflare_pages_production_branch.strip():
            raise PublisherConfigurationError(
                "CLOUDFLARE_PAGES_PRODUCTION_BRANCH must not be empty."
            )

    def _check_toolchain(self) -> None:
        missing = [command for command in ("node", "npm", "npx") if not self.which(command)]
        if missing:
            raise PublisherConfigurationError(
                f"Required deployment command(s) not found: {', '.join(missing)}. Install the current "
                "Node.js LTS release from https://nodejs.org/ (npm and npx are included), "
                "then reopen the terminal."
            )
        self.npx_path = self.which("npx") or "npx"

    def _list_projects(self) -> list[dict[str, Any]]:
        result = self._run_wrangler(
            ["pages", "project", "list", "--json"], purpose="project listing"
        )
        return self._as_object_list(self._parse_json(result.stdout, "project list"), "projects")

    def _find_or_create_project(
        self,
        projects: list[dict[str, Any]],
        instagram_url: str,
        expected_marker: str,
    ) -> dict[str, Any]:
        by_name = {self._project_name(project): project for project in projects}
        for collision in range(PROJECT_CREATE_ATTEMPTS):
            candidate = cloudflare_project_name(
                self.config.cloudflare_project_prefix,
                instagram_url,
                collision=collision,
            )
            existing = by_name.get(candidate)
            if existing:
                if self._project_belongs_to_business(existing, expected_marker):
                    return existing
                continue
            try:
                self._run_wrangler(
                    [
                        "pages",
                        "project",
                        "create",
                        candidate,
                        "--production-branch",
                        self.config.cloudflare_pages_production_branch,
                    ],
                    purpose="project creation",
                )
            except PublisherCommandError as exc:
                if not self._is_name_rejection(str(exc)):
                    raise
                refreshed = self._list_projects()
                by_name.update({self._project_name(item): item for item in refreshed})
                raced = by_name.get(candidate)
                if raced and self._project_belongs_to_business(raced, expected_marker):
                    return raced
                continue
            refreshed = self._list_projects()
            created = next(
                (item for item in refreshed if self._project_name(item) == candidate), None
            )
            return created or {"name": candidate, "subdomain": f"{candidate}.pages.dev"}
        raise PublisherError(
            "Could not allocate a safe Cloudflare Pages project name after "
            f"{PROJECT_CREATE_ATTEMPTS} attempts. Change CLOUDFLARE_PROJECT_PREFIX and retry."
        )

    def _project_belongs_to_business(
        self, project: dict[str, Any], expected_marker: str
    ) -> bool:
        has_deployment_signal = bool(
            project.get("latest_deployment") or project.get("domains") or project.get("subdomain")
        )
        if not has_deployment_signal:
            return True
        url = self._stable_production_url(project, self._project_name(project))
        try:
            response = self.http_get(
                url,
                timeout=self.config.cloudflare_live_timeout_seconds,
                allow_redirects=True,
            )
        except requests.RequestException:
            return False
        if response.status_code == 404 and not project.get("latest_deployment"):
            return True
        return response.status_code == 200 and expected_marker in (response.text or "")

    def _latest_production_deployment(
        self, project_name: str, upload_url: str
    ) -> dict[str, Any]:
        result = self._run_wrangler(
            [
                "pages",
                "deployment",
                "list",
                "--project-name",
                project_name,
                "--environment",
                "production",
                "--json",
            ],
            purpose="deployment listing",
        )
        deployments = self._as_object_list(
            self._parse_json(result.stdout, "deployment list"), "deployments"
        )
        production = [item for item in deployments if self._is_production_deployment(item)]
        if not production:
            raise PublisherError(
                "Cloudflare Pages did not report a production deployment after upload."
            )
        if upload_url:
            matching = [item for item in production if self._deployment_url(item) == upload_url]
            if matching:
                return matching[0]
        return max(production, key=lambda item: self._deployment_timestamp(item) or "")

    def _run_wrangler(
        self, args: list[str], *, purpose: str
    ) -> subprocess.CompletedProcess[str]:
        command = [
            self.npx_path or "npx",
            "--yes",
            self.config.cloudflare_wrangler_package,
            *args,
        ]
        env = os.environ.copy()
        env["CLOUDFLARE_ACCOUNT_ID"] = self.config.cloudflare_account_id
        env["CLOUDFLARE_API_TOKEN"] = self.config.cloudflare_api_token
        env["CI"] = "1"
        env["FORCE_COLOR"] = "0"
        # Do not set WRANGLER_LOG=none: Wrangler 4.110 suppresses successful
        # machine-readable command output at that level, including --json.
        env.pop("WRANGLER_LOG", None)
        env["WRANGLER_SEND_METRICS"] = "false"
        env["WRANGLER_SEND_ERROR_REPORTS"] = "false"
        try:
            result = self.runner(
                command,
                cwd=Path.cwd(),
                env=env,
                text=True,
                capture_output=True,
                check=False,
                timeout=self.config.cloudflare_command_timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            raise PublisherCommandError(
                f"Cloudflare Pages {purpose} timed out after "
                f"{self.config.cloudflare_command_timeout_seconds} seconds."
            ) from exc
        except FileNotFoundError as exc:
            raise PublisherConfigurationError(
                "npx could not be started. Install the current Node.js LTS release from "
                "https://nodejs.org/ and reopen the terminal."
            ) from exc
        except OSError as exc:
            raise PublisherCommandError(
                f"Cloudflare Pages {purpose} could not start: {self._redact(str(exc))}"
            ) from exc
        if result.returncode != 0:
            output = (result.stderr or result.stdout or "Wrangler returned no error details").strip()
            raise PublisherCommandError(
                f"Cloudflare Pages {purpose} failed: {self._redact(output)[:4000]}"
            )
        return result

    def _parse_json(self, output: str, label: str) -> Any:
        stripped = output.strip()
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            decoder = json.JSONDecoder()
            for index, char in enumerate(stripped):
                if char not in "[{":
                    continue
                try:
                    value, _ = decoder.raw_decode(stripped[index:])
                    return value
                except json.JSONDecodeError:
                    continue
        raise PublisherError(f"Wrangler {label} did not return valid JSON.")

    def _as_object_list(self, payload: Any, key: str) -> list[dict[str, Any]]:
        if isinstance(payload, dict):
            payload = payload.get("result", payload.get(key, payload.get("data", [])))
        if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
            raise PublisherError(f"Wrangler {key} JSON has an unexpected shape.")
        return payload

    def _project_name(self, project: dict[str, Any]) -> str:
        for key in ("name", "project_name", "projectName", "Project Name"):
            value = project.get(key)
            if isinstance(value, str) and value:
                return value
        return ""

    def _stable_production_url(self, project: dict[str, Any], project_name: str) -> str:
        subdomain = project.get("subdomain")
        if isinstance(subdomain, str) and subdomain:
            return self._as_https_url(subdomain)
        domains = project.get("domains")
        if isinstance(domains, list):
            pages_domains = [str(item) for item in domains if str(item).endswith(".pages.dev")]
            if pages_domains:
                domain = min(pages_domains, key=lambda item: (item.count("."), len(item)))
                return self._as_https_url(domain)
        return f"https://{project_name}.pages.dev"

    def _deployment_url(self, deployment: dict[str, Any]) -> str:
        for key in ("url", "deployment_url", "deploymentUrl"):
            value = deployment.get(key)
            if isinstance(value, str) and value:
                return self._as_https_url(value)
        aliases = deployment.get("aliases")
        if isinstance(aliases, list) and aliases:
            return self._as_https_url(str(aliases[0]))
        return ""

    def _deployment_id(self, deployment: dict[str, Any], deployment_url: str) -> str:
        for key in ("id", "deployment_id", "deploymentId"):
            value = deployment.get(key)
            if value:
                return str(value)
        return (urlsplit(deployment_url).hostname or "").split(".")[0]

    def _deployment_timestamp(self, deployment: dict[str, Any]) -> str:
        for key in ("created_on", "created_at", "createdAt", "modified_on"):
            value = deployment.get(key)
            if value:
                return str(value)
        return ""

    def _is_production_deployment(self, deployment: dict[str, Any]) -> bool:
        environment = deployment.get("environment")
        if isinstance(environment, dict):
            environment = environment.get("name")
        return environment in (None, "", "production")

    def _deployment_url_from_output(self, output: str) -> str:
        urls = re.findall(r"https://[^\s\]\[<>\"']+\.pages\.dev", output)
        return urls[-1].rstrip(".,)") if urls else ""

    def _is_name_rejection(self, message: str) -> bool:
        normalized = message.lower()
        return any(
            marker in normalized
            for marker in (
                "already exists",
                "already taken",
                "not available",
                "project name",
                "invalid name",
            )
        )

    def _as_https_url(self, value: str) -> str:
        return value if value.startswith("https://") else "https://" + value.lstrip("/")

    def _redact(self, value: str) -> str:
        for secret in (self.config.cloudflare_api_token, self.config.cloudflare_account_id):
            if secret:
                value = value.replace(secret, "[REDACTED]")
        return re.sub(r"Bearer\s+\S+", "Bearer [REDACTED]", value, flags=re.IGNORECASE)


class LiveSiteVerifier:
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

    def verify(self, url: str, *, site_dir: Path, expected_marker: str) -> None:
        if not url.startswith("https://"):
            raise LiveVerificationError("Production URL must use https://.")
        last_error = "unknown live verification error"
        for attempt in range(self.retries):
            try:
                self._verify_once(url, site_dir=site_dir, expected_marker=expected_marker)
                return
            except (LiveVerificationError, requests.RequestException) as exc:
                last_error = str(exc)
                if attempt + 1 < self.retries:
                    self.sleep(self.backoff_seconds * (2**attempt))
        raise LiveVerificationError(
            f"Cloudflare Pages live verification failed after {self.retries} attempts: {last_error}"
        )

    def _verify_once(self, url: str, *, site_dir: Path, expected_marker: str) -> None:
        response = self.http_get(url, timeout=self.timeout_seconds, allow_redirects=True)
        if response.status_code != 200:
            raise LiveVerificationError(
                f"Production URL returned HTTP {response.status_code}, expected 200."
            )
        body = response.text or ""
        if not body.strip():
            raise LiveVerificationError("Production URL returned an empty response body.")
        content_type = (response.headers.get("content-type", "") or "").lower()
        if content_type and "html" not in content_type:
            raise LiveVerificationError(
                f"Production URL returned {content_type!r}, expected HTML."
            )
        soup = BeautifulSoup(body, "html.parser")
        if soup.find("html") is None:
            raise LiveVerificationError("Production response is not an HTML document.")
        marker = soup.find("meta", attrs={"name": "siteagent-business-id"})
        if marker is None or marker.get("content") != expected_marker:
            raise LiveVerificationError("Production HTML does not contain the expected site marker.")
        lowered = body.lower()
        cloudflare_errors = (
            "cloudflare ray id",
            "error code:",
            "web server is down",
            "direct ip access not allowed",
            "attention required! | cloudflare",
        )
        if any(error in lowered for error in cloudflare_errors):
            raise LiveVerificationError("Production URL returned a Cloudflare error page.")
        self._verify_local_assets(url, soup, site_dir)

    def _verify_local_assets(self, page_url: str, soup: BeautifulSoup, site_dir: Path) -> None:
        local_refs: list[str] = []
        for tag, attribute in (("img", "src"), ("script", "src"), ("link", "href")):
            for element in soup.find_all(tag):
                value = element.get(attribute)
                if not isinstance(value, str) or not value:
                    continue
                parsed = urlsplit(value)
                if parsed.scheme or parsed.netloc or value.startswith(("#", "data:")):
                    continue
                candidate = (site_dir / parsed.path.lstrip("/")).resolve()
                if candidate.is_file() and candidate != (site_dir / "index.html").resolve():
                    local_refs.append(value)
        for asset_ref in dict.fromkeys(local_refs):
            response = self.http_get(
                urljoin(page_url, asset_ref),
                timeout=self.timeout_seconds,
                allow_redirects=True,
            )
            if response.status_code != 200:
                raise LiveVerificationError(
                    f"Published asset {asset_ref!r} returned HTTP {response.status_code}."
                )


def validate_site_directory(site_dir: Path) -> tuple[Path, list[Path]]:
    try:
        root = site_dir.expanduser().resolve(strict=True)
    except FileNotFoundError as exc:
        raise SiteValidationError(f"Site directory does not exist: {site_dir}") from exc
    if not root.is_dir():
        raise SiteValidationError(f"Site path is not a directory: {root}")
    entries = list(root.rglob("*"))
    files = [entry for entry in entries if entry.is_file()]
    if not files:
        raise SiteValidationError(f"Site directory is empty: {root}")
    if not (root / "index.html").is_file():
        raise SiteValidationError(f"Site directory is missing index.html: {root}")
    if len(files) > MAX_FILE_COUNT:
        raise SiteValidationError(
            f"Site contains {len(files)} files; Cloudflare Pages allows at most {MAX_FILE_COUNT}."
        )
    for entry in entries:
        relative = entry.relative_to(root)
        if entry.is_symlink():
            raise SiteValidationError(f"Symlinks are not allowed in published sites: {relative}")
        try:
            resolved = entry.resolve(strict=True)
        except OSError as exc:
            raise SiteValidationError(f"Could not resolve site path {relative}: {exc}") from exc
        if not resolved.is_relative_to(root):
            raise SiteValidationError(f"Site path escapes the publish directory: {relative}")
    for path in files:
        relative = path.relative_to(root)
        _validate_publishable_name(relative)
        size = path.stat().st_size
        if size > MAX_FILE_SIZE_BYTES:
            raise SiteValidationError(
                f"File {relative} is {size / (1024 * 1024):.2f} MiB; the Cloudflare Pages "
                f"limit is {MAX_FILE_SIZE_BYTES / (1024 * 1024):.0f} MiB. Optimize the file "
                "or move heavy media to external storage."
            )
    return root, files


def _validate_publishable_name(relative: Path) -> None:
    lowered_parts = [part.lower() for part in relative.parts]
    forbidden_parts = {
        ".git",
        ".codex",
        ".env",
        ".dev.vars",
        "credentials",
        "generation_reports",
        "critique_reports",
        "reports",
        "telegram_jobs.json",
        "deployment.json",
    }
    if any(part in forbidden_parts or part.startswith(".env.") for part in lowered_parts):
        raise SiteValidationError(f"Sensitive or internal file is not publishable: {relative}")
    filename = lowered_parts[-1]
    if filename.endswith((".pem", ".key", ".p12", ".pfx")):
        raise SiteValidationError(f"Credential file is not publishable: {relative}")
    if re.match(r"^(prompt|research|strategy|critique|site[_-]?spec|report)([-_.]|$)", filename):
        raise SiteValidationError(f"Internal prompt/report file is not publishable: {relative}")
    if "credential" in filename or "secret" in filename:
        raise SiteValidationError(f"Potential credential file is not publishable: {relative}")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
