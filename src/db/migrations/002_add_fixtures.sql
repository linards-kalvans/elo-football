-- Add fixtures and predictions tables for live match tracking

CREATE TABLE IF NOT EXISTS fixtures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,  -- ISO 8601 (YYYY-MM-DD)
    home_team_id INTEGER NOT NULL REFERENCES teams(id),
    away_team_id INTEGER NOT NULL REFERENCES teams(id),
    competition_id INTEGER NOT NULL REFERENCES competitions(id),
    season TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'scheduled'
        CHECK (status IN ('scheduled', 'completed', 'postponed', 'cancelled')),
    external_api_id TEXT,
    last_updated TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(date, home_team_id, away_team_id, competition_id)
);

CREATE TABLE IF NOT EXISTS predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id INTEGER REFERENCES matches(id),
    fixture_id INTEGER REFERENCES fixtures(id),
    predicted_at TEXT NOT NULL DEFAULT (datetime('now')),
    p_home REAL NOT NULL,
    p_draw REAL NOT NULL,
    p_away REAL NOT NULL,
    home_elo REAL NOT NULL,
    away_elo REAL NOT NULL,
    CHECK (
        (match_id IS NOT NULL AND fixture_id IS NULL) OR
        (match_id IS NULL AND fixture_id IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_fixtures_status ON fixtures(status);
CREATE INDEX IF NOT EXISTS idx_fixtures_date ON fixtures(date);
CREATE INDEX IF NOT EXISTS idx_predictions_fixture ON predictions(fixture_id);
CREATE INDEX IF NOT EXISTS idx_predictions_match ON predictions(match_id);
