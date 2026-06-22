from __future__ import annotations

import asyncio
import logging

from aiohttp import web
from telegram import BotCommand, BotCommandScopeAllPrivateChats, BotCommandScopeChat, Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from webapp import create_webapp

from commands import (
    app_command,
    assignment_command,
    assignmentdelete_command,
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
    eventdelete_command,
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


async def post_init(application) -> None:
    settings = application.bot_data["settings"]

    shared_commands = [
        BotCommand("today", "See today's overview"),
        BotCommand("help", "View all commands"),
        BotCommand("app", "Open NeenyKeeps mini app"),
        BotCommand("event", "Add an event"),
        BotCommand("todo", "Add a task"),
        BotCommand("dump", "Create a brain dump"),
        BotCommand("assignment", "Add an assignment or deadline"),
    ]
    await application.bot.set_my_commands(shared_commands, scope=BotCommandScopeAllPrivateChats())
    await application.bot.set_my_commands(shared_commands, scope=BotCommandScopeChat(chat_id=settings.owner_telegram_user_id))


def build_application():
    settings = get_settings()
    app = ApplicationBuilder().token(settings.telegram_bot_token).post_init(post_init).build()
    app.bot_data["settings"] = settings
    app.bot_data["db"] = Database(settings)

    app.add_handler(CommandHandler("app", app_command))
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
    app.add_handler(CommandHandler("assignmentdelete", assignmentdelete_command))
    app.add_handler(CommandHandler("assignments", assignments_command))
    app.add_handler(CommandHandler("calendar", calendar_command))
    app.add_handler(CommandHandler("event", event_command))
    app.add_handler(CommandHandler("eventdelete", eventdelete_command))
    app.add_handler(CommandHandler("events", events_command))
    app.add_handler(CommandHandler("mood", mood_command))
    app.add_error_handler(error_handler)
    return app


def main() -> None:
    settings = get_settings()
    app = build_application()
    db = Database(settings)

    if settings.miniapp_url:
        async def run_all():
            webapp = create_webapp(settings, db)
            runner = web.AppRunner(webapp)
            await runner.setup()
            site = web.TCPSite(runner, "0.0.0.0", settings.webapp_port)
            await site.start()
            logger.info("Mini app server running on port %s", settings.webapp_port)

            async with app:
                await app.initialize()
                await app.start()
                await app.updater.start_polling()
                logger.info("Starting neebot with mini app server")

                stop_event = asyncio.Event()
                try:
                    await stop_event.wait()
                except (KeyboardInterrupt, SystemExit):
                    pass
                finally:
                    await app.updater.stop()
                    await app.stop()
                    await app.shutdown()
                    await runner.cleanup()

        asyncio.run(run_all())
    else:
        logger.info("Starting neebot (no mini app — set MINIAPP_URL to enable)")
        app.run_polling()


if __name__ == "__main__":
    main()
