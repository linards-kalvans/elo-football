-- Add source column to predictions table to distinguish live vs backfilled predictions.
ALTER TABLE predictions ADD COLUMN source TEXT NOT NULL DEFAULT 'live';
