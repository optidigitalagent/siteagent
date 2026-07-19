from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from site_agent.config import Settings
from site_agent.identifiers import stable_business_id
from site_agent.preview import (
    PREVIEW_PRODUCTION_BRANCH,
    PreviewLiveVerifier,
    PreviewPublisher,
    prepare_preview_staging,
    preview_branch_name,
    preview_project_name,
)
from site_agent.publisher import LiveVerificationError, PublisherError


SOURCE_URL = "https://www.instagram.com/example_business/?igsh=tracking"
RUN_ID = "f684eed531f74dd8995b2a58ac77739e"


class FakeResponse:
    def __init__(self, text: str, *, status_code: int = 200, headers: dict | None = None):
        self.status_code = status_code
        self.text = text
        self.headers = headers or {
            "content-type": "text/html; charset=utf-8",
            "x-robots-tag": "noindex, nofollow, noarchive, nosnippet",
        }


class ScriptedRunner:
    def __init__(self, responses: list[subprocess.CompletedProcess[str]]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[list[str], dict]] = []

    def __call__(self, command: list[str], **kwargs):
        self.calls.append((command, kwargs))
        return self.responses.pop(0)


def completed(stdout: str = "", stderr: str = "", returncode: int = 0):
    return subprocess.CompletedProcess(["npx"], returncode, stdout, stderr)


def config() -> Settings:
    return Settings(
        _env_file=None,
        HOSTING_PROVIDER="cloudflare_pages",
        PUBLISH_REQUIRED=True,
        CLOUDFLARE_ACCOUNT_ID="account-id",
        CLOUDFLARE_API_TOKEN="preview-secret-token",
        CLOUDFLARE_LIVE_RETRIES=1,
        CLOUDFLARE_LIVE_BACKOFF_SECONDS=0,
        CLOUDFLARE_COMMAND_TIMEOUT_SECONDS=10,
    )


def make_site(root: Path) -> Path:
    site = root / "accepted_site"
    (site / "services").mkdir(parents=True)
    marker = stable_business_id(SOURCE_URL)
    (site / "index.html").write_text(
        "<!doctype html><html><head>"
        '<meta name="robots" content="index,follow">'
        f'<meta name="siteagent-business-id" content="{marker}">'
        "</head><body>Accepted home</body></html>",
        encoding="utf-8",
    )
    (site / "services" / "index.html").write_text(
        "<!doctype html><html><body>Services</body></html>",
        encoding="utf-8",
    )
    return site


def protected_html(*, marker: bool) -> str:
    marker_html = (
        f'<meta name="siteagent-business-id" content="{stable_business_id(SOURCE_URL)}">'
        if marker
        else ""
    )
    return (
        "<!doctype html><html><head>"
        '<meta name="robots" content="noindex,nofollow,noarchive,nosnippet">'
        f"{marker_html}</head><body>Preview</body></html>"
    )


class PreviewStagingTests(unittest.TestCase):
    def test_staging_copies_site_and_protects_every_html(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            site = make_site(root)
            staging, checks = prepare_preview_staging(run_dir=root / "run", site_dir=site)

            self.assertNotEqual(staging, site)
            self.assertEqual(checks["local_html_pages_protected"], 2)
            self.assertTrue(checks["local_robots_meta_verified"])
            for html_path in staging.rglob("*.html"):
                rendered = html_path.read_text(encoding="utf-8").lower()
                self.assertIn('name="robots"', rendered)
                self.assertIn("noindex", rendered)
                self.assertNotIn("index,follow", rendered)
            self.assertEqual(
                (staging / "robots.txt").read_text(encoding="utf-8"),
                "User-agent: *\nDisallow: /\n",
            )
            headers = (staging / "_headers").read_text(encoding="utf-8")
            self.assertIn("X-Robots-Tag: noindex, nofollow", headers)
            self.assertIn("Cache-Control: no-store", headers)
            self.assertFalse((site / "robots.txt").exists())

    def test_staging_injects_exact_business_meta_instead_of_accepting_asset_path_match(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            site = make_site(root)
            index = site / "index.html"
            index.write_text(
                "<!doctype html><html><head></head><body>"
                f"<img src='/assets/{stable_business_id(SOURCE_URL)}/photo.jpg'>"
                "</body></html>",
                encoding="utf-8",
            )

            staging, _ = prepare_preview_staging(
                run_dir=root / "run",
                site_dir=site,
                expected_marker=stable_business_id(SOURCE_URL),
            )

            rendered = (staging / "index.html").read_text(encoding="utf-8")
            self.assertIn('name="siteagent-business-id"', rendered)
            self.assertIn(f'content="{stable_business_id(SOURCE_URL)}"', rendered)

    def test_project_and_branch_are_isolated_by_run(self) -> None:
        first = preview_project_name(SOURCE_URL, RUN_ID)
        second = preview_project_name(SOURCE_URL, "another-run")
        self.assertTrue(first.startswith("siteagent-preview-"))
        self.assertNotEqual(first, second)
        self.assertNotEqual(preview_branch_name(RUN_ID), PREVIEW_PRODUCTION_BRANCH)


class PreviewPublisherTests(unittest.TestCase):
    def test_failed_retry_preserves_existing_verified_preview_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run_dir = root / "run"
            run_dir.mkdir()
            verified = {
                "provider": "cloudflare_pages_preview",
                "project_name": "siteagent-preview-existing",
                "preview_url": "https://hash.siteagent-preview-existing.pages.dev",
                "deployment_url": "https://hash.siteagent-preview-existing.pages.dev",
                "branch": "preview-existing",
                "environment": "preview",
                "status": "success",
                "deployed_at": "2026-07-18T12:00:00+00:00",
                "verification_status": "verified",
                "staging_dir": "preview_publish",
            }
            metadata_path = run_dir / "preview_deployment.json"
            metadata_path.write_text(json.dumps(verified), encoding="utf-8")
            no_credentials = Settings(
                _env_file=None,
                HOSTING_PROVIDER="cloudflare_pages",
                PUBLISH_REQUIRED=True,
                CLOUDFLARE_ACCOUNT_ID="",
                CLOUDFLARE_API_TOKEN="",
            )

            with self.assertRaisesRegex(PublisherError, "CLOUDFLARE_API_TOKEN"):
                PreviewPublisher(
                    no_credentials,
                    runner=ScriptedRunner([]),
                    which=lambda command: self.fail("toolchain lookup must not run"),
                ).publish(
                    run_dir=run_dir,
                    site_dir=make_site(root),
                    source_url=SOURCE_URL,
                    run_id=RUN_ID,
                )

            self.assertEqual(json.loads(metadata_path.read_text(encoding="utf-8")), verified)
            failure = json.loads(
                (run_dir / "preview_deployment_failure.json").read_text(encoding="utf-8")
            )
            self.assertEqual(failure["status"], "failed")
            self.assertFalse(failure["production_deployment_started"])

    def test_missing_or_incomplete_pages_credentials_fail_closed_without_runner(self) -> None:
        cases = (
            ("both missing", "", "", "CLOUDFLARE_API_TOKEN"),
            ("token missing", "account-id", "", "CLOUDFLARE_API_TOKEN"),
            ("account missing", "", "preview-secret-token", "CLOUDFLARE_ACCOUNT_ID"),
            ("token whitespace", "account-id", "   ", "CLOUDFLARE_API_TOKEN"),
            ("account whitespace", "   ", "preview-secret-token", "CLOUDFLARE_ACCOUNT_ID"),
        )
        for label, account_id, api_token, expected_error in cases:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                run_dir = root / "run"
                runner = ScriptedRunner([])
                incomplete_config = Settings(
                    _env_file=None,
                    HOSTING_PROVIDER="cloudflare_pages",
                    PUBLISH_REQUIRED=True,
                    CLOUDFLARE_ACCOUNT_ID=account_id,
                    CLOUDFLARE_API_TOKEN=api_token,
                )

                with self.assertRaisesRegex(PublisherError, expected_error):
                    PreviewPublisher(
                        incomplete_config,
                        runner=runner,
                        which=lambda command: self.fail(
                            f"toolchain lookup should not run without Pages credentials: {command}"
                        ),
                    ).publish(
                        run_dir=run_dir,
                        site_dir=make_site(root),
                        source_url=SOURCE_URL,
                        run_id=RUN_ID,
                    )

                self.assertEqual(runner.calls, [])
                metadata = json.loads(
                    (run_dir / "preview_deployment.json").read_text(encoding="utf-8")
                )
                self.assertEqual(metadata["provider"], "cloudflare_pages_preview")
                self.assertEqual(metadata["status"], "failed")
                self.assertFalse(metadata["production_deployment_started"])
                self.assertFalse((run_dir / "deployment.json").exists())

    def test_deploys_only_non_production_branch_and_writes_preview_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run_dir = root / "run"
            site = make_site(root)
            project_name = preview_project_name(SOURCE_URL, RUN_ID)
            branch = preview_branch_name(RUN_ID)
            deployment_url = f"https://deploy123.{project_name}.pages.dev"
            runner = ScriptedRunner(
                [
                    completed("[]"),
                    completed("Created"),
                    completed(f"Deployment complete: {deployment_url}"),
                    completed(
                        json.dumps(
                            [
                                {
                                    "Id": "preview-deployment-id",
                                    "Deployment": deployment_url,
                                    "Environment": "Preview",
                                    "Branch": branch,
                                    "created_on": "2026-07-18T12:00:00+00:00",
                                }
                            ]
                        )
                    ),
                ]
            )

            def http_get(url: str, **kwargs):
                if url.endswith("robots.txt"):
                    return FakeResponse(
                        "User-agent: *\nDisallow: /\n",
                        headers={"content-type": "text/plain"},
                    )
                return FakeResponse(protected_html(marker=url.rstrip("/") == deployment_url))

            result = PreviewPublisher(
                config(),
                runner=runner,
                which=lambda command: f"/{command}",
                http_get=http_get,
                sleep=lambda _: None,
            ).publish(
                run_dir=run_dir,
                site_dir=site,
                source_url=SOURCE_URL,
                run_id=RUN_ID,
            )

            commands = [call[0] for call in runner.calls]
            create = commands[1]
            deploy = commands[2]
            listing = commands[3]
            self.assertEqual(result.preview_url, deployment_url)
            self.assertEqual(result.environment, "preview")
            self.assertIn(PREVIEW_PRODUCTION_BRANCH, create)
            self.assertIn("--branch", deploy)
            self.assertIn(branch, deploy)
            self.assertNotIn(PREVIEW_PRODUCTION_BRANCH, deploy)
            self.assertIn("--environment", listing)
            self.assertIn("preview", listing)
            self.assertFalse(any("domain" in command for command in commands))
            metadata = json.loads((run_dir / "preview_deployment.json").read_text(encoding="utf-8"))
            self.assertEqual(metadata["preview_url"], deployment_url)
            self.assertTrue(metadata["checks"]["dedicated_project"])
            self.assertFalse(metadata["checks"]["production_deployment_started"])
            self.assertFalse((run_dir / "deployment.json").exists())

    def test_reuses_same_run_preview_project_without_create(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run_dir = root / "run"
            site = make_site(root)
            project_name = preview_project_name(SOURCE_URL, RUN_ID)
            branch = preview_branch_name(RUN_ID)
            deployment_url = f"https://deploy123.{project_name}.pages.dev"
            runner = ScriptedRunner(
                [
                    completed(json.dumps([{"name": project_name}])),
                    completed(f"Deployment complete: {deployment_url}"),
                    completed(
                        json.dumps(
                            [
                                {
                                    "url": deployment_url,
                                    "environment": "preview",
                                    "branch": branch,
                                }
                            ]
                        )
                    ),
                ]
            )

            def http_get(url: str, **kwargs):
                if url.endswith("robots.txt"):
                    return FakeResponse("Disallow: /", headers={})
                return FakeResponse(protected_html(marker=url.rstrip("/") == deployment_url))

            PreviewPublisher(
                config(),
                runner=runner,
                which=lambda command: f"/{command}",
                http_get=http_get,
                sleep=lambda _: None,
            ).publish(
                run_dir=run_dir,
                site_dir=site,
                source_url=SOURCE_URL,
                run_id=RUN_ID,
            )
            self.assertFalse(any("create" in call[0] for call in runner.calls))

    def test_stable_project_domain_is_rejected_and_secret_is_redacted(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            project_name = preview_project_name(SOURCE_URL, RUN_ID)
            stable_url = f"https://{project_name}.pages.dev"
            runner = ScriptedRunner(
                [
                    completed(json.dumps([{"name": project_name}])),
                    completed(f"Deployment complete: {stable_url}"),
                    completed(
                        json.dumps(
                            [
                                {
                                    "url": stable_url,
                                    "environment": "preview",
                                    "branch": preview_branch_name(RUN_ID),
                                }
                            ]
                        )
                    ),
                ]
            )
            with self.assertRaisesRegex(PublisherError, "stable project domain"):
                PreviewPublisher(
                    config(),
                    runner=runner,
                    which=lambda command: f"/{command}",
                ).publish(
                    run_dir=root / "run",
                    site_dir=make_site(root),
                    source_url=SOURCE_URL,
                    run_id=RUN_ID,
                )
            metadata = (root / "run" / "preview_deployment.json").read_text(encoding="utf-8")
            self.assertNotIn("preview-secret-token", metadata)
            self.assertFalse((root / "run" / "deployment.json").exists())


class PreviewVerifierTests(unittest.TestCase):
    def test_missing_live_x_robots_tag_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            site = make_site(Path(temp))
            staging, _ = prepare_preview_staging(run_dir=Path(temp) / "run", site_dir=site)
            response = FakeResponse(protected_html(marker=True), headers={"content-type": "text/html"})
            verifier = PreviewLiveVerifier(
                http_get=lambda *args, **kwargs: response,
                sleep=lambda _: None,
                retries=1,
            )
            with self.assertRaisesRegex(LiveVerificationError, "X-Robots-Tag"):
                verifier.verify(
                    "https://deploy.example.pages.dev",
                    site_dir=staging,
                    expected_marker=stable_business_id(SOURCE_URL),
                )


if __name__ == "__main__":
    unittest.main()
