# Crumb

Crumb is a daily microlearning web app. Learners choose subjects, read short lessons, answer a recall question, and track completed lessons.

## Run locally

Requirements: Python 3.10 or newer. Install dependencies with:

```sh
python -m pip install -r requirements.txt
```

```sh
python server.py
```

Open `http://127.0.0.1:8000`. The app creates `crumb.sqlite3` on first launch. Set `CRUMB_DB` to select another database file, or set `CRUMB_PORT` to change the port.

## Features

- Account registration and sign-in with PBKDF2 password hashes and HTTP-only session cookies.
- Twenty subjects returned by `/api/subjects` and persisted in SQLite.
- Curated lesson records loaded from `data/lessons.json` into the `lessons` table, then delivered to the frontend through `/api/lessons`.
- Per-user subject preferences, generated lessons, completed lesson history, and reminder preferences stored in SQLite.
- Search and random lesson selection use database-backed API routes.
- Topic generation uses Google's Gemini API from the server. Put `GEMINI_API_KEY` in the root `.env` file; `GEMINI_MODEL` is optional and defaults to `gemini-3.5-flash-lite`. Random-topic generation chooses a saved subject, samples four generic seed words in random order, asks Gemini for ten subject-specific topics, randomly selects one on the server, then asks Gemini to write the lesson. Generated lessons target five substantial sections and four review questions, with at least 400 words of section content. Existing process environment variables override values in `.env`.

```dotenv
GEMINI_API_KEY=your-key
GEMINI_MODEL=gemini-3.5-flash-lite
```

The API key stays on the server. If `GEMINI_API_KEY` is missing, lesson generation returns a setup error; it does not substitute a sample response.

## Frontend structure

`frontend/index.html` is a small document shell. Its JavaScript is divided into API and state modules, shared UI helpers, and page modules under `frontend/js/pages/`. The browser does not contain a sample account, lesson fixtures, or local-storage persistence.

## API routes

- `GET /api/subjects`
- `GET /api/lessons?subject=biology&q=cell`
- `GET /api/lessons/{id}`
- `GET /api/lessons/random` (signed-in)
- `POST /api/register`, `POST /api/login`, `POST /api/logout`
- `GET /api/me`, `GET /api/preferences`, `PUT /api/preferences`
- `GET /api/progress`, `POST /api/completions`
- `POST /api/lessons/generate` (signed-in, Gemini API key required; send `prompt` for a chosen topic or `{ "randomTopic": true }` for a preference-based random topic)

## Current limits

Reminder preferences are saved, but no reminder is delivered yet. Account recovery, email verification, HTTPS deployment, database migrations beyond the current compatibility step, and production hosting remain to be implemented. Generated lessons should be reviewed before relying on them as authoritative instruction.
