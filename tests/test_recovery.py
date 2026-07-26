from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from site_agent import cli
from site_agent.job_queue import (
    InterruptedDeliveryUncertain,
    PreviewRecoveryNotAllowed,
    TelegramJobQueue,
)
from site_agent.models import DeploymentResult
from site_agent.preview import PreviewDeploymentResult
from site_agent.workflow import checksum


INSTAGRAM_URL = "https://www.instagram.com/example_business/"


def _verified_preview(url: str = "https://hash.siteagent-preview-example.pages.dev") -> PreviewDeploymentResult:
    return PreviewDeploymentResult(
        project_name="siteagent-preview-example",
        preview_url=url,
        deployment_url=url,
        deployment_id="preview-deployment-1",
        branch="preview-job-preview",
        deployed_at="2026-07-19T00:00:00+00:00",
        staging_dir="runs/job-preview/preview_publish",
    )


class RecoveryQueueTests(unittest.TestCase):
    def _running_job(self, queue: TelegramJobQueue):
        job = queue.enqueue(INSTAGRAM_URL, chat_id=42)
        payload = json.loads(queue.path.read_text(encoding="utf-8"))
        payload[0]["status"] = "running"
        queue.path.write_text(json.dumps(payload), encoding="utf-8")
        return job

    def test_running_job_is_selected_before_pending_work(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            queue = TelegramJobQueue(Path(temp) / "jobs.json", git_sync=False)
            running = self._running_job(queue)
            queue.enqueue("https://www.instagram.com/later/", chat_id=43)

            resumed = queue.next_interrupted()

            self.assertIsNotNone(resumed)
            self.assertEqual(resumed.id, running.id)
            self.assertEqual(queue.next_pending().instagram_url, "https://instagram.com/later")

    def test_enqueue_normalizes_and_deduplicates_unfinished_business_url(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            queue = TelegramJobQueue(Path(temp) / "jobs.json", git_sync=False)
            first = queue.enqueue(
                "https://www.instagram.com/Example_Business/?igsh=tracking",
                chat_id=42,
            )
            duplicate = queue.enqueue("instagram.com/example_business/", chat_id=99)

            self.assertEqual(duplicate.id, first.id)
            self.assertEqual(first.instagram_url, "https://instagram.com/example_business")
            self.assertEqual(len(json.loads(queue.path.read_text(encoding="utf-8"))), 1)

    def test_known_media_failure_reclaims_same_run_for_preview(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            queue = TelegramJobQueue(Path(temp) / "jobs.json", git_sync=False)
            job = queue.enqueue(INSTAGRAM_URL, chat_id=42)
            queue.set_run_dir(job.id, r"runs\same-run")
            queue.fail(job.id, "media_input/manifest.json does not exist")

            reclaimed = queue.reclaim_failed_preview(job.id)

            self.assertEqual(reclaimed.id, job.id)
            self.assertEqual(reclaimed.run_id, job.id)
            self.assertEqual(reclaimed.run_dir, r"runs\same-run")
            self.assertEqual(reclaimed.status, "running")
            self.assertEqual(reclaimed.telegram_notification_status, "not_started")
            self.assertTrue(any(event.startswith("preview_reclaimed:") for event in reclaimed.recovery_events))

    def test_media_input_checkpoint_blocker_remains_recoverable(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            queue = TelegramJobQueue(Path(temp) / "jobs.json", git_sync=False)
            job = queue.enqueue(INSTAGRAM_URL, chat_id=42)
            queue.set_run_dir(job.id, r"runs\same-run")

            failed = queue.fail(
                job.id,
                "media-input checkpoint blocked: no provable business media remained after all fallbacks",
            )

            self.assertEqual(failed.recovery_failure_code, "PREVIEW_RECOVERABLE_FAILURE")
            self.assertTrue(failed.recovery_eligible)
            selected = queue.next_recoverable_preview()
            self.assertIsNotNone(selected)
            self.assertEqual(selected.id, job.id)
            reclaimed = queue.reclaim_failed_preview(job.id)
            self.assertEqual(reclaimed.run_dir, r"runs\same-run")
            self.assertEqual(reclaimed.status, "running")

    def test_image_provider_failure_remains_recoverable_in_same_preview_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            queue = TelegramJobQueue(Path(temp) / "jobs.json", git_sync=False)
            job = queue.enqueue(INSTAGRAM_URL, chat_id=42)
            queue.set_run_dir(job.id, r"runs\same-run")

            failed = queue.fail(
                job.id,
                "media generation is unavailable: image service request failed",
            )

            self.assertEqual(failed.recovery_failure_code, "PREVIEW_RECOVERABLE_FAILURE")
            self.assertTrue(failed.recovery_eligible)
            reclaimed = queue.reclaim_failed_preview(job.id)
            self.assertEqual(reclaimed.id, job.id)
            self.assertEqual(reclaimed.run_dir, r"runs\same-run")
            self.assertEqual(reclaimed.status, "running")

    def test_acceptance_failure_reclaims_same_preview_after_artifact_revision(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            queue = TelegramJobQueue(Path(temp) / "jobs.json", git_sync=False)
            job = queue.enqueue(INSTAGRAM_URL, chat_id=42)
            queue.set_run_dir(job.id, r"runs\same-run")
            queue.fail(job.id, "Acceptance audit blocked deployment: commercial gate failed")

            reclaimed = queue.reclaim_failed_preview(job.id)

            self.assertEqual(reclaimed.id, job.id)
            self.assertEqual(reclaimed.status, "running")
            self.assertEqual(reclaimed.telegram_notification_status, "not_started")

    def test_unrelated_failure_cannot_enter_preview_recovery_lane(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            queue = TelegramJobQueue(Path(temp) / "jobs.json", git_sync=False)
            job = queue.enqueue(INSTAGRAM_URL, chat_id=42)
            queue.fail(job.id, "Cloudflare deployment may have succeeded")

            with self.assertRaises(PreviewRecoveryNotAllowed):
                queue.reclaim_failed_preview(job.id)

    def test_insufficient_content_failure_is_recoverable_by_same_preview_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            queue = TelegramJobQueue(Path(temp) / "jobs.json", git_sync=False)
            job = queue.enqueue(INSTAGRAM_URL, chat_id=42)
            queue.set_run_dir(job.id, r"runs\same-run")
            queue.fail(job.id, "BLOCKED_INSUFFICIENT_BUSINESS_CONTENT: product_identified")

            selected = queue.next_recoverable_preview()
            self.assertIsNotNone(selected)
            self.assertEqual(selected.id, job.id)
            reclaimed = queue.reclaim_failed_preview(job.id)
            self.assertEqual(reclaimed.run_dir, r"runs\same-run")
            self.assertEqual(reclaimed.status, "running")

    def test_legacy_preview_metadata_is_reconciled_without_production_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            queue = TelegramJobQueue(Path(temp) / "jobs.json", git_sync=False)
            job = queue.enqueue(INSTAGRAM_URL, chat_id=42)
            payload = json.loads(queue.path.read_text(encoding="utf-8"))
            payload[0]["status"] = "preview_ready"
            queue.path.write_text(json.dumps(payload), encoding="utf-8")

            repaired = queue.reconcile_preview_metadata(
                job.id,
                run_dir=r"runs\same-run",
                preview_url="https://hash.siteagent-preview-example.pages.dev",
                deployment_id="deployment-id",
                project_name="siteagent-preview-example",
                branch="preview-same-run",
                checkpoints={"preview_live_verified": "completed_and_valid"},
            )

            self.assertEqual(repaired.preview_deployment_id, "deployment-id")
            self.assertEqual(repaired.run_dir, r"runs\same-run")
            self.assertTrue(repaired.recovery_eligible)
            self.assertEqual(repaired.site_url, "")
            self.assertEqual(repaired.repo_url, "")
            self.assertEqual(repaired.telegram_notification_status, "not_started")

    def test_preview_ready_is_not_production_completion(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            queue = TelegramJobQueue(Path(temp) / "jobs.json", git_sync=False)
            job = queue.enqueue(INSTAGRAM_URL, chat_id=42)
            queue.fail(job.id, "research failed all facts")
            queue.reclaim_failed_preview(job.id)

            ready = queue.mark_preview_ready(
                job.id,
                preview_url="https://preview.example.pages.dev",
                deployment_id="preview-deployment",
                project_name="siteagent-preview-example",
                branch="preview-job",
                checkpoints={"critics_completed": "completed_and_valid"},
            )

            self.assertEqual(ready.status, "preview_ready")
            self.assertEqual(ready.site_url, "")
            self.assertEqual(ready.repo_url, "")
            self.assertEqual(ready.telegram_notification_status, "not_started")
            self.assertEqual(
                ready.checkpoints["ONE_LINK_SITE_PREVIEW_READY_FOR_USER_REVIEW"],
                "completed_and_valid",
            )

    def test_uncertain_notification_is_never_retried_automatically(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            queue = TelegramJobQueue(Path(temp) / "jobs.json", git_sync=False)
            job = self._running_job(queue)
            queue.mark_notification_sending(job.id)

            with self.assertRaisesRegex(InterruptedDeliveryUncertain, job.id):
                queue.next_interrupted()

    def test_manual_resend_requires_recorded_authorization_and_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            queue = TelegramJobQueue(Path(temp) / "jobs.json", git_sync=False)
            job = self._running_job(queue)
            queue.mark_notification_unknown(job.id, "connection interrupted")

            authorized = queue.authorize_manual_resend(job.id, reason="user confirmed")
            self.assertEqual(authorized.status, "running")
            self.assertEqual(authorized.telegram_notification_status, "sending")
            self.assertIn("authorized_at", authorized.manual_resend_authorization)

            sent = queue.record_notification_sent(
                job.id, {"status": "accepted", "sent_at": "2026-07-14T00:00:00+00:00"}
            )
            self.assertEqual(sent.telegram_notification_status, "sent")
            self.assertEqual(sent.telegram_receipt["status"], "accepted")
            self.assertNotIn("chat_id", sent.telegram_receipt)
            self.assertNotIn("message_id", sent.telegram_receipt)


class RecoveryCliTests(unittest.TestCase):
    def test_delivery_resume_rejects_stale_full_tree_critic_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            run_dir = Path(temp)
            reports_dir = run_dir / "generation_reports"
            critiques_dir = run_dir / "critique_reports"
            site_dir = run_dir / "site"
            reports_dir.mkdir()
            critiques_dir.mkdir()
            site_dir.mkdir()
            index_path = site_dir / "index.html"
            index_path.write_text("<html><body>Accepted</body></html>", encoding="utf-8")
            provenance_path = critiques_dir / "critique_iteration_1.provenance.json"
            provenance_path.write_text(
                json.dumps({
                    "site_sha256": cli.SiteAgentOrchestrator._site_checksum(site_dir),
                    "hash_scope": "html_css_js_tree",
                }),
                encoding="utf-8",
            )
            # A post-review CSS edit must invalidate the saved critic even when
            # index.html and the approved report themselves are unchanged.
            (site_dir / "styles.css").write_text("body { color: red; }", encoding="utf-8")

            orchestrator = object.__new__(cli.SiteAgentOrchestrator)
            orchestrator._read_model = Mock(side_effect=[
                SimpleNamespace(instagram_url=INSTAGRAM_URL),
                SimpleNamespace(approved_for_delivery=True),
            ])
            orchestrator.acceptance_auditor = Mock()

            result = orchestrator._resume_delivery_if_ready(
                instagram_url=INSTAGRAM_URL,
                job_id="job-preview",
                run_dir=run_dir,
                reports_dir=reports_dir,
                site_dir=site_dir,
                production=False,
                preview=True,
            )

            self.assertIsNone(result)
            orchestrator.acceptance_auditor.audit.assert_not_called()

    def test_go_resumes_into_preview_with_preview_notification_only(self) -> None:
        job = SimpleNamespace(
            id="job-1",
            run_id="job-1",
            instagram_url=INSTAGRAM_URL,
            chat_id=42,
            status="running",
            run_dir="runs/job-1",
        )
        queue = Mock()
        queue.next_interrupted.return_value = job
        publish = _verified_preview()
        ready = SimpleNamespace(
            **{
                **job.__dict__,
                "status": "preview_ready",
                "workflow_lane": "preview",
                "preview_url": publish.preview_url,
                "preview_deployment_id": publish.deployment_id,
                "preview_project_name": publish.project_name,
                "preview_branch": publish.branch,
                "site_url": "",
                "repo_url": "",
                "production_authorization": {},
                "telegram_preview_notification_status": "not_started",
            }
        )
        queue.mark_preview_ready.return_value = ready
        queue.get.return_value = SimpleNamespace(
            telegram_preview_notification_status="sent"
        )
        orchestrator = Mock()
        orchestrator.run.return_value = SimpleNamespace(publish=publish)
        with (
            patch.object(cli, "_pending_job_queue", return_value=queue),
            patch.object(cli, "SiteAgentOrchestrator", return_value=orchestrator),
            patch.object(cli, "_deliver_preview_notification") as deliver,
        ):
            cli.run_pending_job()

        orchestrator.run.assert_called_once_with(
            INSTAGRAM_URL,
            production=False,
            preview=True,
            run_id="job-1",
            run_path=Path("runs/job-1"),
            real_business_media_only=False,
        )
        queue.mark_preview_ready.assert_called_once()
        queue.complete.assert_not_called()
        queue.mark_notification_sending.assert_not_called()
        deliver.assert_called_once()

    def test_preview_resume_uses_same_run_and_preview_notification_only(self) -> None:
        failed = SimpleNamespace(
            id="job-preview",
            run_id="job-preview",
            instagram_url=INSTAGRAM_URL,
            chat_id=42,
            status="failed",
            run_dir=r"runs\job-preview",
            preview_url="",
            telegram_notification_status="not_started",
        )
        running = SimpleNamespace(**{**failed.__dict__, "status": "running"})
        queue = Mock()
        queue.get.return_value = failed
        queue.reclaim_failed_preview.return_value = running
        publish = _verified_preview()
        ready = SimpleNamespace(
            **{
                **running.__dict__,
                "status": "preview_ready",
                "workflow_lane": "preview",
                "preview_url": publish.preview_url,
                "preview_deployment_id": publish.deployment_id,
                "preview_project_name": publish.project_name,
                "preview_branch": publish.branch,
                "site_url": "",
                "repo_url": "",
                "production_authorization": {},
                "telegram_preview_notification_status": "not_started",
            }
        )
        queue.mark_preview_ready.return_value = ready
        queue.get.return_value = SimpleNamespace(
            **failed.__dict__,
            telegram_preview_notification_status="sent",
        )
        orchestrator = Mock()
        orchestrator.run.return_value = SimpleNamespace(publish=publish)

        with (
            patch.object(cli, "_pending_job_queue", return_value=queue),
            patch.object(cli, "SiteAgentOrchestrator", return_value=orchestrator),
            patch.object(cli, "_deliver_preview_notification") as deliver,
        ):
            cli.run_preview_job("job-preview")

        orchestrator.run.assert_called_once_with(
            INSTAGRAM_URL,
            production=False,
            preview=True,
            run_id="job-preview",
            run_path=Path(r"runs\job-preview"),
            real_business_media_only=False,
        )
        queue.mark_preview_ready.assert_called_once()
        self.assertEqual(
            queue.mark_preview_ready.call_args.kwargs["preview_url"],
            "https://hash.siteagent-preview-example.pages.dev",
        )
        queue.complete.assert_not_called()
        queue.mark_notification_sending.assert_not_called()
        deliver.assert_called_once()

    def test_preview_ready_revalidates_same_run_without_duplicate_queue_event(self) -> None:
        ready = SimpleNamespace(
            id="job-preview",
            run_id="job-preview",
            instagram_url=INSTAGRAM_URL,
            chat_id=42,
            status="preview_ready",
            run_dir=r"runs\job-preview",
            preview_url="https://hash.siteagent-preview-example.pages.dev",
            telegram_notification_status="not_started",
            telegram_preview_notification_status="sent",
            workflow_lane="preview",
            preview_deployment_id="preview-deployment-1",
            preview_project_name="siteagent-preview-example",
            preview_branch="preview-job-preview",
            site_url="",
            repo_url="",
            production_authorization={},
        )
        queue = Mock()
        queue.get.return_value = ready
        orchestrator = Mock()
        orchestrator.run.return_value = SimpleNamespace(publish=_verified_preview(ready.preview_url))

        with (
            patch.object(cli, "_pending_job_queue", return_value=queue),
            patch.object(cli, "SiteAgentOrchestrator", return_value=orchestrator),
            patch.object(cli, "_deliver_preview_notification") as deliver,
        ):
            cli.run_preview_job("job-preview")

        orchestrator.run.assert_called_once_with(
            INSTAGRAM_URL,
            production=False,
            preview=True,
            run_id="job-preview",
            run_path=Path(r"runs\job-preview"),
            real_business_media_only=False,
        )
        queue.mark_preview_ready.assert_not_called()
        queue.reclaim_failed_preview.assert_not_called()
        deliver.assert_not_called()

    def test_preview_ready_validation_failure_does_not_destroy_checkpoint(self) -> None:
        ready = SimpleNamespace(
            id="job-preview",
            run_id="job-preview",
            instagram_url=INSTAGRAM_URL,
            chat_id=42,
            status="preview_ready",
            run_dir=r"runs\job-preview",
            preview_url="https://hash.siteagent-preview.pages.dev",
            telegram_notification_status="not_started",
        )
        queue = Mock()
        queue.get.return_value = ready
        orchestrator = Mock()
        orchestrator.run.side_effect = RuntimeError("cached preview validation failed")

        with (
            patch.object(cli, "_pending_job_queue", return_value=queue),
            patch.object(cli, "SiteAgentOrchestrator", return_value=orchestrator),
            self.assertRaisesRegex(RuntimeError, "cached preview validation failed"),
        ):
            cli.run_preview_job("job-preview")

        queue.fail.assert_not_called()
        queue.mark_preview_ready.assert_not_called()

    def test_preview_lane_rejects_a_verified_production_result(self) -> None:
        production = DeploymentResult(
            provider="cloudflare_pages",
            project_name="customer-production",
            production_url="https://customer-production.pages.dev",
            deployment_url="https://hash.customer-production.pages.dev",
            status="success",
            deployed_at="2026-07-19T00:00:00+00:00",
            verification_status="verified",
        )
        with self.assertRaisesRegex(RuntimeError, "non-preview deployment"):
            cli._preview_result_from_result(SimpleNamespace(publish=production))

    def test_production_promotion_requires_explicit_authorization_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            run_dir = Path(temp)
            job = SimpleNamespace(
                id="job-preview",
                run_id="job-preview",
                instagram_url=INSTAGRAM_URL,
                chat_id=42,
                status="preview_ready",
                run_dir=str(run_dir),
            )
            queue = Mock()
            queue.get.return_value = job
            with (
                patch.object(cli, "_pending_job_queue", return_value=queue),
                patch.object(cli, "SiteAgentOrchestrator") as orchestrator,
                self.assertRaisesRegex(RuntimeError, "production_authorization.json"),
            ):
                cli.run_production_promotion("job-preview", authorized=True)
            orchestrator.assert_not_called()

    def test_production_promotion_requires_authorize_flag_before_queue_access(self) -> None:
        with (
            patch.object(cli, "_pending_job_queue") as queue_factory,
            self.assertRaisesRegex(RuntimeError, "--authorize-production"),
        ):
            cli.run_production_promotion("job-preview", authorized=False)
        queue_factory.assert_not_called()

    def test_production_authorization_materializes_exact_rights_bound_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            run_dir = Path(temp)
            reports = run_dir / "generation_reports"
            reports.mkdir()
            source = {
                "purpose": "isolated_preview",
                "media": [
                    {
                        "asset_id": asset_id,
                        "url": f"https://res.cloudinary.com/example/image/upload/{asset_id}.jpg",
                        "source_kind": "business_social",
                        "provenance_type": "verified_official_business_asset",
                        "user_authorized_for_preview": True,
                        "allowed_for_customer_production": False,
                        "user_authorized": False,
                        "allowed_for_public_site": False,
                    }
                    for asset_id in ("one", "two")
                ],
            }
            (reports / "02_authorised_media_manifest.json").write_text(
                json.dumps(source), encoding="utf-8"
            )
            (reports / "acceptance_audit.provenance.json").write_text(
                json.dumps({"media_records_sha256": checksum(source["media"])}),
                encoding="utf-8",
            )
            authorization = {
                "job_id": "job-preview",
                "run_id": "job-preview",
                "authorized_media_asset_ids": ["one", "two"],
            }

            manifest = cli._materialize_production_manifest(run_dir, authorization)

            self.assertEqual(manifest["purpose"], "customer_production")
            self.assertTrue(all(item["source_kind"] == "business_social" for item in manifest["media"]))
            self.assertTrue(all(item["provenance_type"] == "verified_official_business_asset" for item in manifest["media"]))
            self.assertTrue(all(item["user_authorized"] for item in manifest["media"]))
            self.assertTrue(all(item["allowed_for_public_site"] for item in manifest["media"]))
            self.assertTrue(all(item["allowed_for_customer_production"] for item in manifest["media"]))
            self.assertTrue((run_dir / "production_input" / "media_manifest.json").is_file())

            with self.assertRaisesRegex(RuntimeError, "exactly match"):
                cli._materialize_production_manifest(
                    run_dir,
                    {**authorization, "authorized_media_asset_ids": ["one"]},
                )
            changed = dict(source)
            changed["media"] = [dict(item) for item in source["media"]]
            changed["media"][0]["url"] = "https://res.cloudinary.com/example/image/upload/replaced.jpg"
            (reports / "02_authorised_media_manifest.json").write_text(
                json.dumps(changed), encoding="utf-8"
            )
            with self.assertRaisesRegex(RuntimeError, "accepted preview provenance"):
                cli._materialize_production_manifest(run_dir, authorization)


if __name__ == "__main__":
    unittest.main()
