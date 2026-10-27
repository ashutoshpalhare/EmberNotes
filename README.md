# Ember Notes

A self-hostable, Django-powered notes app with a focused dark interface, autosave, tags, pinning, archive, trash, search, sorting, and per-user note isolation.

> **Project status:** Phase 2 production-readiness work. Configure a persistent database, shared cache, SMTP and verified backups before hosting real user data.

## Features

- Account signup, login, logout, password-reset emails, and reset-token flow
- Brute-force protection for login attempts and IP-based signup throttling
- Privacy-conscious authentication event logs that omit credentials and note content
- Configurable PostgreSQL connections and optional Redis-backed shared cache
- SQLite backup/restore commands with integrity checks and a pre-restore safety copy
- Create and edit notes with debounced autosave and manual save
- Save-state feedback, retry on failure, and flush pending edits before destructive actions
- Tags, pinned notes, archive, recoverable trash, and permanent deletion
- Search across note titles, bodies, and tags; sorting and paginated grid/list views
- Per-user ownership checks and CSRF-protected state-changing requests
- Django admin, static assets served through WhiteNoise, and a management command to purge old trash

## Tech stack

- Python 3.10+ (use a supported Python version compatible with your deployment)
- Django 5.2
- SQLite for local development; PostgreSQL supported through `DATABASE_URL`
- WhiteNoise for static files
- Gunicorn as the WSGI server

## Local setup

### 1. Create a virtual environment

**macOS / Linux**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Windows PowerShell**
```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2. Install dependencies and configure the environment

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Copy `.env.example` to `.env`. For local development, set `DJANGO_DEBUG=True` and keep `DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1`. Generate a local secret key with:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Put the generated value in `DJANGO_SECRET_KEY` in your local `.env`. Never commit `.env` or use a development key in production.

### 3. Apply migrations and start the server

```bash
python manage.py check
python manage.py migrate
python manage.py runserver
```

Open http://127.0.0.1:8000/ and create an account.

## Tests and checks

GitHub Actions runs the test suite, Django system check, and migration consistency check on pull requests to `main` and pushes to `main`. See `.github/workflows/django-ci.yml`.

Run the project's Django tests:

```bash
python manage.py test
python manage.py check
python manage.py makemigrations --check --dry-run
```

Run the production deployment check after setting production environment variables (including a real secret key and allowed hosts):

```bash
python manage.py check --deploy
```

The deploy check is expected to report configuration warnings until the hosting environment and settings are fully configured. Do not suppress warnings without understanding them.

## Configuration reference

| Variable | Purpose |
| --- | --- |
| `DJANGO_DEBUG` | Enables development mode. Must be false in production. |
| `DJANGO_SECRET_KEY` | Required outside debug/test mode; keep secret and rotate if exposed. |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated hostnames accepted by Django. |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Full trusted origins including scheme, e.g. `https://notes.example.com`, only when needed. |
| `DJANGO_TIME_ZONE` | Application timezone; the example uses `Asia/Kolkata`. |
| `DJANGO_SECURE_SSL_REDIRECT` | Redirects HTTP to HTTPS in production by default. |
| `DJANGO_BEHIND_PROXY` | Enables forwarded-protocol handling only when the trusted proxy is configured correctly. |
| `DJANGO_HSTS_SECONDS` | HSTS duration in production; only enable long durations after HTTPS is confirmed. |
| `DJANGO_ADMIN_URL` | Admin URL path. This is not a substitute for authentication or rate limiting. |
| `DJANGO_DB_PATH` | Optional path to the SQLite database file when `DATABASE_URL` is unset. |
| `DATABASE_URL` | Optional PostgreSQL connection URL; TLS is required by the app in production. |
| `DB_CONN_MAX_AGE` | Persistent database connection lifetime in seconds (default 60). |
| `CACHE_URL` | Optional Redis URL for a shared cache; configure this for reliable IP rate limits across multiple workers. |
| `AXES_FAILURE_LIMIT` | Failed login attempts before lockout (default 5). |
| `AXES_COOLOFF_HOURS` | Login lockout duration in hours (default 1). |
| `DEFAULT_FROM_EMAIL` | Sender shown on password-reset emails. |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | Production SMTP connection settings; keep credentials in the hosting secret manager. |
| `EMAIL_USE_TLS`, `EMAIL_USE_SSL`, `EMAIL_TIMEOUT` | SMTP transport and timeout settings. |
| `DJANGO_LOG_LEVEL` | Python root logger level. Do not log note contents or credentials. |

The application currently configures SQLite in `ember/settings.py`. `DJANGO_DB_PATH` changes the file location; it does **not** make storage persistent on its own. On hosting platforms with ephemeral filesystems, SQLite data can disappear during redeploys/restarts. Before production use, confirm persistent storage or migrate to a managed database such as PostgreSQL, and test a restore from backup.

## Production readiness checklist

Do not treat a successful local run as proof of production readiness.

- [ ] Set `DJANGO_DEBUG=False` and a unique, strong `DJANGO_SECRET_KEY` in the host's secret manager.
- [ ] Set exact `DJANGO_ALLOWED_HOSTS` and, if required, `DJANGO_CSRF_TRUSTED_ORIGINS`.
- [ ] Confirm HTTPS termination and proxy configuration with the hosting provider before enabling redirects/HSTS.
- [ ] Confirm the database location survives restarts and deployments; use PostgreSQL for a multi-instance deployment.
- [ ] Configure scheduled, access-controlled backups and perform a restore drill.
- [ ] Apply migrations during deployment and collect static files with `python manage.py collectstatic --noinput`.
- [ ] Run `python manage.py check --deploy` against the actual production environment and resolve applicable warnings.
- [ ] Confirm login lockout and signup rate limits with your actual shared-cache/worker topology.
- [ ] Configure production SMTP and test password recovery end to end.
- [ ] Confirm logs do not contain secrets, passwords, session tokens, or private note content.
- [ ] Schedule `python manage.py purge_trash --days 30` only after documenting its permanent-deletion policy and ensuring backups exist.
- [ ] Verify registration, login/logout, CRUD, autosave, trash/restore, search, mobile layout, and error states in a real browser.

## Database backups and restore

### SQLite (local/single-instance only)

Create an integrity-checked snapshot:

```bash
python manage.py backup_db
python manage.py backup_db --output /secure/backups/ember.sqlite3
```

The default destination is `backups/`, which is excluded from Git. Backups contain private note content and account data: restrict access, encrypt them at rest, and copy them to storage independent of the app host. Never commit or publicly serve backups.

To restore, **stop every app worker first** and verify the chosen backup. The command requires an explicit destructive confirmation and preserves the previous live database as a safety copy when one exists:

```bash
python manage.py restore_db /secure/backups/ember.sqlite3 --confirm
```

The restore command supports SQLite only. Run a restore drill on a non-production copy before relying on it; a successful backup is not proof that recovery works.

### PostgreSQL (recommended for production)

Use managed database snapshots/PITR when your provider supports them. As a portable manual alternative, use the provider's recommended `pg_dump` and `pg_restore` workflow from a secured host:

```bash
pg_dump --format=custom --file=ember-backup.dump "$DATABASE_URL"
# Destructive restore: stop app workers and confirm the target database first.
pg_restore --clean --if-exists --no-owner --dbname="$DATABASE_URL" ember-backup.dump
```

Keep dumps encrypted and access-controlled. A restore can replace database objects/data; never test it against the only production database. Schedule backups, monitor their success, and periodically restore into an isolated database.

## Authentication protection and email

- Login failures are tracked by Django Axes; the default lockout is five failures for the username/IP combination for one hour.
- Signup POSTs are limited to five per IP per hour. Configure `CACHE_URL` to Redis for shared rate-limit state across multiple workers; the local-memory fallback is not shared between processes.
- Password reset uses Django's token-based built-in flow. Unknown email addresses receive the same confirmation page to reduce account enumeration. Production must configure working SMTP credentials; development prints reset emails to the console.
- Authentication logs record event types only; they intentionally omit usernames, passwords, session tokens, and note contents. Protect and rotate host logs as part of operations.

## Data and privacy notes

Notes are private to the authenticated owner at the application-query level. This is not end-to-end encryption: operators with database access may be able to read stored note content. Do not promise encrypted notes unless encryption and key management are implemented and independently reviewed.

The `purge_trash` management command permanently deletes notes that have remained in the trash longer than the selected retention window (30 days by default). Backups and database retention are separate concerns.

## Repository layout

```text
accounts/      Signup and account views/forms
ember/         Django project settings and URL configuration
notes/         Note/tag models, forms, views, tests, purge command
templates/     Django templates
static/        CSS and JavaScript
manage.py      Django management entry point
requirements.txt
.env.example   Documented environment-variable template
```

## Contributing

1. Create a branch for your change.
2. Add or update tests for behavior changes.
3. Run `python manage.py test`, `python manage.py check`, and `python manage.py makemigrations --check --dry-run`.
4. Open a pull request with a summary and test results.

## License

No license file was present when this README was written. Add a `LICENSE` file before inviting reuse or redistribution; without an explicit license, normal copyright restrictions apply.
