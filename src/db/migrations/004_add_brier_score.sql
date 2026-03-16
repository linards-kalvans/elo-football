-- Add Brier score columns to predictions table for accuracy tracking

ALTER TABLE predictions ADD COLUMN brier_score REAL;
ALTER TABLE predictions ADD COLUMN scored_at TEXT;
