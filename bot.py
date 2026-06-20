from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from commands import (
    assignment_command,
    assignments_command,
    approve_command,
    calendar_command,
    diary_command,
    dump_command,
    dumpdelete_command,
    dumpedit_command,
    dumps_command,
    dumpview_command,
    done_command,
    event_command,
    events_command,
    help_command,
    journal_command,
    mood_command,
    owner_command,
    pending_users_command,
    start_command,
    today_command,
    todo_command,
    todos_command,
)
from config import get_settings
from db import Database


logging.basicConfig(
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Unhandled bot error", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        await update.effective_message.reply_text(
            "Something went wrong while saving. Please try again."
        )


def build_application():
    settings = get_settings()
    app = ApplicationBuilder().token(settings.telegram_bot_token).build()
    app.bot_data["settings"] = settings
    app.bot_data["db"] = Database(settings)

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("owner", owner_command))
    app.add_handler(CommandHandler("pending_users", pending_users_command))
    app.add_handler(CommandHandler("approve", approve_command))
    app.add_handler(CommandHandler("today", today_command))
    app.add_handler(CommandHandler("todo", todo_command))
    app.add_handler(CommandHandler("todos", todos_command))
    app.add_handler(CommandHandler("dump", dump_command))
    app.add_handler(CommandHandler("dumps", dumps_command))
    app.add_handler(CommandHandler("dumpview", dumpview_command))
    app.add_handler(CommandHandler("dumpedit", dumpedit_command))
    app.add_handler(CommandHandler("dumpdelete", dumpdelete_command))
    app.add_handler(CommandHandler("done", done_command))
    app.add_handler(CommandHandler("journal", journal_command))
    app.add_handler(CommandHandler("diary", diary_command))
    app.add_handler(CommandHandler("assignment", assignment_command))
    app.add_handler(CommandHandler("assignments", assignments_command))
    app.add_handler(CommandHandler("calendar", calendar_command))
    app.add_handler(CommandHandler("event", event_command))
    app.add_handler(CommandHandler("events", events_command))
    app.add_handler(CommandHandler("mood", mood_command))
    app.add_error_handler(error_handler)
    return app


def main() -> None:
    app = build_application()
    logger.info("Starting neebot")
    app.run_polling()


if __name__ == "__main__":
    main()
