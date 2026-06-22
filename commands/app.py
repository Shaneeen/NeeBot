from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.ext import ContextTypes


async def app_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings = context.bot_data["settings"]
    url = settings.miniapp_url
    if not url:
        await update.message.reply_text(
            "Mini app URL not configured. Set the MINIAPP_URL environment variable."
        )
        return

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Open NeenyKeeps", web_app=WebAppInfo(url=url))]
    ])
    await update.message.reply_text(
        "Tap below to open your dashboard:",
        reply_markup=keyboard,
    )
