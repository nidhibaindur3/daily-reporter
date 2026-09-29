# Deploying to Render

**Status:** A personal and prototype deployment baseline is available. Production
authentication, backups, budgets, and alerting are still planned.

## What the Blueprint creates

The root [Render Blueprint](../render.yaml) provisions four resources in the
Ohio region:

| Resource | Render type | Default compute |
| --- | --- | --- |
| `daily-digest-web` | Static site | Free CDN hosting |
| `daily-digest-api` | Python web service | Free |
| `daily-digest-worker` | Python background worker | `0.5c-512mb` paid plan |
| `daily-digest-db` | PostgreSQL 16 | Free |

The static frontend uses the API's generated `RENDER_EXTERNAL_URL` at build
time. The API uses the frontend's generated URL as its exact CORS origin. The
API and worker use the database's private-network `DATABASE_URL`, and the worker
reuses the API service's provider secrets.

The worker runs `alembic upgrade head` as a pre-deploy command. This keeps
migrations out of the API request process while supporting the free API plan,
which cannot run Render pre-deploy commands.

## Create the deployment

1. Push this repository to a Git provider supported by Render.
2. In the Render Dashboard, choose **New > Blueprint** and select the repository.
3. Keep the Blueprint path as **render.yaml**.
4. Enter **FINNHUB_API_KEY** and **OPENAI_API_KEY** when Render prompts for the
   two `sync: false` values.
5. Review the resources and apply the Blueprint.
6. Wait for the database, worker, API, and static site deploys to complete.

Do not add either provider key to a `VITE_` variable. Vite variables are bundled
into public browser assets.

## Verify the deployment

Open the API's public URL from its Render service page and check:

    curl https://YOUR-API.onrender.com/api/health

The expected response is:

    {"status":"ok"}

Then open the `daily-digest-web` URL and verify that:

1. Watchlist cards load without a browser CORS error.
2. Starting Research Discovery returns an accepted run.
3. The `daily-digest-worker` logs show that it claims and completes the job.
4. The completed opportunity and its evidence links appear in the frontend.

If the API reports a database error or the research tables are missing, inspect
the worker's latest pre-deploy logs for the Alembic failure before retrying the
deploy.

## Current operational limits

- The application has no authentication. Anyone who can reach the frontend or
  API URL can start provider-backed work. Keep the URLs private and monitor
  Finnhub and OpenAI usage until authentication and budgets are implemented.
- Render's free web service sleeps after an idle period, so the first API call
  can be slow.
- Free Render Postgres is limited, has no backups, and expires after 30 days.
  Upgrade the database before storing data that must survive.
- Render background workers do not have a free compute plan. The Blueprint uses
  the smallest general-purpose paid worker plan.
- The database blocks external connections with `ipAllowList: []`. The API and
  worker can still connect over Render's private network. Use Render's approved
  connection controls rather than opening the database to the internet.

Before calling the deployment production-ready, add authentication and provider
budgets, upgrade PostgreSQL to a backed-up paid plan, choose an API plan that
does not sleep, configure monitoring and alerts, and test backup restoration.

## Configuration changes

Non-secret shared backend settings live in the
`daily-digest-backend-config` environment group in **render.yaml**. Secrets are
owned by the API service and referenced by the worker. After changing a
`VITE_` variable, rebuild the static site because Vite embeds it at build time.

The backend accepts either:

- A single `DATABASE_URL`, used by Render and other hosted environments, or
- The existing `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`,
  `POSTGRES_HOST`, and `POSTGRES_PORT` settings used by local Docker Compose.

`DATABASE_URL` takes precedence when both forms are present.
