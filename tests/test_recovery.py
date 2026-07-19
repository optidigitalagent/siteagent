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


INSTAGRAM_URL = "https://www.instagram.com/example_business/"


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

    def test_preview_ready_is_not_completion_or_telegram_delivery(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            queue = TelegramJobQueue(Path(temp) / "jobs.json", git_sync=False)
            job = queue.enqueue(INSTAGRAM_URL, chat_id=42)
            queue.fail(job.id, "research failed all facts")
            queue.reclaim_failed_preview(job.id)

            ready = queue.mark_preview_ready(
                job.id,
                preview_url="https://preview.example.pages.dev",
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

    def test_resumed_job_notifies_before_queue_completion(self) -> None:
        job = SimpleNamespace(
            id="job-1",
            instagram_url=INSTAGRAM_URL,
            chat_id=42,
            status="running",
            run_dir="runs/job-1",
        )
        queue = Mock()
        queue.next_interrupted.return_value = job
        publish = DeploymentResult(
            provider="cloudflare_pages",
            project_name="siteagent-example",
            production_url="https://siteagent-example.pages.dev",
            deployment_url="https://deploy.siteagent-example.pages.dev",
            status="success",
            deployed_at="2026-07-14T00:00:00+00:00",
            verification_status="verified",
        )
        orchestrator = Mock()
        orchestrator.run.return_value = SimpleNamespace(publish=publish)
        notifier = Mock()
        events: list[str] = []
        queue.record_checkpoints.side_effect = lambda *args, **kwargs: events.append("checkpoints")
        queue.mark_notification_sending.side_effect = lambda *args, **kwargs: events.append("sending")
        notifier.send_done.side_effect = lambda *args, **kwargs: events.append("notified") or {}
        queue.record_notification_sent.side_effect = lambda *args, **kwargs: events.append("receipt")
        queue.complete.side_effect = lambda *args, **kwargs: events.append("completed")

        with (
            patch.object(cli, "_pending_job_queue", return_value=queue),
            patch.object(cli, "SiteAgentOrchestrator", return_value=orchestrator),
            patch.object(cli, "TelegramNotifier", return_value=notifier),
        ):
            cli.run_pending_job()

        orchestrator.run.assert_called_once_with(
            INSTAGRAM_URL,
            production=True,
            run_id="job-1",
            run_path=Path("runs/job-1"),
        )
        self.assertEqual(events, ["checkpoints", "sending", "notified", "receipt", "completed"])
        queue.complete.assert_called_once_with(
            "job-1", site_url=publish.production_url, repo_url=publish.repo_url
        )

    def test_preview_resume_uses_same_run_and_never_notifies_or_completes(self) -> None:
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
        orchestrator = Mock()
        orchestrator.run.return_value = SimpleNamespace(
            publish=SimpleNamespace(
                deployment_url="https://hash.siteagent-preview.pages.dev",
                production_url="",
            )
        )

        with (
            patch.object(cli, "_pending_job_queue", return_value=queue),
            patch.object(cli, "SiteAgentOrchestrator", return_value=orchestrator),
            patch.object(cli, "TelegramNotifier") as notifier_class,
        ):
            cli.run_preview_job("job-preview")

        orchestrator.run.assert_called_once_with(
            INSTAGRAM_URL,
            production=False,
            preview=True,
            run_id="job-preview",
            run_path=Path(r"runs\job-preview"),
        )
        queue.mark_preview_ready.assert_called_once()
        self.assertEqual(
            queue.mark_preview_ready.call_args.kwargs["preview_url"],
            "https://hash.siteagent-preview.pages.dev",
        )
        queue.complete.assert_not_called()
        queue.mark_notification_sending.assert_not_called()
        notifier_class.assert_not_called()

    def test_preview_ready_revalidates_same_run_without_duplicate_queue_event(self) -> None:
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
        orchestrator.run.return_value = SimpleNamespace(
            publish=SimpleNamespace(
                deployment_url=ready.preview_url,
                production_url="",
            )
        )

        with (
            patch.object(cli, "_pending_job_queue", return_value=queue),
            patch.object(cli, "SiteAgentOrchestrator", return_value=orchestrator),
        ):
            cli.run_preview_job("job-preview")

        orchestrator.run.assert_called_once_with(
            INSTAGRAM_URL,
            production=False,
            preview=True,
            run_id="job-preview",
            run_path=Path(r"runs\job-preview"),
        )
        queue.mark_preview_ready.assert_not_called()
        queue.reclaim_failed_preview.assert_not_called()

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


if __name__ == "__main__":
    unittest.main()
