# NeeBot Message Overview

## Entry points

### `/start`

#### approved user

Hey 👋 Welcome back.

/today — your daily summary  
/help — all commands

#### owner

Hey 👋 Welcome back.

/today — your daily summary  
/help — all commands · /owner — admin

#### unapproved user

This bot is private. Your access request has been sent.

Your ID: `123456789`  
You'll be able to use the bot once approved. Then send `/start` again.

Notes:
- Keep the Telegram user ID visible.
- Do not show the `/approve` command to unapproved users.

## Help

### all users

Tasks      `/todo` · `/todos` · `/done`  
Schedule   `/assignment` · `/event` · `/calendar`  
Journal    `/journal` · `/mood` · `/diary`  
View       `/today` · `/assignments` · `/events`

### owner

Admin      `/owner` · `/pending_users` · `/approve`

## Tasks

### `/todo`

#### no input

Add a task:

`/todo title`  
`/todo date title`

Dates: `today` · `tomorrow` · `mon` · `next fri`

`/todo tomorrow Pick up parcel`  
`/todo next wed Submit report`

#### success

✅ Todo added — Wed 25 Jun

Buy milk

### `/todos`

#### no pending todos

No pending todos.

#### has items

Pending todos:

1. Buy milk
2. Submit report — Wed 25 Jun
3. Call dentist

#### this week

This week — Mon 23 Jun to Sun 29 Jun:

1. Wed 25 Jun — Submit report
2. Fri 27 Jun — Buy groceries

### `/done`

#### no input

Mark a task complete:

`/done number`  or  `/done uuid`

`/done 2`

Get numbers from `/todos`.

#### not found

Todo not found. Check your list with `/todos`.

#### success

✅ Done: Buy milk

## Schedule

### `/assignment`

#### no input

Save a deadline:

`/assignment title`  
`/assignment YYYY-MM-DD title`

`/assignment 2025-07-01 Submit thesis`

#### success

📌 Assignment saved

Submit thesis — due 1 Jul 2025

### `/assignments`

#### no active assignments

No active assignments.

#### has items

Active assignments:

1. Submit thesis — due 1 Jul 2025 09:00
2. Fintech report — due 12 Jul 2025 23:59

### `/event`

#### no input

Save an event:

`/event MM-DD title`  
`/event YYYY-MM-DD HH:MM title`

`/event 07-04 Fireworks`  
`/event 07-04 20:00 Fireworks night`

Year defaults to current. Time defaults to `09:00`.

#### parse error

Couldn't read that. Expected:

`/event MM-DD title`  
`/event 07-04 20:00 Fireworks night`

#### success

📅 Event saved

Fireworks night — Sat 4 Jul, 20:00

### `/events`

#### no upcoming events

No upcoming events.

#### has items

Upcoming events:

1. Sat 4 Jul 2025 08:00 PM — Fireworks night
2. Mon 6 Jul 2025 09:00 AM — Team check-in

### `/calendar`

#### bad format

View a month:

`/calendar`          current month  
`/calendar YYYY-MM`

`/calendar 2025-08`

#### success

Calendar — August 2025

Assignments:

1. 01 Aug 09:00 AM — Submit thesis

Events:

1. 04 Aug 08:00 PM — Fireworks night

## Journal

### `/journal`

#### no input

Write a journal entry:

`/journal text`  
`/journal yesterday text`  
`/journal YYYY-MM-DD text`

`/journal Today was productive but tiring.`  
`/journal yesterday Had a cozy rest day.`

Sending `/journal` again for the same date updates that entry.

#### success

📝 Journal saved — Wed 25 Jun

If moods already exist for that date:

Mood: 😊 😴

### `/diary`

#### no entry

No journal entry for Wed 25 Jun.

Add one with:

`/journal 2025-06-25 your entry`

#### has entry

Journal for Wed 25 Jun:

Mood: 😊 😴

Today was productive but tiring.

### `/mood`

#### no input

Add up to 3 moods:

`/mood happy tired`  
`/mood yesterday 🛋️ 😊 😴`  
`/mood 2025-06-25 calm grateful`

Available moods:

🛋️ cozy/rest  
😊 happy  
🤩 excited  
😢 sad  
😴 tired  
😌 calm  
😵 stressed  
😰 anxious  
🙏 grateful  
💪 productive  
😤 angry

#### parse error

Couldn't read that mood entry.

Use up to 3 moods.

`/mood cozy happy tired`  
`/mood 😴🤩💪`

#### success

💬 Mood saved — Wed 25 Jun

😊 😴

#### success with no journal text yet

💬 Mood saved — Wed 25 Jun

😊 😴

Journal text is still empty. Add it with:

`/journal 2025-06-25 your entry`

## View

### `/today`

#### summary structure

Summary — Wed 25 Jun 2025

Todos:

1. Buy milk

Assignments:

1. Submit thesis — due 1 Jul 2025

Events:

1. 09:00 AM — Team check-in

Journal:

Mood: 😊 😴
Today was productive but tiring.

Habits:

No habit logs today.

#### fully empty day

Summary — Wed 25 Jun 2025

Todos:
No pending todos.

Assignments:
No active assignments.

Events:
No events today.

Journal:
No journal entry today.

Habits:
No habit logs today.

Notes:
- Habits appear in `/today` if habit data exists in the database.
- Habit commands are present in code but not currently registered in `bot.py`.

## Admin

### `/owner`

#### owner

Owner menu

`/pending_users` — review access requests  
`/approve <telegram_user_id>` — approve a user

#### non-owner

This menu is only available to the owner.

### `/pending_users`

#### no pending users

No pending access requests.

#### has pending users

Pending access requests:

123456789 — Jane Doe  
987654321 — Alex Tan

### `/approve`

#### no input

Usage: `/approve <telegram_user_id>`

#### bad id

Telegram user id must be numeric.

#### not found

User not found. They need to send `/start` first.

#### success

Approved Jane Doe (`123456789`).

## Access and fallback messages

### unapproved user using a protected command

Your access request is pending owner approval. Use `/start` after you have been approved.

### non-owner using an owner-only command

Only the bot owner can use this command.

### unexpected internal error

Something went wrong while saving. Please try again.
