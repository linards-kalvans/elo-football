# European Football Elo Rating Project

This document defines the plan for building Elo-based ratings for European clubs with a focus on the English Premier League (EPL) initial prototype and expansion to other leagues.

## Scope
- EPL prototype: 2016-2026 history, tiered match importance weighting, league-base starting values per league strength.
- Data sources: Football-Data.co.uk as primary for EPL data; Kaggle as backup.
- Output: maintain a single data-tracking Markdown entry (elo_project_data.md) with matches, parameters, and results; support historical Elo queries by date.

## Data sources & provenance
- Primary: Football-Data.co.uk England data (2016-2026) including EPL results; League Cup if available.
- Backup: Kaggle EPL datasets.

## Data model (ingest)
- Match record fields: date, home_team, away_team, home_score, away_score, competition_tier, venue
- Derived: result (home win/draw/away win), weight by competition tier

## Ingest plan (high level)
1) Fetch EPL data from Football-Data.co.uk for 2016-2026; parse CSV to match records.
2) Normalize team names to canonical IDs (e.g., EPL clubs).
3) Store in elo_project_data.md as a markdown table log (or as a JSON array if preferred).
4) Validate data quality (dates, scores, missing values).
5) If gaps, pull from Kaggle backup and merge with primary data, preserving provenance.

## Weights (initial)
- CL (Champions League) > EL (Europa League) > Conf. League > Premier League > FA Cup > Championship > League Cup > Lower leagues
- 10-year history window; implement time decay and tier multipliers in the Elo model (to be detailed in data ingests).

## Milestones
- M1: Data ingestion scaffolding in data_ingest.md and elo_project_data.md
- M2: Prototype Elo kernel with simple K-factor and time decay
- M3: Historical date querying interface

## Roles
- PM/Analyst: Elisa
- Development: Coding Agent

See data_ingest.py for the EPL pipeline code and elo_project_data.md for output.
