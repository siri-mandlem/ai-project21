# Student Study Planner

A Flask + Neon PostgreSQL study planner for subjects, daily goals, scheduled sessions, and progress tracking.

## Local development

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
python -m backend.app
```

Without `DATABASE_URL`, the app uses a local SQLite database. For Neon, set `DATABASE_URL` to the pooled PostgreSQL connection string and set a strong `SECRET_KEY`.

## Render + GitHub + Neon

Push this folder to GitHub, create a Render Web Service from the repository, and use the included `render.yaml`. If configuring Render manually, use:

- Build: `pip install -r backend/requirements.txt`
- Start: `gunicorn --chdir backend app:app`
- Health check: `/health`

Add `DATABASE_URL` from Neon and `SECRET_KEY` in Render environment variables. The application creates the tables from `database/schema.sql` on startup.
