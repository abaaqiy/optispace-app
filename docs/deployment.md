# Deploy Optispace for free

Optispace can run as one **Free Render web service**, with the React frontend,
Django API and Django administration site on the same HTTPS address. It connects
to the existing Aiven PostgreSQL database, so accounts, rooms and timetables are
shared by everyone using the deployed app.

The repository includes a Dockerfile and `render.yaml`. Docker builds the React
frontend, collects Django static files, and starts Gunicorn with one worker and
four threads. No Redis service, paid disk, background worker, paid domain or
additional database is needed.
This version has no email sending or password-reset service; email delivery is
disabled in production rather than requiring an SMTP subscription.

## Keep the total cost at zero

- Use Render's **Hobby workspace** and the service's **Free compute plan**.
  These are separate settings. `render.yaml` explicitly sets `plan: free`.
- Do not add a credit card or other payment method. With no payment method,
  Render suspends free services or disables new builds when included quotas
  run out, instead of charging for extra usage.
- Do not enable paid compute, additional services, persistent disks, performance
  build pipelines, paid workspace features or custom domains.
- Confirm that the existing Aiven service's plan is **Free** in the Aiven
  Console. A PostgreSQL connection URL does not disclose its billing plan.
  A free trial on a paid plan is different from the permanent Free plan.
  Aiven Free PostgreSQL has 1 GB storage and a maximum of 20 connections.
- If a provider asks for payment details, stop that setup. Do not authorize a
  card verification hold or switch to a paid plan to finish this deployment.

Free limits are deliberate tradeoffs. Render sleeps after 15 minutes without
requests and typically takes about a minute to wake on the next visit. Its free
services share 750 running hours per calendar month, plus the workspace's
included bandwidth and build minutes. Do not add automatic keepalive requests
to bypass sleeping. This setup is suitable for a beginner project, demonstration
and modest collaboration; it does not promise uninterrupted campus-wide use.

The files in the container disappear on restart or redeployment. The app stores
its data in PostgreSQL. Do not create a Render Free PostgreSQL database instead:
that product expires after 30 days. The Aiven **Free** plan has no time limit,
although Aiven can turn off inactive services and notify you beforehand.

## Before publishing

1. Confirm the Aiven Free plan as described above.
2. Change the existing administrator's short demo password to a strong unique
   password in Django admin. Open **Users**, select the administrator, and use
   the password-change link. This preserves the account and saved records.
   Do not publish or share the previous demo password.
3. Make sure this deployment commit is present on GitHub's `feature/backend`
   branch. Render builds the GitHub copy, not uncommitted local files.
4. Sign up or sign in to [Render](https://dashboard.render.com/) and connect the
   GitHub account that has access to `abaaqiy/optispace-app`.

Do not paste passwords, API tokens or the real PostgreSQL URL into issues,
commits, frontend variables or screenshots. Set database credentials in the
hosting provider's private environment configuration.

## Create the service

1. In Render, choose **New → Blueprint** and select `abaaqiy/optispace-app`.
2. Select the **feature/backend** branch and the root `render.yaml` file.
3. Review the resource list: it must contain only one web service on **Free**.
   There should be no database, disk, worker or other paid resource.
4. When prompted for `DATABASE_URL`, supply the same Aiven PostgreSQL URL used
   privately in `backend/.env`, including `sslmode=require`. Keep this value
   private. Render generates `DJANGO_SECRET_KEY` automatically. Django adds a
   stable prefix to Render's 44-character generated value to meet its secret
   length check without reducing the generated randomness.
5. Create the Blueprint. Wait for the image build and startup to finish.
6. Copy the service's assigned `https://…onrender.com` address from its dashboard.

No shell or paid pre-deploy task is needed: the startup script applies pending
migrations before starting Gunicorn. Startup stops if migrations fail. The build
collects static files using disposable settings and does not contact PostgreSQL.
The database health probe is exempt from Django's HTTP redirect so Render's
internal probe receives the actual database result instead of a healthy-looking
redirect. Browser pages and authenticated API requests require HTTPS.

If a Blueprint cannot be used, create a **Web Service** manually with these
settings:

| Setting | Value |
| --- | --- |
| Repository | `https://github.com/abaaqiy/optispace-app` |
| Branch | `feature/backend` |
| Language/runtime | Docker |
| Root directory | Leave empty |
| Dockerfile path | `./Dockerfile` |
| Compute plan | **Free** |
| Region | Frankfurt |
| Health check path | `/api/health/` |
| Automatic deploys | Off |

Then add the environment variables below. Generate a secret locally with
`python -c "import secrets; print(secrets.token_urlsafe(64))"` and enter it as
`DJANGO_SECRET_KEY` in Render; never commit it.

## Environment variables

| Variable | Value/purpose |
| --- | --- |
| `DATABASE_URL` | Required private Aiven PostgreSQL URI with TLS enabled. |
| `DJANGO_SECRET_KEY` | Required strong random secret; generated by the Blueprint. Keep it stable across redeploys. |
| `DJANGO_DEBUG` | `false`. |
| `DJANGO_TRUST_PROXY` | `true`, because Render terminates HTTPS at its trusted proxy. |
| `RENDER_EXTERNAL_HOSTNAME` | Render supplies the assigned hostname automatically; Django allows that exact host. |
| `PORT` | Render supplies this automatically; the server listens on it. |

Do not create `VITE_DATABASE_URL` or any other frontend database variable. The
frontend calls `/api/` on its own host. Its session cookies and Django admin use
the same origin, with HTTPS redirects and secure cookies enabled in production.

For another trusted HTTPS reverse proxy, provide `DJANGO_ALLOWED_HOSTS` as an
explicit comma-separated hostname list instead of relying on Render's hostname.
Only enable `DJANGO_TRUST_PROXY` behind a proxy that controls the forwarded HTTPS
header. Extra trusted browser origins can be supplied via
`DJANGO_CSRF_TRUSTED_ORIGINS` when needed; they are unnecessary for this single
host deployment.

## Verify the live app

After the service shows **Live**, open these URLs using its assigned HTTPS host:

1. `/api/health/` should return an HTTP 200 JSON response. It checks database
   connectivity without listing credentials or application records.
2. `/` should display the student and lecturer login page for a browser without
   an existing session.
3. `/staff-login` should display the separate administrator login. It remains
   unlinked from the public page.
4. `/admin/` should show a styled Django admin login or dashboard.
5. Log in with an existing test student or approved lecturer. Confirm rooms,
   timetable entries and facilities match the PostgreSQL records.
6. As an administrator, cancel a test timetable entry. A student or lecturer
   viewing that room should see the update within the existing five-second
   polling interval. Restore the entry after verification if appropriate.
7. Try the host on a different phone or computer. It should show the same saved
   data, while each browser has its own login session.

## Updates and troubleshooting

Automatic deploys are disabled to conserve free build minutes. After a tested
commit is pushed to `feature/backend`, choose **Manual Deploy → Deploy latest
commit**. Render keeps the prior deployment available if an image build fails;
review the deployment logs and fix the cause before trying again.

- A slow first page after inactivity is the expected Free service cold start.
- A database connection failure means the Aiven service, TLS configuration,
  credentials or network access must be checked. It does not switch to SQLite.
- A startup migration error stops the new server. Check logs; do not delete or
  recreate PostgreSQL to get past it.
- A CSRF or host error usually means the external hostname or trusted proxy
  configuration is wrong. Use the assigned HTTPS host and explicit allowed
  hosts. Do not turn off CSRF protection or set allowed hosts to `*`.
- If usage is exhausted, wait for the quota reset or reduce requests/builds.
  Keep the service on Free and do not add payment details.

Keep a private PostgreSQL backup before future schema changes. Backups contain
personal data and must stay outside Git and the Docker image.

## Verify a release locally

Use a separate PostgreSQL instance for automated tests. Do not run Django's
test suite with your live database credentials. With a local test URL supplied:

```sh
cd backend
DATABASE_URL=postgresql://user@127.0.0.1:55439/postgres?sslmode=disable \
  /absolute/path/to/optispace-app/venv/bin/python manage.py test --noinput
```

Run `npm run lint`, `npm run build`, and
`node --test src/availability.test.js` from the repository root. A production
`check --deploy` also checks HTTPS settings; HSTS subdomain and preload warnings
are intentional because the app only controls its assigned hostname. The
email-backend check is explicitly silenced while outgoing email is disabled.
Build the full container with `docker build -t optispace-app .` when Docker is
available. Never supply real database credentials as Docker build arguments.

## Official service documentation

Terms and quotas can change; check the provider before creating resources:

- [Render's free service limits and no-payment-method behavior](https://render.com/docs/free)
- [Render's free first deployment](https://render.com/docs/your-first-deploy)
- [Render Blueprint fields and explicit free plan](https://render.com/docs/blueprint-spec)
- [Docker deployments on Render](https://render.com/docs/docker)
- [Render billing FAQ](https://render.com/docs/faq)
- [Aiven PostgreSQL Free plan](https://aiven.io/docs/products/postgresql/concepts/pg-free-tier)
