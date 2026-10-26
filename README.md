# Curio — Daily Microlearning

A responsive, Duolingo-inspired microlearning experience for exploring one small idea at a time across subjects like science, history, mathematics, nature, language, art, technology, psychology, and space.

## What works in this prototype

- Responsive dashboard and navigation for Home, Explore, progress, and subject preferences.
- A curated starter shelf of short lessons with reading cards and multiple-choice recall questions.
- Lesson recommendations based on selected interests, plus a random lesson picker.
- A custom topic prompt that creates a bite-sized lesson card from a subject-specific template.
- Completion history, lesson counts, and a simple streak display.
- Account creation and sign-in with email and password, plus signed session cookies.
- Profile settings for name, subject interests, and an optional reminder preference.
- SQLite persistence for accounts, subject interests, lesson completions, generated lessons, and reminder settings.
- Browser-local fallback using `localStorage` when the app is opened without its server.

## Run it

Python 3.10 or newer is required. The backend uses only Python's standard library and SQLite, so no package install is needed. Start the app from this directory:

```sh
python server.py
```

Then visit `http://127.0.0.1:8000`. The database file `curio.sqlite3` is created in the project folder on first launch. Set `CURIO_PORT` or `CURIO_DB` to use a different port or database path.

## Prototype boundaries

This is an early local MVP, not a production deployment. Accounts and learning data are stored in SQLite on the machine running the server. Passwords are hashed with PBKDF2, and sessions use HTTP-only cookies. There is no email verification, password reset, HTTPS configuration, multi-instance session storage, or deployment hardening yet. Topic prompts use local templates rather than an AI service or live content library. Reminder preferences are stored, but the app does not schedule delivery; reminders while the site is closed need a scheduler and notification service.

## Next implementation steps

1. Add email verification and account recovery.
2. Add database migrations and stronger deployment security.
3. Curate lesson content, including source and review metadata.
4. Connect topic prompts to a controlled lesson-generation service or expand the reviewed library.
5. Add server-scheduled, opt-in reminders and notification management.
6. Add automated tests, accessibility review, and deployment configuration.
