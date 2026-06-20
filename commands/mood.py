from __future__ import annotations

from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes

from .common import get_authorized_profile, safe_reply
from .date_utils import format_human_date, parse_optional_date_args

MOOD_MAP = {
    "cozy": "🛋️",
    "rest": "🛋️",
    "restful": "🛋️",
    "happy": "😊",
    "excited": "🤩",
    "exciting": "🤩",
    "sad": "😢",
    "tired": "😴",
    "tiring": "😴",
    "calm": "😌",
    "stressed": "😵",
    "anxious": "😰",
    "grateful": "🙏",
    "productive": "💪",
    "angry": "😤",
    "cozy/rest": "🛋️",
    "🛋️": "🛋️",
    "😊": "😊",
    "🤩": "🤩",
    "😢": "😢",
    "😴": "😴",
    "😌": "😌",
    "😵": "😵",
    "😰": "😰",
    "🙏": "🙏",
    "💪": "💪",
    "😤": "😤",
}

EMOJI_MOODS = sorted(
    [key for key in MOOD_MAP if any(ord(char) > 127 for char in key)],
    key=len,
    reverse=True,
)


def _split_mood_token(token: str) -> list[str]:
    direct = MOOD_MAP.get(token.lower(), MOOD_MAP.get(token))
    if direct:
        return [direct]

    parts: list[str] = []
    remaining = token
    while remaining:
        matched = False
        for emoji in EMOJI_MOODS:
            if remaining.startswith(emoji):
                parts.append(MOOD_MAP[emoji])
                remaining = remaining[len(emoji):]
                matched = True
                break
        if not matched:
            raise ValueError(token)
    return parts


def _parse_moods(args: list[str]) -> list[str]:
    normalized = " ".join(args).replace(",", " ").split()
    moods: list[str] = []
    for token in normalized:
        for mood in _split_mood_token(token):
            if mood not in moods:
                moods.append(mood)
    if not moods or len(moods) > 3:
        raise ValueError("count")
    return moods


async def mood_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await safe_reply(
            update,
            "[ mood_ ]\n"
            "Save up to 3 moods for your journal.\n\n"
            "[ format_ ]\n"
            "↳ /mood mood mood mood\n"
            "↳ /mood yesterday mood mood\n"
            "↳ /mood YYYY-MM-DD mood mood\n\n"
            "[ examples_ ]\n"
            "↳ /mood happy tired\n"
            "↳ /mood yesterday cozy happy tired\n"
            "↳ /mood 2026-06-25 calm grateful\n\n"
            "[ moods_ ]\n"
            "↳ 🛋️ cozy / rest\n"
            "↳ 😊 happy\n"
            "↳ 🤩 excited\n"
            "↳ 😢 sad\n"
            "↳ 😴 tired\n"
            "↳ 😌 calm\n"
            "↳ 😵 stressed\n"
            "↳ 😰 anxious\n"
            "↳ 🙏 grateful\n"
            "↳ 💪 productive\n"
            "↳ 😤 angry",
        )
        return
    current_date = datetime.now(
        context.application.bot_data["db"].settings.tzinfo
    ).date()
    entry_date, mood_text = parse_optional_date_args(context.args, current_date)
    try:
        moods = _parse_moods(mood_text.split())
    except ValueError:
        await safe_reply(
            update,
            "[ mood_ ]\n"
            "Couldn't read that mood entry.\n\n"
            "↳ Use up to 3 moods\n"
            "↳ /mood cozy happy tired\n"
            "↳ /mood 😴🤩💪",
        )
        return

    profile = await get_authorized_profile(update, context)
    if not profile:
        return
    entry = context.application.bot_data["db"].upsert_journal_moods(profile["id"], moods, entry_date)
    await safe_reply(
        update,
        "[ mood_saved_ ]\n"
        f"entry: {format_human_date(entry_date, current_date)}\n"
        f"mood: {' '.join(moods)}\n\n"
        "Added to your journal →",
    )
