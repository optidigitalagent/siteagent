from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from site_agent.config import settings
from site_agent.models import PublishResult


class PublisherError(RuntimeError):
    pass


class Publisher:
    def publish(self, *, run_dir: Path, site_dir: Path) -> PublishResult:
        if not settings.publish_remote_url:
            return PublishResult(
                site_url=(site_dir / "index.html").resolve().as_uri(),
                repo_url=settings.public_repo_url or run_dir.resolve().as_uri(),
                deployed=False,
            )

        repo_dir = run_dir / "publish_repo"
        if repo_dir.exists():
            shutil.rmtree(repo_dir)
        repo_dir.mkdir(parents=True)

        self._copy_site(site_dir, repo_dir)
        self._copy_reports(run_dir, repo_dir)
        self._git(repo_dir, "init")
        self._git(repo_dir, "checkout", "-B", settings.publish_branch)
        self._git(repo_dir, "remote", "add", "origin", settings.publish_remote_url)
        self._git(repo_dir, "add", ".")
        self._git(repo_dir, "commit", "-m", "Publish generated site")
        self._git(repo_dir, "push", "-f", "origin", settings.publish_branch)

        site_url = self._pages_url()
        return PublishResult(
            site_url=site_url,
            repo_url=settings.public_repo_url or settings.publish_remote_url,
            deployed=True,
        )

    def _copy_site(self, site_dir: Path, repo_dir: Path) -> None:
        for item in site_dir.iterdir():
            target = repo_dir / item.name
            if item.is_dir():
                shutil.copytree(item, target)
            else:
                shutil.copy2(item, target)

    def _copy_reports(self, run_dir: Path, repo_dir: Path) -> None:
        for name in ["generation_reports", "critique_reports"]:
            source = run_dir / name
            if source.exists():
                shutil.copytree(source, repo_dir / name)

    def _git(self, cwd: Path, *args: str) -> None:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            raise PublisherError(f"git {' '.join(args)} failed: {result.stderr or result.stdout}")

    def _pages_url(self) -> str:
        if settings.public_repo_url and "github.com" in settings.public_repo_url:
            parts = settings.public_repo_url.rstrip("/").split("/")
            if len(parts) >= 2:
                owner = parts[-2]
                repo = parts[-1].removesuffix(".git")
                return f"https://{owner}.github.io/{repo}/"
        return settings.public_repo_url or settings.publish_remote_url

