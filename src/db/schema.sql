-- Elo rating system schema

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS teams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    country TEXT NOT NULL DEFAULT '',
    aliases TEXT NOT NULL DEFAULT '[]'  -- JSON array of alternative names
);

-- FTS5 virtual table for fast team search (multi-language aliases)
CREATE VIRTUAL TABLE IF NOT EXISTS teams_fts USING fts5(
    name,
    aliases,
    content=teams,
    content_rowid=id
);

-- Triggers to keep FTS index in sync with teams table
CREATE TRIGGER IF NOT EXISTS teams_ai AFTER INSERT ON teams BEGIN
    INSERT INTO teams_fts(rowid, name, aliases) VALUES (new.id, new.name, new.aliases);
END;

CREATE TRIGGER IF NOT EXISTS teams_ad AFTER DELETE ON teams BEGIN
    INSERT INTO teams_fts(teams_fts, rowid, name, aliases) VALUES ('delete', old.id, old.name, old.aliases);
END;

CREATE TRIGGER IF NOT EXISTS teams_au AFTER UPDATE ON teams BEGIN
    INSERT INTO teams_fts(teams_fts, rowid, name, aliases) VALUES ('delete', old.id, old.name, old.aliases);
    INSERT INTO teams_fts(rowid, name, aliases) VALUES (new.id, new.name, new.aliases);
END;

CREATE TABLE IF NOT EXISTS competitions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    tier INTEGER NOT NULL DEFAULT 5,
    country TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,  -- ISO 8601 (YYYY-MM-DD)
    home_team_id INTEGER NOT NULL REFERENCES teams(id),
    away_team_id INTEGER NOT NULL REFERENCES teams(id),
    home_goals INTEGER NOT NULL,
    away_goals INTEGER NOT NULL,
    result TEXT NOT NULL CHECK (result IN ('H', 'D', 'A')),
    competition_id INTEGER NOT NULL REFERENCES competitions(id),
    season TEXT NOT NULL,
    UNIQUE(date, home_team_id, away_team_id, competition_id)
);

CREATE TABLE IF NOT EXISTS ratings_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id INTEGER NOT NULL REFERENCES teams(id),
    match_id INTEGER NOT NULL REFERENCES matches(id),
    date TEXT NOT NULL,
    rating REAL NOT NULL,
    rating_delta REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS parameters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_timestamp TEXT NOT NULL,
    k_factor REAL NOT NULL,
    home_advantage REAL NOT NULL,
    decay_rate REAL NOT NULL,
    promoted_elo REAL NOT NULL,
    spread REAL NOT NULL,
    matches_processed INTEGER NOT NULL
);

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
    brier_score REAL,
    scored_at TEXT,
    source TEXT NOT NULL DEFAULT 'live',
    CHECK (
        (match_id IS NOT NULL AND fixture_id IS NULL) OR
        (match_id IS NULL AND fixture_id IS NOT NULL)
    )
);

CREATE TABLE IF NOT EXISTS api_team_mappings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    api_source TEXT NOT NULL,          -- e.g., 'football-data.org'
    api_team_id INTEGER NOT NULL,      -- team ID in the external API
    api_team_name TEXT NOT NULL,       -- team name as returned by API
    team_id INTEGER NOT NULL REFERENCES teams(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(api_source, api_team_id)
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_ratings_team_date ON ratings_history(team_id, date);
CREATE INDEX IF NOT EXISTS idx_matches_date ON matches(date);
CREATE INDEX IF NOT EXISTS idx_matches_competition ON matches(competition_id);
CREATE INDEX IF NOT EXISTS idx_ratings_match ON ratings_history(match_id);
CREATE INDEX IF NOT EXISTS idx_fixtures_status ON fixtures(status);
CREATE INDEX IF NOT EXISTS idx_fixtures_date ON fixtures(date);
CREATE INDEX IF NOT EXISTS idx_predictions_fixture ON predictions(fixture_id);
CREATE INDEX IF NOT EXISTS idx_predictions_match ON predictions(match_id);
CREATE INDEX IF NOT EXISTS idx_api_team_mappings_source ON api_team_mappings(api_source, api_team_id);
CREATE INDEX IF NOT EXISTS idx_api_team_mappings_team ON api_team_mappings(team_id);
