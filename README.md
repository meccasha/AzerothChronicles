# Azeroth Chronicles

A private adventure journal, progression tracker and Hall of Fame for a group of friends who play
**World of Warcraft** together — across guilds, seasons and expansions.

- **Shared timeline** of boss kills, wipes-before-the-kill, achievements, notable loot, Mythic+ runs and
  hand-written memories, with comments, reactions, screenshots, favorites and pins.
- **Automatic capture** from a lightweight in-game addon (`addon/`) and Battle.net (achievements with real
  completion dates), with **provenance on every event** and cross-reporter **de-duplication**.
- **Statistics** aggregated server-side from recorded rows only, with explicit data-coverage notes.
- **Hall of Fame**: 10 automatic awards + 1 voted award, weekly / monthly / seasonal / all-time, reproducible.
- **Real game artwork**: item & achievement icons, boss portraits and dungeon/raid art from Blizzard's Game
  Data API (needs only a free Battle.net API client), with built-in icons as fallback.
- **Loot Museum**, member profiles, group settings (event & loot rules), integrations status page.
- Fully usable without Blizzard credentials: a **fictional demo group** and a **mock Battle.net** adapter.

> Not affiliated with Blizzard Entertainment. All demo people, characters, raids, bosses and items are fictional.

## Quick start (Docker)

```bash
cp .env.example .env
```

```bash
docker compose up --build
```

Open http://localhost:3000 and click **Explore the demo group**, or create an account and your own group.

## Quick start (local)

Requirements: Python 3.12+, Node 22+, PostgreSQL 16, [uv](https://docs.astral.sh/uv/).

```bash
make setup
```

```bash
createdb azeroth && make migrate && make seed
```

```bash
make api   # FastAPI on :8000
```

```bash
make web   # Next.js on :3000 (proxies /api to :8000)
```

Details: [docs/development.md](docs/development.md).

## Repository layout

```
backend/     FastAPI + SQLAlchemy 2 + Alembic API, ingestion, Battle.net adapter, stats, awards, tests
frontend/    Next.js (App Router) + Tailwind + shadcn-style UI + TanStack Query + Recharts; Vitest & Playwright
addon/       AzerothChronicles WoW Retail addon (Lua) — writes SavedVariables, never touches the network
companion/   Optional stdlib-only uploader that watches the SavedVariables file
docs/        Architecture, schema diagram, integration notes, award rules, deployment, status
```

## Documentation

| Doc | |
|---|---|
| [Architecture & schema](docs/architecture.md) | Components, data flow, ER diagram, dedup design, security |
| [Development](docs/development.md) | Local setup, migrations, demo data, tests |
| [Ingestion format](docs/ingestion-format.md) | The `azeroth-chronicles/v1` envelope used by addon, companion and simulated imports |
| [Battle.net integration](docs/blizzard-integration.md) | App registration, OAuth, endpoints used, verification checklist |
| [WoW addon](docs/addon.md) | Installation, events used, API-verification status, restrictions |
| [Awards](docs/awards.md) | Exact calculation rules and how to add a new award |
| [Deployment](docs/deployment.md) | Production configuration and checklist |
| [Status, risks & roadmap](docs/status.md) | What is implemented, what remains, known limitations |
| [Privacy policy template](docs/privacy-policy.md) | Starting point for operators |

## Tests

```bash
make test-backend   # 69 pytest tests incl. executing the real addon Lua against a mocked WoW API
```

```bash
make test-web       # TypeScript + Vitest
```

```bash
make e2e            # Playwright: register → group → import → timeline/stats/awards (+ mobile demo)
```
