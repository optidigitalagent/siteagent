from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    llm_provider: str = Field(default="codex", alias="LLM_PROVIDER")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4.1", alias="OPENAI_MODEL")
    codex_command: str = Field(default="codex", alias="CODEX_COMMAND")
    codex_model: str = Field(default="", alias="CODEX_MODEL")
    telegram_bot_token: str = Field(default="", alias="TELEGRAM_BOT_TOKEN")

    hosting_provider: str = Field(default="cloudflare_pages", alias="HOSTING_PROVIDER")
    publish_required: bool = Field(default=True, alias="PUBLISH_REQUIRED")
    cloudflare_account_id: str = Field(default="", alias="CLOUDFLARE_ACCOUNT_ID")
    cloudflare_api_token: str = Field(default="", alias="CLOUDFLARE_API_TOKEN")
    cloudflare_pages_production_branch: str = Field(
        default="main",
        alias="CLOUDFLARE_PAGES_PRODUCTION_BRANCH",
    )
    cloudflare_project_prefix: str = Field(default="siteagent", alias="CLOUDFLARE_PROJECT_PREFIX")
    cloudflare_wrangler_package: str = Field(default="wrangler@4", alias="CLOUDFLARE_WRANGLER_PACKAGE")
    cloudflare_command_timeout_seconds: int = Field(
        default=300,
        alias="CLOUDFLARE_COMMAND_TIMEOUT_SECONDS",
    )
    cloudflare_live_retries: int = Field(default=5, alias="CLOUDFLARE_LIVE_RETRIES")
    cloudflare_live_backoff_seconds: float = Field(
        default=2.0,
        alias="CLOUDFLARE_LIVE_BACKOFF_SECONDS",
    )
    cloudflare_live_timeout_seconds: float = Field(
        default=15.0,
        alias="CLOUDFLARE_LIVE_TIMEOUT_SECONDS",
    )

    # Deprecated Git publisher settings. Use only with HOSTING_PROVIDER=git.
    publish_remote_url: str = Field(default="", alias="PUBLISH_REMOTE_URL")
    public_repo_url: str = Field(default="", alias="PUBLIC_REPO_URL")
    publish_branch: str = Field(default="gh-pages", alias="PUBLISH_BRANCH")

    runs_dir: Path = Field(default=Path("runs"), alias="RUNS_DIR")
    telegram_queue_path: Path = Field(
        default=Path(".codex/inbox/telegram_jobs.json"),
        alias="TELEGRAM_QUEUE_PATH",
    )
    telegram_inbox_git_sync: bool = Field(default=False, alias="TELEGRAM_INBOX_GIT_SYNC")
    telegram_inbox_git_remote: str = Field(default="origin", alias="TELEGRAM_INBOX_GIT_REMOTE")
    telegram_inbox_git_remote_url: str = Field(default="", alias="TELEGRAM_INBOX_GIT_REMOTE_URL")
    telegram_inbox_git_branch: str = Field(default="main", alias="TELEGRAM_INBOX_GIT_BRANCH")
    telegram_inbox_git_user_name: str = Field(
        default="website-agent-bot",
        alias="TELEGRAM_INBOX_GIT_USER_NAME",
    )
    telegram_inbox_git_user_email: str = Field(
        default="website-agent-bot@example.local",
        alias="TELEGRAM_INBOX_GIT_USER_EMAIL",
    )
    max_fix_iterations: int = Field(default=5, alias="MAX_FIX_ITERATIONS")
    send_verbose_telegram_logs: bool = Field(default=False, alias="SEND_VERBOSE_TELEGRAM_LOGS")


settings = Settings()
