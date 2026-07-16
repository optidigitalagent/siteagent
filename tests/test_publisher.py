from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from site_agent.config import Settings
from site_agent.identifiers import cloudflare_project_name, stable_business_id
from site_agent.models import DeploymentResult
from site_agent.publisher import (
    MAX_FILE_SIZE_BYTES,
    CloudflarePagesPublisher,
    GitPublisher,
    LiveSiteVerifier,
    LiveVerificationError,
    Publisher,
    PublisherCommandError,
    PublisherConfigurationError,
    PublisherError,
    SiteValidationError,
    validate_site_directory,
)
from site_agent.studio import _media_provenance_report
from site_agent.telegram_notify import TelegramNotifier


INSTAGRAM_URL = "https://www.instagram.com/Example_Business/?utm_source=test"


class FakeResponse:
    def __init__(
        self,
        status_code: int = 200,
        text: str = "",
        content_type: str = "text/html; charset=utf-8",
    ) -> None:
        self.status_code = status_code
        self.text = text
        self.headers = {"content-type": content_type}


class ScriptedRunner:
    def __init__(self, responses: list[subprocess.CompletedProcess[str] | BaseException]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[list[str], dict]] = []

    def __call__(self, command: list[str], **kwargs):
        self.calls.append((command, kwargs))
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response


def completed(stdout: str = "", stderr: str = "", returncode: int = 0):
    return subprocess.CompletedProcess(["npx"], returncode, stdout, stderr)


def config(**overrides) -> Settings:
    values = {
        "HOSTING_PROVIDER": "cloudflare_pages",
        "PUBLISH_REQUIRED": True,
        "CLOUDFLARE_ACCOUNT_ID": "account-id",
        "CLOUDFLARE_API_TOKEN": "super-secret-token",
        "CLOUDFLARE_PROJECT_PREFIX": "siteagent",
        "CLOUDFLARE_LIVE_RETRIES": 3,
        "CLOUDFLARE_LIVE_BACKOFF_SECONDS": 0,
        "CLOUDFLARE_COMMAND_TIMEOUT_SECONDS": 10,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def make_site(root: Path, *, instagram_url: str = INSTAGRAM_URL, with_asset: bool = False) -> Path:
    site_dir = root / "site"
    site_dir.mkdir(parents=True)
    marker = stable_business_id(instagram_url)
    asset_html = ""
    if with_asset:
        assets = site_dir / "assets"
        assets.mkdir()
        (assets / "logo.txt").write_text("asset", encoding="utf-8")
        asset_html = '<img src="assets/logo.txt" alt="logo">'
    (site_dir / "index.html").write_text(
        "<!doctype html><html><head>"
        f'<meta name="siteagent-business-id" content="{marker}">'
        "</head><body>Current site"
        f"{asset_html}</body></html>",
        encoding="utf-8",
    )
    return site_dir


def live_html(instagram_url: str = INSTAGRAM_URL, *, asset: bool = False) -> str:
    asset_html = '<img src="assets/logo.txt" alt="logo">' if asset else ""
    return (
        "<!doctype html><html><head>"
        f'<meta name="siteagent-business-id" content="{stable_business_id(instagram_url)}">'
        f"</head><body>Current site{asset_html}</body></html>"
    )


def happy_existing_runner(project_name: str) -> ScriptedRunner:
    deployment_url = f"https://deploy123.{project_name}.pages.dev"
    return ScriptedRunner(
        [
            completed(json.dumps([{"name": project_name}])),
            completed(f"Deployment complete: {deployment_url}"),
            completed(
                json.dumps(
                    [
                        {
                            "id": "deployment-id",
                            "url": deployment_url,
                            "environment": "production",
                            "created_on": "2026-07-14T12:00:00+00:00",
                        }
                    ]
                )
            ),
        ]
    )


class ProjectNamingTests(unittest.TestCase):
    def test_project_slug_is_cloudflare_safe(self) -> None:
        name = cloudflare_project_name("My Agency !!!", "https://instagram.com/Caf%C3%A9.Name/")
        self.assertRegex(name, r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
        self.assertLessEqual(len(name), 58)

    def test_same_instagram_url_has_same_project_name(self) -> None:
        first = cloudflare_project_name("siteagent", "https://www.instagram.com/Example/")
        second = cloudflare_project_name("siteagent", "instagram.com/example?utm_source=x")
        self.assertEqual(first, second)

    def test_different_instagram_urls_do_not_conflict(self) -> None:
        first = cloudflare_project_name("siteagent", "https://instagram.com/same_name/")
        second = cloudflare_project_name("siteagent", "https://instagram.com/same-name/")
        self.assertNotEqual(first, second)


class SitePreflightTests(unittest.TestCase):
    def test_missing_index_html_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            site = Path(temp) / "site"
            site.mkdir()
            (site / "asset.txt").write_text("x", encoding="utf-8")
            with self.assertRaisesRegex(SiteValidationError, "missing index.html"):
                validate_site_directory(site)

    def test_empty_site_directory_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            site = Path(temp) / "site"
            site.mkdir()
            with self.assertRaisesRegex(SiteValidationError, "empty"):
                validate_site_directory(site)

    def test_file_over_25_mib_is_rejected_with_guidance(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            site = make_site(Path(temp))
            large = site / "video.mp4"
            with large.open("wb") as handle:
                handle.truncate(MAX_FILE_SIZE_BYTES + 1)
            with self.assertRaises(SiteValidationError) as caught:
                validate_site_directory(site)
            message = str(caught.exception)
            self.assertIn("video.mp4", message)
            self.assertIn("25 MiB", message)
            self.assertIn("external storage", message)

    def test_internal_or_secret_file_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            site = make_site(Path(temp))
            (site / ".env.production").write_text("TOKEN=x", encoding="utf-8")
            with self.assertRaisesRegex(SiteValidationError, "Sensitive or internal"):
                validate_site_directory(site)


class CloudflarePublisherTests(unittest.TestCase):
    def test_missing_cloudflare_token_is_controlled_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            site = make_site(Path(temp))
            publisher = CloudflarePagesPublisher(config(CLOUDFLARE_API_TOKEN=""))
            with self.assertRaisesRegex(PublisherConfigurationError, "CLOUDFLARE_API_TOKEN"):
                publisher.publish(site_dir=site, instagram_url=INSTAGRAM_URL)

    def test_missing_account_id_is_controlled_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            site = make_site(Path(temp))
            publisher = CloudflarePagesPublisher(config(CLOUDFLARE_ACCOUNT_ID=""))
            with self.assertRaisesRegex(PublisherConfigurationError, "CLOUDFLARE_ACCOUNT_ID"):
                publisher.publish(site_dir=site, instagram_url=INSTAGRAM_URL)

    def test_missing_npx_has_install_guidance(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            site = make_site(Path(temp))
            publisher = CloudflarePagesPublisher(
                config(),
                which=lambda command: None if command == "npx" else f"/{command}",
            )
            with self.assertRaisesRegex(PublisherConfigurationError, "nodejs.org"):
                publisher.publish(site_dir=site, instagram_url=INSTAGRAM_URL)

    def test_existing_project_is_reused(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            site = make_site(Path(temp))
            project_name = cloudflare_project_name("siteagent", INSTAGRAM_URL)
            runner = happy_existing_runner(project_name)
            publisher = CloudflarePagesPublisher(
                config(),
                runner=runner,
                which=lambda command: f"/{command}",
                http_get=lambda *args, **kwargs: FakeResponse(text=live_html()),
                sleep=lambda _: None,
            )
            result = publisher.publish(site_dir=site, instagram_url=INSTAGRAM_URL)
            commands = [call[0] for call in runner.calls]
            self.assertFalse(any("create" in command for command in commands))
            self.assertEqual(result.project_name, project_name)

    def test_new_project_is_created(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            site = make_site(Path(temp))
            project_name = cloudflare_project_name("siteagent", INSTAGRAM_URL)
            deployment_url = f"https://deploy123.{project_name}.pages.dev"
            runner = ScriptedRunner(
                [
                    completed("[]"),
                    completed("Project created"),
                    completed(json.dumps([{"name": project_name, "subdomain": f"{project_name}.pages.dev"}])),
                    completed(f"Deployment complete: {deployment_url}"),
                    completed(json.dumps([{"id": "new-id", "url": deployment_url, "environment": "production"}])),
                ]
            )
            publisher = CloudflarePagesPublisher(
                config(),
                runner=runner,
                which=lambda command: f"/{command}",
                http_get=lambda *args, **kwargs: FakeResponse(text=live_html()),
                sleep=lambda _: None,
            )
            result = publisher.publish(site_dir=site, instagram_url=INSTAGRAM_URL)
            create_command = runner.calls[1][0]
            self.assertIn("create", create_command)
            self.assertIn("--production-branch", create_command)
            self.assertEqual(result.deployment_id, "new-id")

    def test_unrelated_existing_project_uses_stable_collision_suffix(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            site = make_site(Path(temp))
            base_name = cloudflare_project_name("siteagent", INSTAGRAM_URL)
            collision_name = cloudflare_project_name("siteagent", INSTAGRAM_URL, collision=1)
            deployment_url = f"https://deploy123.{collision_name}.pages.dev"
            runner = ScriptedRunner(
                [
                    completed(json.dumps([{"name": base_name, "subdomain": f"{base_name}.pages.dev"}])),
                    completed("Project created"),
                    completed(json.dumps([{"name": collision_name, "subdomain": f"{collision_name}.pages.dev"}])),
                    completed(f"Deployment complete: {deployment_url}"),
                    completed(json.dumps([{"id": "collision-id", "url": deployment_url, "environment": "production"}])),
                ]
            )
            responses = [
                FakeResponse(text="<html><body>unrelated project</body></html>"),
                FakeResponse(text=live_html()),
            ]
            publisher = CloudflarePagesPublisher(
                config(),
                runner=runner,
                which=lambda command: f"/{command}",
                http_get=lambda *args, **kwargs: responses.pop(0),
                sleep=lambda _: None,
            )
            result = publisher.publish(site_dir=site, instagram_url=INSTAGRAM_URL)
            self.assertEqual(result.project_name, collision_name)
            self.assertIn(collision_name, runner.calls[1][0])

    def test_project_creation_failure_is_domain_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            site = make_site(Path(temp))
            runner = ScriptedRunner([completed("[]"), completed(stderr="permission denied", returncode=1)])
            publisher = CloudflarePagesPublisher(
                config(), runner=runner, which=lambda command: f"/{command}"
            )
            with self.assertRaisesRegex(PublisherCommandError, "project creation failed"):
                publisher.publish(site_dir=site, instagram_url=INSTAGRAM_URL)

    def test_upload_failure_is_domain_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            site = make_site(Path(temp))
            project_name = cloudflare_project_name("siteagent", INSTAGRAM_URL)
            runner = ScriptedRunner(
                [
                    completed(json.dumps([{"name": project_name}])),
                    completed(stderr="upload rejected", returncode=1),
                ]
            )
            publisher = CloudflarePagesPublisher(
                config(), runner=runner, which=lambda command: f"/{command}"
            )
            with self.assertRaisesRegex(PublisherCommandError, "site upload failed"):
                publisher.publish(site_dir=site, instagram_url=INSTAGRAM_URL)

    def test_wrangler_timeout_is_domain_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            site = make_site(Path(temp))
            timeout = subprocess.TimeoutExpired(["npx"], 10)
            publisher = CloudflarePagesPublisher(
                config(),
                runner=ScriptedRunner([timeout]),
                which=lambda command: f"/{command}",
            )
            with self.assertRaisesRegex(PublisherCommandError, "timed out after 10 seconds"):
                publisher.publish(site_dir=site, instagram_url=INSTAGRAM_URL)

    def test_secret_is_not_exposed_in_error_or_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            site = make_site(root)
            runner = ScriptedRunner(
                [completed(stderr="bad super-secret-token account-id", returncode=1)]
            )
            publisher = Publisher(
                config(),
                runner=runner,
                which=lambda command: f"/{command}",
            )
            with self.assertRaises(PublisherError) as caught:
                publisher.publish(
                    run_dir=root,
                    site_dir=site,
                    instagram_url=INSTAGRAM_URL,
                    production=True,
                )
            metadata = (root / "deployment.json").read_text(encoding="utf-8")
            self.assertNotIn("super-secret-token", str(caught.exception))
            self.assertNotIn("super-secret-token", metadata)
            self.assertNotIn("account-id", metadata)
            command = runner.calls[0][0]
            self.assertNotIn("super-secret-token", command)
            self.assertEqual(runner.calls[0][1]["env"]["CLOUDFLARE_API_TOKEN"], "super-secret-token")
            self.assertNotIn("WRANGLER_LOG", runner.calls[0][1]["env"])
            self.assertEqual(runner.calls[0][1]["env"]["WRANGLER_SEND_METRICS"], "false")

    def test_deployment_result_is_parsed_and_structured(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            site = make_site(Path(temp))
            project_name = cloudflare_project_name("siteagent", INSTAGRAM_URL)
            runner = happy_existing_runner(project_name)
            publisher = CloudflarePagesPublisher(
                config(),
                runner=runner,
                which=lambda command: f"/{command}",
                http_get=lambda *args, **kwargs: FakeResponse(text=live_html()),
                sleep=lambda _: None,
            )
            result = publisher.publish(site_dir=site, instagram_url=INSTAGRAM_URL)
            self.assertEqual(result.provider, "cloudflare_pages")
            self.assertEqual(result.status, "success")
            self.assertEqual(result.verification_status, "verified")
            self.assertTrue(result.production_url.startswith("https://"))
            self.assertEqual(result.deployment_id, "deployment-id")

    def test_successful_facade_writes_deployment_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            site = make_site(root)
            project_name = cloudflare_project_name("siteagent", INSTAGRAM_URL)
            publisher = Publisher(
                config(),
                runner=happy_existing_runner(project_name),
                which=lambda command: f"/{command}",
                http_get=lambda *args, **kwargs: FakeResponse(text=live_html()),
                sleep=lambda _: None,
            )
            result = publisher.publish(
                run_dir=root,
                site_dir=site,
                instagram_url=INSTAGRAM_URL,
                production=True,
            )
            metadata = json.loads((root / "deployment.json").read_text(encoding="utf-8"))
            self.assertEqual(metadata["production_url"], result.production_url)
            self.assertEqual(metadata["verification_status"], "verified")
            self.assertNotIn("super-secret-token", json.dumps(metadata))


class LiveVerificationTests(unittest.TestCase):
    def test_live_url_200_html_with_marker_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            site = make_site(Path(temp))
            verifier = LiveSiteVerifier(
                http_get=lambda *args, **kwargs: FakeResponse(text=live_html()),
                sleep=lambda _: None,
            )
            verifier.verify(
                "https://example.pages.dev",
                site_dir=site,
                expected_marker=stable_business_id(INSTAGRAM_URL),
            )

    def test_live_url_error_status_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            site = make_site(Path(temp))
            verifier = LiveSiteVerifier(
                http_get=lambda *args, **kwargs: FakeResponse(status_code=500, text="error"),
                sleep=lambda _: None,
                retries=1,
            )
            with self.assertRaisesRegex(LiveVerificationError, "HTTP 500"):
                verifier.verify(
                    "https://example.pages.dev",
                    site_dir=site,
                    expected_marker=stable_business_id(INSTAGRAM_URL),
                )

    def test_live_verification_retries_then_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            site = make_site(Path(temp))
            responses = [
                FakeResponse(status_code=503, text="pending"),
                FakeResponse(status_code=503, text="pending"),
                FakeResponse(text=live_html()),
            ]
            sleeps: list[float] = []
            verifier = LiveSiteVerifier(
                http_get=lambda *args, **kwargs: responses.pop(0),
                sleep=sleeps.append,
                retries=3,
                backoff_seconds=1,
            )
            verifier.verify(
                "https://example.pages.dev",
                site_dir=site,
                expected_marker=stable_business_id(INSTAGRAM_URL),
            )
            self.assertEqual(sleeps, [1, 2])

    def test_main_local_assets_are_checked(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            site = make_site(Path(temp), with_asset=True)
            calls: list[str] = []

            def get(url: str, **kwargs):
                calls.append(url)
                if url.endswith("logo.txt"):
                    return FakeResponse(text="asset", content_type="text/plain")
                return FakeResponse(text=live_html(asset=True))

            LiveSiteVerifier(http_get=get, sleep=lambda _: None).verify(
                "https://example.pages.dev",
                site_dir=site,
                expected_marker=stable_business_id(INSTAGRAM_URL),
            )
            self.assertIn("https://example.pages.dev/assets/logo.txt", calls)


class ProviderAndDeliveryTests(unittest.TestCase):
    def test_direct_production_facade_rechecks_studio_fixture_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            site = make_site(root)
            studio = root / "studio"
            (studio / "input").mkdir(parents=True)
            image = "https://media.example/fixture.jpg"
            (site / "index.html").write_text(f'<img src="{image}">', encoding="utf-8")
            (studio / "input" / "media_manifest.json").write_text(
                json.dumps({"media": [{"asset_id": "fixture", "url": image, "source_kind": "fixture_stock"}]}),
                encoding="utf-8",
            )
            (studio / "media_provenance_report.json").write_text(
                json.dumps(_media_provenance_report(studio_dir=studio, site_dir=site)), encoding="utf-8"
            )
            publisher = Publisher(config(HOSTING_PROVIDER="local", PUBLISH_REQUIRED=False))
            with self.assertRaisesRegex(PublisherConfigurationError, "selected fixture/stock/unverified media"):
                publisher.publish(
                    run_dir=root, site_dir=site, instagram_url=INSTAGRAM_URL, production=True
                )

    def test_telegram_production_never_returns_file_url(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            site = make_site(root)
            publisher = Publisher(config(HOSTING_PROVIDER="local", PUBLISH_REQUIRED=False))
            with self.assertRaisesRegex(PublisherConfigurationError, "Telegram production"):
                publisher.publish(
                    run_dir=root,
                    site_dir=site,
                    instagram_url=INSTAGRAM_URL,
                    production=True,
                )
            metadata = json.loads((root / "deployment.json").read_text(encoding="utf-8"))
            self.assertEqual(metadata["status"], "failed")
            self.assertNotIn("file://", json.dumps(metadata))

    def test_local_provider_requires_explicit_non_required_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            site = make_site(root)
            publisher = Publisher(config(HOSTING_PROVIDER="local", PUBLISH_REQUIRED=False))
            result = publisher.publish(
                run_dir=root,
                site_dir=site,
                instagram_url=INSTAGRAM_URL,
            )
            self.assertEqual(result.provider, "local")
            self.assertTrue(result.production_url.startswith("file:"))

    def test_local_provider_is_blocked_when_publish_required(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            site = make_site(root)
            publisher = Publisher(config(HOSTING_PROVIDER="local", PUBLISH_REQUIRED=True))
            with self.assertRaises(PublisherConfigurationError):
                publisher.publish(run_dir=root, site_dir=site, instagram_url=INSTAGRAM_URL)

    def test_telegram_success_requires_live_verified_result(self) -> None:
        local_result = DeploymentResult(
            provider="local",
            production_url="file:///tmp/site/index.html",
            deployment_url="file:///tmp/site/index.html",
            status="local_preview",
            deployed_at="2026-07-14T00:00:00+00:00",
            verification_status="not_required",
        )
        with self.assertRaisesRegex(ValueError, "live-verified"):
            TelegramNotifier(token="unused").send_done(1, local_result)

    def test_telegram_success_message_contains_only_public_site_url(self) -> None:
        verified = DeploymentResult(
            provider="cloudflare_pages",
            project_name="siteagent-example-abc123",
            production_url="https://siteagent-example-abc123.pages.dev",
            deployment_url="https://deployment.siteagent-example-abc123.pages.dev",
            deployment_id="deployment",
            status="success",
            deployed_at="2026-07-14T00:00:00+00:00",
            verification_status="verified",
        )
        bot = Mock()
        bot.send_message = AsyncMock()
        with patch("site_agent.telegram_notify.Bot", return_value=bot):
            TelegramNotifier(token="unused").send_done(42, verified)
        message = bot.send_message.await_args.kwargs["text"]
        self.assertEqual(
            message,
            "Готово:\n\nСайт:\nhttps://siteagent-example-abc123.pages.dev",
        )
        self.assertNotIn("Репозиторий", message)
        self.assertNotIn("file:", message)

    def test_deployment_failure_does_not_complete_job(self) -> None:
        from site_agent import cli

        job = Mock(id="job-1", instagram_url=INSTAGRAM_URL, chat_id=42)
        queue = Mock()
        queue.next_pending.return_value = job
        queue.claim_next.return_value = job
        orchestrator = Mock()
        orchestrator.run.side_effect = PublisherError("deployment failed")
        notifier = Mock()
        with (
            patch.object(cli, "_pending_job_queue", return_value=queue),
            patch.object(cli, "SiteAgentOrchestrator", return_value=orchestrator),
            patch.object(cli, "TelegramNotifier", return_value=notifier),
        ):
            with self.assertRaisesRegex(PublisherError, "deployment failed"):
                cli.run_pending_job()
        queue.fail.assert_called_once_with("job-1", "deployment failed")
        queue.complete.assert_not_called()
        notifier.send_done.assert_not_called()

    def test_legacy_git_publisher_remains_explicitly_available(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            site = make_site(root)
            git_config = config(
                HOSTING_PROVIDER="git",
                PUBLISH_REMOTE_URL="https://github.com/example/generated.git",
                PUBLIC_REPO_URL="https://github.com/example/generated",
            )
            with patch.object(GitPublisher, "_git", return_value=None):
                result = Publisher(git_config).publish(
                    run_dir=root,
                    site_dir=site,
                    instagram_url=INSTAGRAM_URL,
                )
            self.assertEqual(result.provider, "git")
            self.assertEqual(result.production_url, "https://example.github.io/generated/")
            self.assertTrue((root / "publish_repo" / "index.html").is_file())


if __name__ == "__main__":
    unittest.main()
