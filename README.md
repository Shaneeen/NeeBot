# neebot

`neebot` is a Telegram-based Life OS bot backed by Supabase Postgres. The bot is designed as the first input layer only: all user data lives in Postgres so a future web dashboard can read the same schema.

## Features

- Telegram commands for todos, diary entries, assignments, events, mood logs, brain dumps, and habits
- Supabase/Postgres schema designed for both bot usage and future web UI usage
- Render-friendly process model with environment-variable configuration
- Modular command files so behavior can be extended without turning `bot.py` into a monolith

## Project Structure

```text
life-os-bot/
├── bot.py
├── db.py
├── config.py
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
├── commands/
│   ├── __init__.py
│   ├── common.py
│   ├── start.py
│   ├── today.py
│   ├── todo.py
│   ├── diary.py
│   ├── assignment.py
│   ├── calendar.py
│   ├── mood.py
│   ├── habit.py
│   └── plan.py
└── sql/
    └── schema.sql
```

## Environment Variables

Create `.env` from `.env.example`:

```env
TELEGRAM_BOT_TOKEN=
SUPABASE_DATABASE_URL=
OWNER_TELEGRAM_USER_ID=
APP_TIMEZONE=Asia/Singapore
```

Do not commit `.env`.

## Setup

1. Create a Python virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Apply the schema in your Supabase SQL editor or with `psql`:

```bash
psql "$SUPABASE_DATABASE_URL" -f sql/schema.sql
```

4. Start the bot:

```bash
python bot.py
```

## Private Access Control

- Set `OWNER_TELEGRAM_USER_ID` to your personal Telegram numeric user id.
- The owner is auto-approved on first `/start`.
- Everyone else is created as pending and cannot use the bot until approved.
- Owner workflow:
  - User sends `/start`
  - Owner runs `/pending_users`
  - Owner runs `/approve <telegram_user_id>`

## Supported Commands

- `/start`
- `/help`
- `/today`
- `/todo <text>`
- `/todos`
- `/done <todo number or UUID>`
- `/dump Header | text`
- `/dumps`
- `/dumpview <number>`
- `/dumpedit <number> | new text`
- `/dumpdelete <number>`
- `/journal <text>`
- `/diary`
- `/assignment <text>`
- `/assignments`
- `/assignmentdelete <number>`
- `/event YYYY-MM-DD HH:MM Title`
- `/event YYYY-MM-DD to YYYY-MM-DD Title`
- `/event YYYY-MM-DD HH:MM to YYYY-MM-DD HH:MM Title`
- `/events`
- `/eventdelete <number>`
- `/mood <1-10> [energy <1-10>] [stress <1-10>]`

## Render Deployment

This repo now supports a single Render web service:

- `neebot-web` runs the mini app and receives Telegram webhook updates

If you use the included [render.yaml](/Users/Shaneen/NeeBot/render.yaml), Render can create the service from the repo.

Build command:

```bash
pip install -r requirements.txt
```

Start command:

```bash
python webapp.py
```

Set these environment variables in Render:

- `TELEGRAM_BOT_TOKEN`
- `SUPABASE_DATABASE_URL`
- `OWNER_TELEGRAM_USER_ID`
- `APP_TIMEZONE`
- `WEBHOOK_BASE_URL` set to your public Render base URL, for example `https://your-service.onrender.com`
- `WEBHOOK_SECRET` optional but recommended
- `WEBAPP_PORT` for the web service, default `8080`

## Notes

- The bot now uses Telegram webhooks through `webapp.py`; `bot.py` no longer runs polling.
- Reminders are modeled in the schema but not yet processed by a background sender.
- Todo completion accepts either the todo UUID or the list number from `/todos`.
