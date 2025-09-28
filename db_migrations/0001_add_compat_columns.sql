-- Migration: add compatibility columns expected by code/tests to existing SQLite DB
-- This file is safe to run multiple times; each ALTER is guarded by try/except in sqlite CLI
PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;

-- Add columns to pnl_reports if missing
ALTER TABLE pnl_reports ADD COLUMN total_pnl REAL DEFAULT 0.0;
ALTER TABLE pnl_reports ADD COLUMN fees REAL DEFAULT 0.0;
ALTER TABLE pnl_reports ADD COLUMN trades_count INTEGER DEFAULT 0;
ALTER TABLE pnl_reports ADD COLUMN win_rate REAL DEFAULT 0.0;

-- Make risk_events.message nullable and add description/data columns if missing
ALTER TABLE risk_events ADD COLUMN description TEXT;
ALTER TABLE risk_events ADD COLUMN data JSON;

COMMIT;
