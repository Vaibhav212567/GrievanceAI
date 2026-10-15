# GrievanceAI — AI-assisted Workflow & Grievance Management

A responsive web app prototype for submitting, classifying, prioritizing and tracking grievances.

## Features
- Citizen grievance submission form
- Keyword-based triage suggestions for category and priority (replaceable with a real AI model)
- Grievance register with search and status filters
- Workflow status management
- Dashboard metrics and category charts
- Flask REST API + SQLite database for local use; Render blueprint included for deployment

## Run locally
1. Install Python 3.10+.
2. In this folder, run:
   ```bash
   python -m venv .venv
   # Windows:
   .venv\Scripts\activate
   # macOS/Linux:
   source .venv/bin/activate
   pip install -r requirements.txt
   python app.py
   ```
3. Open http://127.0.0.1:5000

## Deploy online with full account control
1. Create a new GitHub repository under your own account.
2. Upload all files in this folder (keep `static/index.html` in the `static` folder).
3. On Render, choose **New + → Blueprint**, connect your repository, and approve the `render.yaml` configuration.
4. Render will create the web service and PostgreSQL database. Open the generated `onrender.com` URL.
5. Manage source code from GitHub and deployment/environment settings from your Render account.

## Important production notes
- This starter does not yet implement login/role-based authorization. Do not expose the admin status-update endpoints publicly for real government/citizen data until authentication and authorization are added.
- Triage is a transparent keyword heuristic, not a connected LLM. Add a server-side AI provider integration only after setting up a secret API key in the host's environment variables; never put API keys in browser JavaScript.
- Add rate limiting, validation, audit logs, privacy policy, backups and secure authentication before real-world deployment.
- The database is configured for SQLite locally and PostgreSQL via `DATABASE_URL` in deployment.


## Accounts and privacy

- Users can create an account with a name, email and password, then log in and log out.
- Passwords are hashed using Werkzeug before they are stored.
- Each account sees and manages only the grievances submitted under that account.
- On Render, set a long random `SECRET_KEY` environment variable in the web service settings. Do not share it publicly.
- Existing grievances in a database from an older version have no account owner; they are retained in the database but are not shown to newly registered users.
- This is a starter authentication implementation. Before a sensitive public-sector production launch, add email verification, password reset, rate limiting, CSRF protection for all state-changing routes, and a reviewed staff/admin role system.
