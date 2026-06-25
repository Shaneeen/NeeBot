from __future__ import annotations


def main() -> None:
    raise SystemExit(
        "Polling mode has been removed. Start the webhook server with `python webapp.py` "
        "and configure WEBHOOK_BASE_URL for Telegram delivery."
    )


if __name__ == "__main__":
    main()
