from __future__ import annotations

import os
from dataclasses import dataclass
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    supabase_database_url: str
    owner_telegram_user_id: int
    app_timezone: str = "Asia/Singapore"
    miniapp_url: str = ""
    webapp_port: int = 8080

    @property
    def tzinfo(self) -> ZoneInfo:
        try:
            return ZoneInfo(self.app_timezone)
        except ZoneInfoNotFoundError as exc:
            raise RuntimeError(
                f"Invalid APP_TIMEZONE value: {self.app_timezone}"
            ) from exc


def get_settings() -> Settings:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    db_url = os.getenv("SUPABASE_DATABASE_URL", "").strip()
    owner_telegram_user_id = os.getenv("OWNER_TELEGRAM_USER_ID", "").strip()
    timezone = os.getenv("APP_TIMEZONE", "Asia/Singapore").strip() or "Asia/Singapore"
    miniapp_url = os.getenv("MINIAPP_URL", "").strip()
    webapp_port = int(os.getenv("WEBAPP_PORT", "8080"))

    missing = []
    if not token:
        missing.append("TELEGRAM_BOT_TOKEN")
    if not db_url:
        missing.append("SUPABASE_DATABASE_URL")
    if not owner_telegram_user_id:
        missing.append("OWNER_TELEGRAM_USER_ID")
    if missing:
        raise RuntimeError(
            "Missing required environment variables: " + ", ".join(missing)
        )

    try:
        owner_id = int(owner_telegram_user_id)
    except ValueError as exc:
        raise RuntimeError("OWNER_TELEGRAM_USER_ID must be a Telegram numeric user id") from exc

    return Settings(
        telegram_bot_token=token,
        supabase_database_url=db_url,
        owner_telegram_user_id=owner_id,
        app_timezone=timezone,
        miniapp_url=miniapp_url,
        webapp_port=webapp_port,
    )
