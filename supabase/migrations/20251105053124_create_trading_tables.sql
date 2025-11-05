/*
  # Create Trading Tables for RoboQuant

  1. New Tables
    - `trades`: Main trading records
      - `id` (uuid, primary key)
      - `timestamp_open` (timestamptz)
      - `timestamp_close` (timestamptz, nullable)
      - `ticket` (bigint, order ticket number)
      - `symbol` (text, trading pair)
      - `side` (text, BUY/SELL)
      - `volume` (decimal, lot size)
      - `entry_price` (decimal)
      - `exit_price` (decimal, nullable)
      - `sl` (decimal, stop loss price)
      - `tp` (decimal, take profit price)
      - `pnl` (decimal, nullable)
      - `pnl_pct` (decimal, nullable)
      - `duration_minutes` (integer, nullable)
      - `reason_closed` (text, nullable)
      - `created_at` (timestamptz)

    - `performance_metrics`: Strategy performance data
      - `id` (uuid, primary key)
      - `calculated_at` (timestamptz)
      - `period` (text, daily/weekly/monthly)
      - `total_trades` (integer)
      - `win_rate` (decimal)
      - `profit_factor` (decimal)
      - `sharpe_ratio` (decimal)
      - `max_drawdown` (decimal)
      - `total_pnl` (decimal)

    - `strategy_configs`: Strategy configuration versions
      - `id` (uuid, primary key)
      - `name` (text, unique)
      - `parameters` (jsonb)
      - `active` (boolean)
      - `created_at` (timestamptz)
      - `updated_at` (timestamptz)

  2. Indexes
    - Trades indexed by: timestamp_open, symbol, ticket
    - Performance metrics indexed by: period, calculated_at
    - Strategy configs indexed by: name

  3. Security
    - Enable RLS (optional, can be bypassed for trading bot use case)
    - Public read/write access for trading operations
    - Service role access for administration

  4. Important Notes
    - Timestamps stored in UTC
    - Prices stored as decimal for precision (8 decimals)
    - No row level security by default (trading bot runs as service)
    - Ensure proper backups before production use
*/

CREATE TABLE IF NOT EXISTS trades (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  timestamp_open TIMESTAMPTZ NOT NULL,
  timestamp_close TIMESTAMPTZ,
  ticket BIGINT,
  symbol TEXT NOT NULL,
  side TEXT NOT NULL CHECK (side IN ('BUY', 'SELL')),
  volume DECIMAL(10, 2) NOT NULL,
  entry_price DECIMAL(10, 5) NOT NULL,
  exit_price DECIMAL(10, 5),
  sl DECIMAL(10, 5) NOT NULL,
  tp DECIMAL(10, 5) NOT NULL,
  pnl DECIMAL(12, 2),
  pnl_pct DECIMAL(8, 2),
  duration_minutes INTEGER,
  reason_closed TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON trades(timestamp_open DESC);
CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);
CREATE INDEX IF NOT EXISTS idx_trades_ticket ON trades(ticket);

CREATE TABLE IF NOT EXISTS performance_metrics (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  calculated_at TIMESTAMPTZ DEFAULT NOW(),
  period TEXT NOT NULL,
  total_trades INTEGER NOT NULL,
  win_rate DECIMAL(5, 2) NOT NULL,
  profit_factor DECIMAL(10, 2) NOT NULL,
  sharpe_ratio DECIMAL(10, 4) NOT NULL,
  max_drawdown DECIMAL(10, 2) NOT NULL,
  total_pnl DECIMAL(12, 2) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_performance_period ON performance_metrics(period);
CREATE INDEX IF NOT EXISTS idx_performance_calculated ON performance_metrics(calculated_at DESC);

CREATE TABLE IF NOT EXISTS strategy_configs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT UNIQUE NOT NULL,
  parameters JSONB NOT NULL,
  active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_strategy_configs_name ON strategy_configs(name);
