# EPL Data Ingestion Plan

- Primary source: Football-Data.co.uk England data (2016-2026).
- Backup source: Kaggle EPL datasets.

Data fields to ingest per match:
- date (YYYY-MM-DD)
- home_team
- away_team
- home_score
- away_score
- competition_tier (e.g., Premier League, FA Cup, League Cup, Championship, etc.)
- venue (neutral/home/away) if available

Processing steps:
1) Download CSVs from Football-Data.co.uk for EPL 2016-2026.
2) Normalize team names to canonical IDs (e.g., EPL clubs mapping).
3) Build a master log in elo_project_data.md with a Markdown table of matches or a JSON array.
4) Validate data integrity: dates, non-negative scores, valid teams.
5) If missing League Cup data, pull from Kaggle backup and merge by date and competition tier.

Output:
- elo_project_data.md containing the ingested matches with provenance notes.

Provenance notes:
- Record source URL and license per dataset; track version and fetch date.

Next actions:
- Implement a small Python script (or coding-agent task) to perform the ingest automatically.
Pipeline documented in README-like_plan.md.
