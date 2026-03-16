-- Add API team mappings table for external API integration (e.g., football-data.org)

CREATE TABLE IF NOT EXISTS api_team_mappings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    api_source TEXT NOT NULL,          -- e.g., 'football-data.org'
    api_team_id INTEGER NOT NULL,      -- team ID in the external API
    api_team_name TEXT NOT NULL,       -- team name as returned by API
    team_id INTEGER NOT NULL REFERENCES teams(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(api_source, api_team_id)
);

CREATE INDEX IF NOT EXISTS idx_api_team_mappings_source ON api_team_mappings(api_source, api_team_id);
CREATE INDEX IF NOT EXISTS idx_api_team_mappings_team ON api_team_mappings(team_id);
