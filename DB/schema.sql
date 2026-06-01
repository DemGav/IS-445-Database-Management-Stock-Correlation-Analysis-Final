-- ─────────────────────────────────────────────────────────────────────────────
-- IS 445 — Defensive Assets Project
-- MySQL Schema
--
-- Run this script once against the database named in your .env file to create
-- the two tables the application expects.
--
-- Usage:
--   mysql -u <user> -p <database_name> < schema.sql
-- ─────────────────────────────────────────────────────────────────────────────

-- ---------------------------------------------------------------------------
-- Table: ticker_symbol
-- Stores each unique ETF / ticker that has been loaded into the system.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ticker_symbol (
    ticker_id     INT         NOT NULL AUTO_INCREMENT,
    ticker_symbol VARCHAR(20) NOT NULL,
    PRIMARY KEY (ticker_id),
    UNIQUE KEY uq_ticker_symbol (ticker_symbol)
);

-- ---------------------------------------------------------------------------
-- Table: stock_prices
-- Stores daily OHLCV price rows for every ticker.
-- ticker_id is a foreign key back to ticker_symbol.
-- The unique key on (ticker_id, price_date) prevents duplicate date inserts
-- and also makes stress-day and portfolio queries fast.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS stock_prices (
    price_id   INT     NOT NULL AUTO_INCREMENT,
    ticker_id  INT     NOT NULL,
    price_date DATE    NOT NULL,
    open       DOUBLE  NULL,
    close      DOUBLE  NULL,
    high       DOUBLE  NULL,
    low        DOUBLE  NULL,
    volume     BIGINT  NULL,
    PRIMARY KEY (price_id),
    UNIQUE KEY uq_ticker_date (ticker_id, price_date),
    CONSTRAINT fk_price_ticker
        FOREIGN KEY (ticker_id)
        REFERENCES ticker_symbol (ticker_id)
        ON DELETE CASCADE
);
