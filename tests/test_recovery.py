from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from site_agent import cli
from site_agent.job_queue import InterruptedDeliveryUncertain, TelegramJobQueue
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
            self.assertEqual(queue.next_pending().instagram_url, "https://www.instagram.com/later/")

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


if __name__ == "__main__":
    unittest.main()
