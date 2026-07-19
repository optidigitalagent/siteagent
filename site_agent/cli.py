from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from site_agent.config import settings
from site_agent.job_queue import (
    InterruptedDeliveryUncertain,
    PreviewNotificationNotAllowed,
    PreviewRecoveryNotAllowed,
    TelegramJobQueue,
)
from site_agent.identifiers import stable_business_id
from site_agent.json_io import write_json
from site_agent.models import PublishResult
from site_agent.orchestrator import SiteAgentOrchestrator
from site_agent.publisher import LiveSiteVerifier
from site_agent.preview import PreviewDeploymentResult, PreviewLiveVerifier
from site_agent.telegram_notify import TelegramNotifier


GO_ALIASES = {"go", "го"}


def run_instagram_url(instagram_url: str) -> None:
    result = SiteAgentOrchestrator().run(instagram_url)
    print("Готово:")
    print(result.publish.production_url)


def run_pending_job() -> None:
    """Claim or resume the next Telegram job in the isolated preview lane."""
    queue = _pending_job_queue()
    try:
        interrupted = queue.next_interrupted()
        job = interrupted if getattr(interrupted, "status", None) == "running" else None
    except RuntimeError as exc:
        if queue.git_sync and not settings.telegram_inbox_git_sync:
            raise RuntimeError(
                "Не удалось автоматически синхронизировать Telegram inbox через git. "
                "Проверьте git remote/push-доступ или задайте TELEGRAM_INBOX_GIT_SYNC=true."
            ) from exc
        raise
    if job is None:
        try:
            pending_job = queue.next_pending()
        except RuntimeError as exc:
            if queue.git_sync and not settings.telegram_inbox_git_sync:
                raise RuntimeError(
                    "Не удалось автоматически синхронизировать Telegram inbox через git. "
                    "Проверьте git remote/push-доступ или задайте TELEGRAM_INBOX_GIT_SYNC=true."
                ) from exc
            raise
        if pending_job is not None:
            try:
                job = queue.claim_next()
            except RuntimeError as exc:
                if queue.git_sync and not settings.telegram_inbox_git_sync:
                    raise RuntimeError(
                        "Не удалось автоматически синхронизировать Telegram inbox через git. "
                        "Проверьте git remote/push-доступ или задайте TELEGRAM_INBOX_GIT_SYNC=true."
                    ) from exc
                raise
        else:
            recoverable = queue.next_recoverable_preview()
            if recoverable is not None:
                job = queue.reclaim_failed_preview(recoverable.id)
        if job is None:
            print("Нет pending-задач из Telegram.")
            return

    stored_run_dir = getattr(job, "run_dir", "")
    run_dir = (
        stored_run_dir
        if isinstance(stored_run_dir, str) and stored_run_dir
        else str(_existing_run_dir(job.instagram_url) or settings.runs_dir / job.id)
    )
    if not job.run_dir:
        job = queue.set_run_dir(job.id, run_dir)

    _execute_preview_job(queue, job, Path(run_dir))


def run_preview_job(job_id: str) -> None:
    """Resume one existing run into an isolated review preview.

    This lane deliberately performs no production completion and constructs no
    Telegram notifier. The queue remains review-only until a later, explicitly
    authorized production workflow promotes it.
    """
    queue = _pending_job_queue(preview_local=True)
    job = queue.get(job_id)
    was_preview_ready = job.status == "preview_ready" and bool(job.preview_url)
    if job.status == "failed":
        job = queue.reclaim_failed_preview(job_id)
    elif job.status in {"running", "preview_ready"} and job.telegram_notification_status == "not_started":
        pass
    else:
        raise PreviewRecoveryNotAllowed(job_id, f"job status is {job.status}")

    stored_run_dir = job.run_dir
    run_dir = stored_run_dir or str(settings.runs_dir / (job.run_id or job.id))
    if not stored_run_dir:
        job = queue.set_run_dir(job.id, run_dir)

    _execute_preview_job(queue, job, Path(run_dir), was_preview_ready=was_preview_ready)


def _execute_preview_job(
    queue: TelegramJobQueue,
    job: object,
    run_dir: Path,
    *,
    was_preview_ready: bool = False,
) -> None:
    try:
        result = SiteAgentOrchestrator().run(
            job.instagram_url,
            production=False,
            preview=True,
            run_id=getattr(job, "run_id", "") or job.id,
            run_path=run_dir,
        )
        publish = _preview_result_from_result(result)
        preview_url = publish.preview_url
        if not (was_preview_ready and job.preview_url == preview_url):
            job = queue.mark_preview_ready(
                job.id,
                preview_url=preview_url,
                deployment_id=publish.deployment_id,
                project_name=publish.project_name,
                branch=publish.branch,
                checkpoints={
                    "research_completed": "completed_and_valid",
                    "brand_identity_completed": "completed_and_valid",
                    "generation_completed": "completed_and_valid",
                    "technical_gate_completed": "completed_and_valid",
                    "critics_completed": "completed_and_valid",
                    "brand_fidelity_completed": "completed_and_valid",
                    "acceptance_completed": "completed_and_valid",
                    "preview_deployment_completed": "completed_and_valid",
                    "preview_live_verified": "completed_and_valid",
                },
            )
        else:
            job = queue.get(job.id)
    except Exception as exc:
        if not was_preview_ready:
            queue.fail(job.id, str(exc))
        raise
    print("Preview готово:")
    print(preview_url)
    if getattr(job, "telegram_preview_notification_status", "not_started") == "not_started":
        try:
            _deliver_preview_notification(
                queue,
                job,
                publish,
                run_dir=run_dir,
                live_verify=False,
            )
        except Exception:
            print(
                "Telegram preview: "
                + str(
                    getattr(
                        queue.get(job.id),
                        "telegram_preview_notification_status",
                        "unknown",
                    )
                )
            )
            raise
    print(
        "Telegram preview: "
        + str(getattr(queue.get(job.id), "telegram_preview_notification_status", "unknown"))
    )


def _preview_result_from_result(result: object) -> PreviewDeploymentResult:
    publish = getattr(result, "publish", None)
    try:
        validated = PreviewDeploymentResult.model_validate(
            publish.model_dump() if hasattr(publish, "model_dump") else publish
        )
    except Exception as exc:
        raise RuntimeError("Preview publishing returned a non-preview deployment result.") from exc
    if (
        validated.provider != "cloudflare_pages_preview"
        or validated.environment != "preview"
        or validated.verification_status != "verified"
        or not validated.project_name.startswith("siteagent-preview-")
        or not validated.branch.startswith("preview-")
        or not validated.preview_url.startswith("https://")
        or validated.preview_url == f"https://{validated.project_name}.pages.dev"
    ):
        raise RuntimeError("Preview publishing did not return a verified isolated preview deployment.")
    return validated


def _deliver_preview_notification(
    queue: TelegramJobQueue,
    job: object,
    preview: PreviewDeploymentResult,
    *,
    run_dir: Path,
    live_verify: bool,
    authorized_resend: bool = False,
) -> dict[str, str | int]:
    """Deliver one preview URL without changing the preview or production lane."""
    if (
        getattr(job, "status", "") != "preview_ready"
        or getattr(job, "workflow_lane", "") != "preview"
        or getattr(job, "preview_url", "") != preview.preview_url
        or getattr(job, "preview_deployment_id", "") != preview.deployment_id
        or getattr(job, "preview_project_name", "") != preview.project_name
        or getattr(job, "preview_branch", "") != preview.branch
        or getattr(job, "site_url", "")
        or getattr(job, "repo_url", "")
        or bool(getattr(job, "production_authorization", {}))
    ):
        raise PreviewNotificationNotAllowed(
            getattr(job, "id", "unknown"),
            "queue metadata does not exactly match the isolated preview deployment",
        )
    if live_verify:
        PreviewLiveVerifier().verify(
            preview.preview_url,
            site_dir=run_dir / "preview_publish",
            expected_marker=stable_business_id(job.instagram_url),
        )
    business_name = _preview_business_name(run_dir)
    notifier = TelegramNotifier()
    # Token, message identity and all deployment invariants are checked before
    # the durable sending state, so guaranteed pre-request failures remain
    # safely retryable through preview-notify without a generation/deploy rerun.
    notifier.validate_preview_ready(business_name, preview)
    sending = queue.mark_preview_notification_sending(
        job.id,
        preview_url=preview.preview_url,
        deployment_id=preview.deployment_id,
        authorized_resend=authorized_resend,
    )
    try:
        receipt = notifier.send_preview_ready(
            job.chat_id,
            business_name=business_name,
            preview=preview,
            attempt_id=sending.telegram_preview_notification_attempt_id,
        )
    except Exception as exc:
        safe_error = _safe_telegram_error(exc)
        queue.mark_preview_notification_unknown(job.id, "telegram_transport_uncertain")
        raise RuntimeError(
            "Telegram preview notification outcome is uncertain; automatic resend is blocked. "
            f"Safe error: {safe_error}"
        ) from None
    try:
        if authorized_resend:
            queue.record_preview_resend_sent(job.id, receipt)
        else:
            queue.record_preview_notification_sent(job.id, receipt)
    except Exception as exc:
        raise RuntimeError(
            "Telegram accepted the preview notification, but receipt persistence failed; "
            "automatic resend remains blocked."
        ) from exc
    return receipt


def _preview_business_name(run_dir: Path) -> str:
    candidates = (
        run_dir / "generation_reports" / "01_research.json",
        run_dir / "generation_reports" / "00_one_link_intake.json",
    )
    for path in candidates:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        value = payload.get("business_name")
        if isinstance(value, str) and value.strip():
            return " ".join(value.split())
    raise RuntimeError("Verified preview business name is missing from the run artifacts.")


def _safe_telegram_error(exc: Exception) -> str:
    normalized = str(exc).casefold()
    if "timeout" in normalized or "timed out" in normalized:
        return "telegram_transport_timeout"
    return "telegram_transport_uncertain"


def _load_existing_preview(job: object, run_dir: Path) -> PreviewDeploymentResult:
    deployment_path = run_dir / "preview_deployment.json"
    try:
        preview = PreviewDeploymentResult.model_validate_json(
            deployment_path.read_text(encoding="utf-8")
        )
    except (OSError, ValueError) as exc:
        raise RuntimeError("A verified preview_deployment.json is required.") from exc
    if (
        preview.preview_url != getattr(job, "preview_url", "")
        or preview.deployment_id != getattr(job, "preview_deployment_id", "")
        or preview.project_name != getattr(job, "preview_project_name", "")
        or preview.branch != getattr(job, "preview_branch", "")
    ):
        raise RuntimeError("Queue preview metadata does not match preview_deployment.json.")
    return preview


def run_preview_notification(
    job_id: str,
    *,
    authorized_resend: bool = False,
) -> None:
    """Notify an existing verified preview without generation or Cloudflare upload."""
    queue = _pending_job_queue()
    job = queue.get(job_id)
    if job.status != "preview_ready" or job.workflow_lane != "preview":
        raise PreviewNotificationNotAllowed(job_id, "job is not preview_ready")
    if authorized_resend:
        job = queue.authorize_preview_resend(
            job_id,
            reason="User explicitly invoked preview-resend with authorization.",
        )
    elif job.telegram_preview_notification_status != "not_started":
        raise PreviewNotificationNotAllowed(
            job_id,
            f"notification state is {job.telegram_preview_notification_status}",
        )
    run_dir = Path(job.run_dir or settings.runs_dir / (job.run_id or job.id))
    preview = _load_existing_preview(job, run_dir)
    print("Preview готово:")
    print(preview.preview_url)
    try:
        receipt = _deliver_preview_notification(
            queue,
            job,
            preview,
            run_dir=run_dir,
            live_verify=True,
            authorized_resend=authorized_resend,
        )
    except Exception:
        print(
            "Telegram preview: "
            + str(queue.get(job.id).telegram_preview_notification_status)
        )
        raise
    print("Telegram preview: sent")
    print(f"Telegram receipt: {receipt['status']}")


def _pending_job_queue(*, preview_local: bool = False) -> TelegramJobQueue:
    if preview_local:
        return TelegramJobQueue(git_sync=False)
    if settings.telegram_inbox_git_sync:
        return TelegramJobQueue()

    if _has_git_remote():
        return TelegramJobQueue(git_sync=True)

    return TelegramJobQueue(git_sync=False)


def _has_git_remote() -> bool:
    result = subprocess.run(
        ["git", "remote", "get-url", settings.telegram_inbox_git_remote],
        cwd=Path.cwd(),
        text=True,
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


def _existing_run_dir(instagram_url: str) -> Path | None:
    """Find the latest valid legacy run for this exact queue URL.

    Earlier queue entries did not persist a run directory.  Matching the
    validated research artifact lets an interrupted legacy job resume its own
    work rather than starting a timestamped duplicate.
    """
    candidates = sorted(
        (path for path in settings.runs_dir.iterdir() if path.is_dir()),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    ) if settings.runs_dir.is_dir() else []
    for candidate in candidates:
        research_path = candidate / "generation_reports" / "01_research.json"
        try:
            payload = json.loads(research_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if payload.get("instagram_url") == instagram_url:
            return candidate
    return None


def run_authorized_manual_resend(job_id: str) -> None:
    """Send one explicitly authorized recovery notification without rerunning delivery work."""
    # A recovery command must not be blocked by unrelated user changes in the
    # worktree.  It updates only the already-local queue entry for this job.
    queue = TelegramJobQueue(git_sync=False)
    job = queue.get(job_id)
    run_dir = Path(job.run_dir) if job.run_dir else _existing_run_dir(job.instagram_url)
    if run_dir is None:
        raise RuntimeError(f"No persisted run directory found for Telegram job {job_id}.")
    deployment_path = run_dir / "deployment.json"
    try:
        publish = PublishResult.model_validate_json(deployment_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"No valid verified deployment record found for Telegram job {job_id}.") from exc
    if not publish.is_verified_production:
        raise RuntimeError("Manual resend requires a live-verified HTTPS deployment.")

    # This verifies the exact existing Pages URL and marker; it never invokes
    # research, generation, critics, acceptance, or Cloudflare upload.
    LiveSiteVerifier(retries=1).verify(
        publish.production_url,
        site_dir=run_dir / "site",
        expected_marker=stable_business_id(job.instagram_url),
    )

    queue.authorize_manual_resend(
        job.id,
        reason="User confirmed no legacy final message was received and authorized one resend.",
    )
    try:
        receipt = TelegramNotifier().send_done(job.chat_id, publish)
    except Exception as exc:
        queue.mark_notification_unknown(job.id, str(exc))
        raise RuntimeError(f"Telegram resend failed: {exc}") from exc
    queue.record_notification_sent(job.id, receipt)
    queue.complete(job.id, site_url=publish.production_url, repo_url=publish.repo_url)
    print("Готово:")
    print(publish.production_url)


def run_production_promotion(job_id: str, *, authorized: bool) -> None:
    """Promote an approved preview only after a separately persisted preflight."""
    if not authorized:
        raise RuntimeError("Production promotion requires --authorize-production.")
    queue = _pending_job_queue()
    job = queue.get(job_id)
    if job.status != "preview_ready":
        raise RuntimeError("Production promotion requires a preview_ready job.")
    run_dir = Path(job.run_dir or settings.runs_dir / (job.run_id or job.id))
    authorization_path = run_dir / "production_authorization.json"
    try:
        authorization = json.loads(authorization_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RuntimeError(
            "Production promotion requires a valid production_authorization.json artifact."
        ) from exc
    required = (
        "approved",
        "production_media_rights_confirmed",
        "contacts_confirmed",
        "cta_copy_approved",
        "production_preflight_passed",
        "production_live_qa_required",
    )
    missing = [key for key in required if authorization.get(key) is not True]
    if authorization.get("job_id") != job.id or authorization.get("run_id") != (job.run_id or job.id):
        missing.append("exact_job_run_binding")
    if missing:
        raise RuntimeError(
            "Production promotion authorization is incomplete: " + ", ".join(missing)
        )
    production_manifest = _materialize_production_manifest(run_dir, authorization)
    queue.record_production_authorization(
        job.id,
        {
            "authorization_artifact": "production_authorization.json",
            "authorized_media_asset_ids": authorization["authorized_media_asset_ids"],
            "production_manifest_media_count": len(production_manifest["media"]),
        },
    )

    result = SiteAgentOrchestrator().run(
        job.instagram_url,
        production=True,
        preview=False,
        run_id=job.run_id or job.id,
        run_path=run_dir,
    )
    if not result.publish.is_verified_production:
        raise RuntimeError("Production publishing did not return a live-verified HTTPS deployment.")
    queue.record_checkpoints(
        job.id,
        production_preflight_completed="completed_and_valid",
        production_acceptance_completed="completed_and_valid",
        production_deployment_completed="completed_and_valid",
        production_live_qa_completed="completed_and_valid",
    )
    notifier = TelegramNotifier()
    queue.mark_notification_sending(job.id)
    try:
        receipt = notifier.send_done(job.chat_id, result.publish)
    except Exception as exc:
        queue.mark_notification_unknown(job.id, str(exc))
        raise InterruptedDeliveryUncertain(job.id) from exc
    queue.record_notification_sent(job.id, receipt)
    queue.complete(
        job.id,
        site_url=result.publish.production_url,
        repo_url=result.publish.repo_url,
    )
    print("Production готово:")
    print(result.publish.production_url)


def _materialize_production_manifest(run_dir: Path, authorization: dict) -> dict:
    authorised_ids = {
        str(value) for value in authorization.get("authorized_media_asset_ids", []) if str(value).strip()
    }
    if not authorised_ids:
        raise RuntimeError("Production authorization requires authorized_media_asset_ids.")
    preview_path = run_dir / "generation_reports" / "02_authorised_media_manifest.json"
    try:
        preview_manifest = json.loads(preview_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RuntimeError("Production promotion requires the accepted preview media manifest.") from exc
    source_media = [item for item in preview_manifest.get("media", []) if isinstance(item, dict)]
    available_ids = {str(item.get("asset_id", "")) for item in source_media}
    if authorised_ids != available_ids:
        missing = sorted(available_ids - authorised_ids)
        unknown = sorted(authorised_ids - available_ids)
        raise RuntimeError(
            "Production media authorization must exactly match the accepted preview manifest; "
            f"missing={missing}, unknown={unknown}."
        )
    production_media = []
    for source in source_media:
        item = dict(source)
        item.update({
            "source_kind": "business",
            "user_authorized": True,
            "allowed_for_public_site": True,
            "allowed_for_customer_production": True,
        })
        production_media.append(item)
    manifest = {
        **preview_manifest,
        "purpose": "customer_production",
        "media": production_media,
        "production_authorization_job_id": authorization.get("job_id"),
        "production_authorization_run_id": authorization.get("run_id"),
    }
    target = run_dir / "production_input" / "media_manifest.json"
    write_json(target, manifest)
    return manifest


def reconcile_preview_metadata(job_id: str, *, deployment_id: str = "") -> None:
    """Hydrate a verified historical preview record without uploading anything."""
    queue = _pending_job_queue()
    job = queue.get(job_id)
    run_dir = Path(job.run_dir or settings.runs_dir / (job.run_id or job.id))
    deployment_path = run_dir / "preview_deployment.json"
    try:
        deployment = PreviewDeploymentResult.model_validate_json(
            deployment_path.read_text(encoding="utf-8")
        )
    except (OSError, ValueError) as exc:
        raise RuntimeError("A verified preview_deployment.json is required for reconciliation.") from exc
    resolved_id = deployment.deployment_id or deployment_id
    if not resolved_id:
        raise RuntimeError("Preview reconciliation requires the verified Cloudflare deployment id.")
    PreviewLiveVerifier().verify(
        deployment.preview_url,
        site_dir=run_dir / "preview_publish",
        expected_marker=stable_business_id(job.instagram_url),
    )
    queue.reconcile_preview_metadata(
        job.id,
        run_dir=str(run_dir),
        preview_url=deployment.preview_url,
        deployment_id=resolved_id,
        project_name=deployment.project_name,
        branch=deployment.branch,
        checkpoints={
            "research_completed": "completed_and_valid",
            "generation_completed": "completed_and_valid",
            "technical_gate_completed": "completed_and_valid",
            "critics_completed": "completed_and_valid",
            "acceptance_completed": "completed_and_valid",
            "preview_deployment_completed": "completed_and_valid",
            "preview_live_verified": "completed_and_valid",
            "ONE_LINK_SITE_PREVIEW_READY_FOR_USER_REVIEW": "completed_and_valid",
        },
    )
    print("Preview metadata reconciled:")
    print(deployment.preview_url)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a commercial site from an Instagram URL or run the next Telegram job."
    )
    parser.add_argument("command_or_url")
    parser.add_argument("--job-id")
    parser.add_argument("--authorize-manual-resend", action="store_true")
    parser.add_argument("--authorize-preview-resend", action="store_true")
    parser.add_argument("--authorize-production", action="store_true")
    parser.add_argument("--deployment-id", default="")
    args = parser.parse_args()

    if args.command_or_url.lower() in GO_ALIASES:
        run_pending_job()
    elif args.command_or_url == "preview-resume":
        if not args.job_id:
            parser.error("preview-resume requires --job-id")
        run_preview_job(args.job_id)
    elif args.command_or_url == "manual-resend":
        if not args.authorize_manual_resend or not args.job_id:
            parser.error("manual-resend requires --job-id and --authorize-manual-resend")
        run_authorized_manual_resend(args.job_id)
    elif args.command_or_url == "preview-notify":
        if not args.job_id:
            parser.error("preview-notify requires --job-id")
        run_preview_notification(args.job_id)
    elif args.command_or_url == "preview-resend":
        if not args.job_id or not args.authorize_preview_resend:
            parser.error(
                "preview-resend requires --job-id and --authorize-preview-resend"
            )
        run_preview_notification(args.job_id, authorized_resend=True)
    elif args.command_or_url == "production-promote":
        if not args.job_id:
            parser.error("production-promote requires --job-id")
        run_production_promotion(args.job_id, authorized=args.authorize_production)
    elif args.command_or_url == "reconcile-preview":
        if not args.job_id:
            parser.error("reconcile-preview requires --job-id")
        reconcile_preview_metadata(args.job_id, deployment_id=args.deployment_id)
    else:
        run_instagram_url(args.command_or_url)


if __name__ == "__main__":
    main()
