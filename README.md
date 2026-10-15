# GrievanceAI — public portal + protected admin workspace

This version separates public grievance submission from administrator operations.

## Routes

- `/` — public submission form only.
- `/api/grievances` (`POST`) — public submission endpoint; responds with a reference ID only.
- `/admin/login` — administrator sign-in.
- `/admin` — protected management dashboard.
- `/api/grievances` (`GET`, `PATCH`) and `/api/stats` — protected administrator API endpoints.

Public visitors cannot list grievance records or change statuses. The admin dashboard is rendered through a protected Flask route rather than exposed as a public static HTML file.

## Required Render environment variables

Set these in **Render → your web service → Environment**:

- `SECRET_KEY` — a long, random secret string. Do not commit it to GitHub.
- `ADMIN_USERNAME` — administrator username.
- `ADMIN_PASSWORD` — a strong, unique administrator password.
- `DATABASE_URL` — use the Render database connection string already configured by `render.yaml`.
- `COOKIE_SECURE` — leave as `true` on the HTTPS Render deployment. For local HTTP development only, set to `false`.

There are intentionally no default admin credentials. If `ADMIN_USERNAME` and `ADMIN_PASSWORD` are not configured, login will fail closed.

## Deploy

1. Upload these changes to the GitHub repository (or replace the project files).
2. Add the environment variables above in Render.
3. Trigger a deploy.
4. Test that `/` only shows the public form, `/admin` redirects to login, and `/api/grievances` with `GET` returns `401` when not logged in.
5. Log in at `/admin/login` and verify the dashboard and status updates.

## Important limitations / production checklist

- This is an initial role split, not a full government-grade case-management system.
- Public submission is anonymous. The receipt ID is not yet a public tracking mechanism.
- Add CSRF protection, login rate limiting, audit logs, and a deliberate data-retention/privacy policy before broad public launch.
- Existing database records remain in the same database; this update changes access controls, not the stored records.
- Keep secrets out of source control and never share `.env` files publicly.
