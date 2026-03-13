# Football Elo Rating API — Backend

FastAPI backend for querying European football club Elo ratings.

## Quick Start

### Install Dependencies

```bash
uv sync
```

### Run Development Server

```bash
uv run uvicorn backend.main:app --reload
```

The API will be available at `http://localhost:8000`.

### API Documentation

Once the server is running, visit:

- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc
- **OpenAPI JSON:** http://localhost:8000/openapi.json

## Project Structure

```
backend/
├── __init__.py          # Package marker
├── main.py              # FastAPI app + all endpoints
├── models.py            # Pydantic response models
└── README.md            # This file
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/health` | Health check |
| `GET` | `/api/rankings` | Current or historical rankings |
| `GET` | `/api/teams/{id}` | Team detail page |
| `GET` | `/api/teams/{id}/history` | Elo trajectory for charting |
| `GET` | `/api/predict` | Match prediction |
| `GET` | `/api/leagues` | List leagues/competitions |
| `GET` | `/api/search` | Team name search (FTS5) |

See [docs/api-contract.md](../docs/api-contract.md) for full API specification.

## Database Integration

The API connects to the SQLite database at `data/elo.db`. If the database doesn't exist, run the pipeline first:

```bash
uv run python -c "from src.pipeline import run_pipeline; run_pipeline()"
```

This will:
1. Seed the database with all historical data (300 teams, 20,833 matches)
2. Compute Elo ratings for all teams
3. Create full-text search index

## Testing

Run the quick endpoint test:

```bash
uv run python test_api.py
```

For comprehensive tests:

```bash
uv run pytest tests/ -v
```

## CORS Configuration

Development mode allows all origins (`*`). For production, update `backend/main.py`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourdomain.com"],  # Restrict to specific domains
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)
```

## Error Handling

All errors return a consistent JSON structure:

```json
{
  "error": "HTTPException",
  "message": "Human-readable error message",
  "detail": "Optional details"
}
```

See [docs/api-examples/](../docs/api-examples/) for example responses including errors.

## Production Deployment

### Environment Variables

None required yet. Future versions may add:

```bash
export DATABASE_URL=/path/to/elo.db
export API_KEY_REQUIRED=true
```

### Running with Gunicorn

```bash
uv add gunicorn
uv run gunicorn backend.main:app -w 4 -k uvicorn.workers.UvicornWorker
```

### Docker

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install uv && uv sync
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## OpenAPI Features

The FastAPI app includes:

- **Pydantic models** with field descriptions and examples
- **Endpoint tags** for logical grouping
- **Auto-generated schemas** for all request/response types
- **Error response models** documented per endpoint

## Next Steps

Sprint 7 will add:
- Frontend (HTMX + Alpine.js + Chart.js)
- Deployment (Docker, CI/CD)
- Additional endpoints if needed
