from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from site_agent import cli
from site_agent.job_queue import (
    PreviewNotificationNotAllowed,
    TelegramJobQueue,
)
from site_agent.preview import LiveVerificationError, PreviewDeploymentResult, PreviewLiveVerifier
from site_agent.telegram_notify import TelegramNotifier


URL = "https://hash.siteagent-preview-example.pages.dev"
DEPLOYMENT_ID = "preview-deployment-1"
PROJECT = "siteagent-preview-example"
BRANCH = "preview-job-preview"
INSTAGRAM_URL = "https://www.instagram.com/example_business/"


def verified_preview(**changes) -> PreviewDeploymentResult:
    payload = {
        "project_name": PROJECT,
        "preview_url": URL,
        "deployment_url": URL,
        "deployment_id": DEPLOYMENT_ID,
        "branch": BRANCH,
        "deployed_at": "2026-07-19T00:00:00+00:00",
        "staging_dir": "runs/job/preview_publish",
    }
    payload.update(changes)
    return PreviewDeploymentResult(**payload)


def ready_queue(path: Path) -> tuple[TelegramJobQueue, object]:
    queue = TelegramJobQueue(path, git_sync=False)
    job = queue.enqueue(INSTAGRAM_URL, chat_id=42)
    job = queue.mark_preview_ready(
        job.id,
        preview_url=URL,
        deployment_id=DEPLOYMENT_ID,
        project_name=PROJECT,
        branch=BRANCH,
    )
    return queue, job


def accepted_receipt(attempt_id: str, *, url: str = URL, deployment_id: str = DEPLOYMENT_ID):
    return {
        "status": "accepted",
        "sent_at": "2026-07-19T00:00:01+00:00",
        "preview_url_sha256": hashlib.sha256(url.encode("utf-8")).hexdigest(),
        "deployment_id": deployment_id,
        "attempt_id": attempt_id,
    }


class PreviewNotifierTests(unittest.TestCase):
    def test_message_button_and_receipt_are_preview_specific_and_safe(self) -> None:
        bot = Mock()
        bot.send_message = AsyncMock(
            return_value=SimpleNamespace(date=datetime(2026, 7, 19, tzinfo=timezone.utc))
        )
        with patch("site_agent.telegram_notify.Bot", return_value=bot):
            receipt = TelegramNotifier(token="unused").send_preview_ready(
                42,
                business_name="Amidental Kiev",
                preview=verified_preview(),
                attempt_id="attempt-1",
            )

        kwargs = bot.send_message.await_args.kwargs
        self.assertIn("Сайт готов к проверке", kwargs["text"])
        self.assertIn("Бизнес: Amidental Kiev", kwargs["text"])
        self.assertIn(f"Preview: {URL}", kwargs["text"])
        self.assertIn("не является production", kwargs["text"])
        button = kwargs["reply_markup"].inline_keyboard[0][0]
        self.assertEqual(button.text, "Открыть сайт")
        self.assertEqual(button.url, URL)
        self.assertEqual(
            set(receipt),
            {
                "status",
                "sent_at",
                "preview_url_sha256",
                "deployment_id",
                "attempt_id",
            },
        )
        self.assertNotIn("chat_id", receipt)
        self.assertNotIn("message_id", receipt)

    def test_notifier_rejects_root_malicious_or_unbound_preview_urls(self) -> None:
        notifier = TelegramNotifier(token="unused")
        invalid = (
            verified_preview(
                preview_url=f"https://{PROJECT}.pages.dev",
                deployment_url=f"https://{PROJECT}.pages.dev",
            ),
            verified_preview(
                preview_url=f"https://hash.{PROJECT}.pages.dev.evil.example",
                deployment_url=f"https://hash.{PROJECT}.pages.dev.evil.example",
            ),
            verified_preview(
                preview_url=URL + "?token=bad",
                deployment_url=URL + "?token=bad",
            ),
            verified_preview(deployment_id=""),
            verified_preview(deployment_url="https://other.example.pages.dev"),
        )
        for preview in invalid:
            with self.subTest(preview=preview.preview_url):
                with self.assertRaisesRegex(ValueError, "verified isolated preview"):
                    notifier.validate_preview_ready("Business", preview)


class PreviewQueueTests(unittest.TestCase):
    def test_preview_delivery_state_is_separate_safe_and_at_most_once(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            queue, job = ready_queue(Path(temp) / "jobs.json")
            sending = queue.mark_preview_notification_sending(
                job.id,
                preview_url=URL,
                deployment_id=DEPLOYMENT_ID,
            )
            sent = queue.record_preview_notification_sent(
                job.id,
                accepted_receipt(sending.telegram_preview_notification_attempt_id),
            )

            self.assertEqual(sent.status, "preview_ready")
            self.assertEqual(sent.workflow_lane, "preview")
            self.assertEqual(sent.telegram_preview_notification_status, "sent")
            self.assertEqual(sent.telegram_notification_status, "not_started")
            self.assertEqual(sent.site_url, "")
            self.assertEqual(sent.repo_url, "")
            self.assertFalse(sent.production_authorization)
            self.assertNotIn("chat_id", sent.telegram_preview_receipt)
            self.assertNotIn("message_id", sent.telegram_preview_receipt)
            with self.assertRaises(PreviewNotificationNotAllowed):
                queue.mark_preview_notification_sending(
                    job.id,
                    preview_url=URL,
                    deployment_id=DEPLOYMENT_ID,
                )

    def test_new_deployment_permits_one_send_but_reverted_key_stays_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            queue, job = ready_queue(Path(temp) / "jobs.json")
            sending = queue.mark_preview_notification_sending(
                job.id, preview_url=URL, deployment_id=DEPLOYMENT_ID
            )
            queue.record_preview_notification_sent(
                job.id, accepted_receipt(sending.telegram_preview_notification_attempt_id)
            )
            new_url = "https://new.siteagent-preview-example.pages.dev"
            changed = queue.mark_preview_ready(
                job.id,
                preview_url=new_url,
                deployment_id="preview-deployment-2",
                project_name=PROJECT,
                branch=BRANCH,
            )
            self.assertEqual(changed.telegram_preview_notification_status, "not_started")
            queue.mark_preview_notification_sending(
                job.id,
                preview_url=new_url,
                deployment_id="preview-deployment-2",
            )

            # Simulate a later reconciled return to the old deployment key.
            queue.mark_preview_notification_unknown(job.id, "network timeout")
            reverted = queue.mark_preview_ready(
                job.id,
                preview_url=URL,
                deployment_id=DEPLOYMENT_ID,
                project_name=PROJECT,
                branch=BRANCH,
            )
            self.assertEqual(reverted.telegram_preview_notification_status, "sent")
            with self.assertRaises(PreviewNotificationNotAllowed):
                queue.mark_preview_notification_sending(
                    job.id, preview_url=URL, deployment_id=DEPLOYMENT_ID
                )

    def test_syntactic_url_change_does_not_reset_same_deployment(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            queue, job = ready_queue(Path(temp) / "jobs.json")
            sending = queue.mark_preview_notification_sending(
                job.id, preview_url=URL, deployment_id=DEPLOYMENT_ID
            )
            queue.record_preview_notification_sent(
                job.id, accepted_receipt(sending.telegram_preview_notification_attempt_id)
            )
            same = queue.mark_preview_ready(
                job.id,
                preview_url=URL + "/",
                deployment_id=DEPLOYMENT_ID,
                project_name=PROJECT,
                branch=BRANCH,
            )
            self.assertEqual(same.telegram_preview_notification_status, "sent")
            with self.assertRaises(PreviewNotificationNotAllowed):
                queue.mark_preview_notification_sending(
                    job.id,
                    preview_url=URL + "/",
                    deployment_id=DEPLOYMENT_ID,
                )

    def test_uncertain_error_is_redacted_and_does_not_fail_preview(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            queue, job = ready_queue(Path(temp) / "jobs.json")
            queue.mark_preview_notification_sending(
                job.id, preview_url=URL, deployment_id=DEPLOYMENT_ID
            )
            unknown = queue.mark_preview_notification_unknown(
                job.id,
                "POST https://api.telegram.org/botsecret-token/sendMessage "
                "chat_id=123 message_id=456 timed out",
            )
            serialized = queue.path.read_text(encoding="utf-8")
            self.assertEqual(unknown.status, "preview_ready")
            self.assertEqual(unknown.telegram_preview_notification_status, "unknown")
            self.assertNotIn("secret-token", serialized)
            self.assertNotIn("chat_id=123", serialized)
            self.assertNotIn("message_id=456", serialized)
            self.assertNotIn("secret request payload", serialized)

    def test_one_resend_authorization_is_consumed_by_one_attempt(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            queue, job = ready_queue(Path(temp) / "jobs.json")
            queue.mark_preview_notification_sending(
                job.id, preview_url=URL, deployment_id=DEPLOYMENT_ID
            )
            queue.mark_preview_notification_unknown(job.id, "timeout")
            queue.authorize_preview_resend(job.id, reason="user approved")
            queue.mark_preview_notification_sending(
                job.id,
                preview_url=URL,
                deployment_id=DEPLOYMENT_ID,
                authorized_resend=True,
            )
            with self.assertRaises(PreviewNotificationNotAllowed):
                queue.mark_preview_notification_sending(
                    job.id,
                    preview_url=URL,
                    deployment_id=DEPLOYMENT_ID,
                    authorized_resend=True,
                )

    def test_production_authorization_cannot_interleave_with_preview_sending(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            queue, job = ready_queue(Path(temp) / "jobs.json")
            sending = queue.mark_preview_notification_sending(
                job.id, preview_url=URL, deployment_id=DEPLOYMENT_ID
            )
            with self.assertRaises(PreviewNotificationNotAllowed):
                queue.record_production_authorization(job.id, {"approved": True})
            sent = queue.record_preview_notification_sent(
                job.id, accepted_receipt(sending.telegram_preview_notification_attempt_id)
            )
            self.assertEqual(sent.workflow_lane, "preview")
            self.assertFalse(sent.production_authorization)

    def test_receipt_rejects_payload_in_sent_at(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            queue, job = ready_queue(Path(temp) / "jobs.json")
            sending = queue.mark_preview_notification_sending(
                job.id, preview_url=URL, deployment_id=DEPLOYMENT_ID
            )
            unsafe = accepted_receipt(sending.telegram_preview_notification_attempt_id)
            unsafe["sent_at"] = '{"chat_id":123,"text":"request payload"}'
            with self.assertRaisesRegex(ValueError, "invalid sent_at"):
                queue.record_preview_notification_sent(job.id, unsafe)

    def test_concurrent_sending_compare_and_set_allows_one_attempt(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "jobs.json"
            queue, job = ready_queue(path)

            def claim():
                local = TelegramJobQueue(path, git_sync=False)
                try:
                    return local.mark_preview_notification_sending(
                        job.id, preview_url=URL, deployment_id=DEPLOYMENT_ID
                    ).telegram_preview_notification_attempt_id
                except PreviewNotificationNotAllowed:
                    return "blocked"

            with ThreadPoolExecutor(max_workers=2) as executor:
                outcomes = list(executor.map(lambda _: claim(), range(2)))
            self.assertEqual(outcomes.count("blocked"), 1)
            self.assertEqual(len([item for item in outcomes if item != "blocked"]), 1)

    def test_concurrent_authorized_resend_allows_one_attempt(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "jobs.json"
            queue, job = ready_queue(path)
            queue.mark_preview_notification_sending(
                job.id, preview_url=URL, deployment_id=DEPLOYMENT_ID
            )
            queue.mark_preview_notification_unknown(job.id, "timeout")
            queue.authorize_preview_resend(job.id, reason="user approved")

            def claim():
                local = TelegramJobQueue(path, git_sync=False)
                try:
                    return local.mark_preview_notification_sending(
                        job.id,
                        preview_url=URL,
                        deployment_id=DEPLOYMENT_ID,
                        authorized_resend=True,
                    ).telegram_preview_notification_attempt_id
                except PreviewNotificationNotAllowed:
                    return "blocked"

            with ThreadPoolExecutor(max_workers=2) as executor:
                outcomes = list(executor.map(lambda _: claim(), range(2)))
            self.assertEqual(outcomes.count("blocked"), 1)


class PreviewLiveBindingTests(unittest.TestCase):
    def test_live_verifier_rejects_redirect_outside_exact_deployment_origin(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            site = Path(temp)
            (site / "index.html").write_text(
                '<html><head><meta name="robots" content="noindex">'
                '<meta name="siteagent-business-id" content="marker"></head></html>',
                encoding="utf-8",
            )
            response = SimpleNamespace(
                status_code=200,
                headers={"X-Robots-Tag": "noindex"},
                text=(site / "index.html").read_text(encoding="utf-8"),
                url="https://evil.example/",
            )
            verifier = PreviewLiveVerifier(
                http_get=Mock(return_value=response),
                retries=1,
                backoff_seconds=0,
            )
            with self.assertRaisesRegex(LiveVerificationError, "exact deployment origin"):
                verifier.verify(URL, site_dir=site, expected_marker="marker")

    def test_live_verifier_rejects_off_origin_redirect_hop_that_returns(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            site = Path(temp)
            html = (
                '<html><head><meta name="robots" content="noindex">'
                '<meta name="siteagent-business-id" content="marker"></head></html>'
            )
            (site / "index.html").write_text(html, encoding="utf-8")
            history = [
                SimpleNamespace(
                    url="https://evil.example/bounce",
                    headers={"Location": URL},
                )
            ]
            response = SimpleNamespace(
                status_code=200,
                headers={"X-Robots-Tag": "noindex"},
                text=html,
                url=URL,
                history=history,
            )
            verifier = PreviewLiveVerifier(
                http_get=Mock(return_value=response),
                retries=1,
                backoff_seconds=0,
            )
            with self.assertRaisesRegex(LiveVerificationError, "exact deployment origin"):
                verifier.verify(URL, site_dir=site, expected_marker="marker")


class PreviewNotificationCliTests(unittest.TestCase):
    def _job(self, run_dir: Path):
        return SimpleNamespace(
            id="job-preview",
            run_id="job-preview",
            instagram_url=INSTAGRAM_URL,
            chat_id=42,
            status="preview_ready",
            workflow_lane="preview",
            run_dir=str(run_dir),
            preview_url=URL,
            preview_deployment_id=DEPLOYMENT_ID,
            preview_project_name=PROJECT,
            preview_branch=BRANCH,
            site_url="",
            repo_url="",
            production_authorization={},
            telegram_preview_notification_status="not_started",
        )

    def test_preview_notify_revalidates_existing_preview_without_orchestrator_or_upload(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            run_dir = Path(temp)
            (run_dir / "preview_publish").mkdir()
            (run_dir / "preview_deployment.json").write_text(
                verified_preview(staging_dir=str(run_dir / "preview_publish")).model_dump_json(),
                encoding="utf-8",
            )
            job = self._job(run_dir)
            queue = Mock()
            queue.get.return_value = job
            with (
                patch.object(cli, "_pending_job_queue", return_value=queue),
                patch.object(cli, "_deliver_preview_notification", return_value={"status": "accepted"}) as deliver,
                patch.object(cli, "SiteAgentOrchestrator") as orchestrator,
            ):
                cli.run_preview_notification(job.id)
            orchestrator.assert_not_called()
            deliver.assert_called_once()
            self.assertTrue(deliver.call_args.kwargs["live_verify"])

    def test_preflight_failure_does_not_mark_sending(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            run_dir = Path(temp)
            reports = run_dir / "generation_reports"
            reports.mkdir()
            (reports / "01_research.json").write_text(
                json.dumps({"business_name": "Amidental Kiev"}), encoding="utf-8"
            )
            job = self._job(run_dir)
            queue = Mock()
            notifier = Mock()
            notifier.validate_preview_ready.side_effect = RuntimeError("missing token")
            with (
                patch.object(cli, "TelegramNotifier", return_value=notifier),
                self.assertRaisesRegex(RuntimeError, "missing token"),
            ):
                cli._deliver_preview_notification(
                    queue,
                    job,
                    verified_preview(),
                    run_dir=run_dir,
                    live_verify=False,
                )
            queue.mark_preview_notification_sending.assert_not_called()

    def test_transport_failure_becomes_unknown_without_queue_fail(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            run_dir = Path(temp)
            reports = run_dir / "generation_reports"
            reports.mkdir()
            (reports / "01_research.json").write_text(
                json.dumps({"business_name": "Amidental Kiev"}), encoding="utf-8"
            )
            job = self._job(run_dir)
            queue = Mock()
            queue.mark_preview_notification_sending.return_value = SimpleNamespace(
                telegram_preview_notification_attempt_id="attempt-1"
            )
            notifier = Mock()
            notifier.send_preview_ready.side_effect = RuntimeError(
                "https://api.telegram.org/botsecret-token/sendMessage timed out "
                'payload={"chat_id":123,"message_id":456,"text":"secret request payload"}'
            )
            with (
                patch.object(cli, "TelegramNotifier", return_value=notifier),
                self.assertRaisesRegex(RuntimeError, "outcome is uncertain") as raised,
            ):
                cli._deliver_preview_notification(
                    queue,
                    job,
                    verified_preview(),
                    run_dir=run_dir,
                    live_verify=False,
                )
            queue.mark_preview_notification_unknown.assert_called_once()
            stored_error = queue.mark_preview_notification_unknown.call_args.args[1]
            self.assertNotIn("secret-token", stored_error)
            self.assertNotIn("secret request payload", str(raised.exception))
            self.assertNotIn("chat_id", str(raised.exception))
            queue.fail.assert_not_called()

    def test_receipt_persistence_failure_is_not_reclassified_as_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            run_dir = Path(temp)
            reports = run_dir / "generation_reports"
            reports.mkdir()
            (reports / "01_research.json").write_text(
                json.dumps({"business_name": "Amidental Kiev"}), encoding="utf-8"
            )
            job = self._job(run_dir)
            queue = Mock()
            queue.mark_preview_notification_sending.return_value = SimpleNamespace(
                telegram_preview_notification_attempt_id="attempt-1"
            )
            queue.record_preview_notification_sent.side_effect = RuntimeError("git push failed")
            notifier = Mock()
            notifier.send_preview_ready.return_value = accepted_receipt("attempt-1")
            with (
                patch.object(cli, "TelegramNotifier", return_value=notifier),
                self.assertRaisesRegex(RuntimeError, "receipt persistence failed"),
            ):
                cli._deliver_preview_notification(
                    queue,
                    job,
                    verified_preview(),
                    run_dir=run_dir,
                    live_verify=False,
                )
            queue.mark_preview_notification_unknown.assert_not_called()

    def test_resend_requires_explicit_queue_authorization(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            job = self._job(Path(temp))
            job.telegram_preview_notification_status = "sent"
            queue = Mock()
            queue.get.return_value = job
            with (
                patch.object(cli, "_pending_job_queue", return_value=queue),
                self.assertRaises(PreviewNotificationNotAllowed),
            ):
                cli.run_preview_notification(job.id)
            queue.authorize_preview_resend.assert_not_called()


if __name__ == "__main__":
    unittest.main()
