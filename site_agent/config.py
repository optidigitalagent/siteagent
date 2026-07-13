from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4.1", alias="OPENAI_MODEL")
    telegram_bot_token: str = Field(default="", alias="TELEGRAM_BOT_TOKEN")

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
