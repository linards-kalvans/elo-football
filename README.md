# Elo Football

Elo rating system for European football clubs — a web application providing current and historical Elo ratings, team comparisons, and match win-probability predictions.

Rates **300+ teams** across 5 domestic leagues (EPL, La Liga, Bundesliga, Serie A, Ligue 1) plus Champions League, Europa League, and Conference League — over **20,000 matches** processed.

## Features

- **Rankings** — Sortable league-wide Elo rankings with search and filtering
- **Team Profiles** — Individual team pages with rating history chart, stats card (form, trend, peak/trough), and recent results
- **Comparison Charts** — Multi-team Elo history overlay with adjustable time range slider
- **Match Predictions** — Select two teams and get win/draw/loss probabilities based on Elo difference

## How the Elo System Works

Each team starts at a base rating (default 1400). After every match, ratings adjust based on:

- **Expected vs actual result** — Bigger upsets cause larger rating swings
- **Home advantage** — Home team gets a rating bonus (default +55)
- **Margin of victory** — Larger wins produce bigger changes (FiveThirtyEight formula)
- **Time decay** — Ratings regress toward the mean between seasons (decay rate 0.90)
- **Competition tier weighting** — Champions League knockout matches carry more weight (1.5x) than domestic league matches (1.0x)

All parameters are configurable via environment variables with the `ELO_` prefix.

## Quick Start

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager

### Install & Run

```bash
# Install dependencies
uv sync

# Build the database (fetches data, computes ratings, writes to SQLite)
uv run python -c "from src.pipeline import run_pipeline; run_pipeline()"

# Start the web app
uv run uvicorn backend.main:app --reload
```

The app will be available at [http://localhost:8000](http://localhost:8000).

### Run with Docker

```bash
# Build and start
docker compose up --build -d

# App available at http://localhost:8000
```

The database is persisted via a volume mount to `./data/`.

### Run Tests

```bash
uv run pytest tests/ -v    # 164 tests
uv run ruff check .         # Linting
```

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | FastAPI, aiosqlite, Jinja2 |
| Frontend | Alpine.js, ApexCharts, Tailwind CSS (CDN) |
| Database | SQLite (WAL mode) |
| Deployment | Docker, GitHub Actions CI/CD |
| Package Manager | uv |

## Project Structure

```
src/               Core library (Elo engine, config, data loading, prediction)
  elo_engine.py      EloEngine class — compute_ratings(), get_rankings()
  config.py          EloSettings (Pydantic, env-configurable)
  prediction.py      Match outcome probability calculator
  pipeline.py        Idempotent data ingestion pipeline
  db/                SQLite schema, repository, validation
backend/           FastAPI web application
  main.py            REST API endpoints + page routes
  models.py          Pydantic response models
  templates/         Jinja2 HTML templates
data/              Match data (5 leagues + European competitions)
tests/             pytest test suite
docs/              Sprint plans, milestones, architecture decisions
```

## API

Interactive API docs are available at `/docs` (Swagger UI) when the app is running.

Key endpoints:

| Endpoint | Description |
|----------|-------------|
| `GET /api/rankings` | All teams ranked by Elo |
| `GET /api/teams/{id}` | Team details and current rating |
| `GET /api/teams/{id}/history` | Rating history over time |
| `GET /api/teams/{id}/results` | Recent matches with Elo changes |
| `GET /api/predict` | Win/draw/loss probability for two teams |
| `GET /api/search` | Team name search with autocomplete |
| `GET /api/health` | Health check |

## Configuration

All Elo parameters can be set via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `ELO_K_FACTOR` | 20 | Rating adjustment magnitude |
| `ELO_HOME_ADVANTAGE` | 55 | Home team rating bonus |
| `ELO_DECAY_RATE` | 0.90 | Between-season regression factor |
| `ELO_PROMOTED_ELO` | 1400 | Starting rating for new teams |
| `ELO_SPREAD` | 400 | Logistic curve spread parameter |
| `CORS_ORIGINS` | `*` | Allowed CORS origins (comma-separated) |

## License

Private project.
