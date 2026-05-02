# Ember: a Django notes app

Dark, orange-and-gold note taking built on Django 5.2 and SQLite. No JavaScript build step, no external services (only Google Fonts, with system-font fallbacks).

## Features
- Accounts: sign up, sign in, sign out. Every note is private to its owner (enforced server-side).
- Notes with title, body and tags; autosave with visible status (saved, saving, unsaved, couldn't save with retry), plus a Save button and Ctrl/Cmd+S.
- Search (title, body, tags; every word must match), tag filter, sort (last edited, created, title), grid or list layout, pagination.
- Pin, archive, trash with restore, delete forever, empty trash. Destructive actions ask for confirmation.
- Responsive layout with mobile drawer; keyboard focus styles, skip link, reduced-motion support.
- Shortcuts: `/` search, `n` new note, `Ctrl/Cmd+S` save, `Esc` close menu.

## Run locally
```bash
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env          # then set DJANGO_SECRET_KEY (generator command is in the file)
python manage.py migrate
python manage.py createsuperuser   # optional, for /admin/
python manage.py runserver
```
Open http://127.0.0.1:8000. Run tests: `python manage.py test`.

## Deploy
Set these environment variables (see `.env.example`):

| Variable | Notes |
|---|---|
| `DJANGO_DEBUG` | `False` in production (default) |
| `DJANGO_SECRET_KEY` | Required. Long random string |
| `DJANGO_ALLOWED_HOSTS` | e.g. `notes.example.com` |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | e.g. `https://notes.example.com` |
| `DJANGO_BEHIND_PROXY` | `True` if a proxy terminates HTTPS and sets `X-Forwarded-Proto` |
| `DJANGO_DB_PATH` | Persistent SQLite path (mount a volume) |
| `DJANGO_ADMIN_URL` | Optional custom admin path |

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
gunicorn ember.wsgi --bind 0.0.0.0:8000
```
Static files are served by WhiteNoise. With `DJANGO_DEBUG=False`, cookies are Secure and HTTPS redirect and HSTS are on. Back up the SQLite file regularly, or switch `DATABASES` to PostgreSQL for multi-instance hosting.

Optional cron job to permanently remove notes trashed more than 30 days ago:
`python manage.py purge_trash --days 30`

## Layout
`ember/` settings and URLs, `accounts/` sign-up, `notes/` models, forms, views, tests, `templates/`, `static/css/ember.css`, `static/js/app.js`.

## Known limitations
- Plain-text notes (no Markdown or rich text).
- No password reset by email (needs an email backend) and no login rate limiting. Add `django-axes` or a proxy rule before exposing publicly.
- A newly created note exists immediately; an empty one can be trashed like any other.
- Last write wins if the same note is edited in two tabs at once.
- Search uses `icontains`: fine for personal-scale data, not full-text.
