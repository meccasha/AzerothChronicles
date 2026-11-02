# Deployment

The stack is four containers (see `docker-compose.yml`): PostgreSQL, the API (runs `alembic upgrade head`
and, if `DEMO_MODE=true`, seeds the demo group on start), a worker, and the Next.js web server. Only the
web server needs to be public; it proxies `/api` to the API.

## Production checklist

- [ ] `APP_ENV=production`, `COOKIE_SECURE=true`, HTTPS in front (any reverse proxy / load balancer).
- [ ] `PUBLIC_WEB_URL`, `PUBLIC_API_URL` (= `${PUBLIC_WEB_URL}/api`) and `ALLOWED_ORIGINS` set to the real origin.
- [ ] `CREDENTIALS_ENCRYPTION_KEY` set (Fernet key) and backed up — losing it means users must re-link Battle.net.
- [ ] Strong `POSTGRES_PASSWORD`; database not exposed publicly; regular backups (`pg_dump`).
- [ ] `DEMO_MODE=false` and `python -m app.cli purge-demo` for a real group.
- [ ] Battle.net client registered with the production redirect URL; `BLIZZARD_ADAPTER=live`; run the
      verification checklist in [blizzard-integration.md](blizzard-integration.md).
- [ ] Persistent volume for `/app/uploads` (or adapt `EventMedia` storage to object storage).
- [ ] Build the frontend image with `--build-arg API_ORIGIN=http://<api-host>:8000`.
- [ ] Update `backend/app/data/periods.json` when a new expansion or season starts.

## Operations

* Health: `GET /api/health`.
* Migrations: the API container applies them on start (`RUN_MIGRATIONS=0` to disable, e.g. for workers).
* Logs: uvicorn access/error logs on stdout; ingestion and sync problems are also visible per user on the
  Integrations page (`sync_jobs`, `ingestion_records`).
* Scaling: the API is stateless (sessions in Postgres). Rate limiting for login is in-process; put a shared
  limiter (e.g. at the proxy) in front when running several API replicas.
