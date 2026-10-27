# Ember Notes

A self-hostable, Django-powered notes app with a focused dark interface, autosave, tags, pinning, archive, trash, search, sorting, and per-user note isolation.

> **Project status:** Phase 1 stabilization and documentation. Review the deployment and persistence checklist before hosting real user data.

## Features

- Account signup, login, and logout
- Create and edit notes with debounced autosave and manual save
- Save-state feedback, retry on failure, and flush pending edits before destructive actions
- Tags, pinned notes, archive, recoverable trash, and permanent deletion
- Search across note titles, bodies, and tags; sorting and paginated grid/list views
- Per-user ownership checks and CSRF-protected state-changing requests
- Django admin, static assets served through WhiteNoise, and a management command to purge old trash

## Tech stack

- Python 3.10+ (use a supported Python version compatible with your deployment)
- Django 5.2
- SQLite by default
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
| `DJANGO_DB_PATH` | Optional path to the SQLite database file. |
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
- [ ] Add rate limiting for authentication endpoints and a password reset/account recovery flow before public launch.
- [ ] Confirm logs do not contain secrets, passwords, session tokens, or private note content.
- [ ] Schedule `python manage.py purge_trash --days 30` only after documenting its permanent-deletion policy and ensuring backups exist.
- [ ] Verify registration, login/logout, CRUD, autosave, trash/restore, search, mobile layout, and error states in a real browser.

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
