PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS intelligence_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    run_id TEXT NOT NULL UNIQUE,

    generated_at TEXT NOT NULL,
    completed_at TEXT,

    engine_version TEXT,
    source TEXT NOT NULL DEFAULT 'intelligence_orchestrator',

    market_regime TEXT,
    regime_confidence REAL,
    market_risk_level TEXT,

    stock_count INTEGER NOT NULL DEFAULT 0,
    prediction_count INTEGER NOT NULL DEFAULT 0,
    committee_decision_count INTEGER NOT NULL DEFAULT 0,

    prediction_center_seconds REAL NOT NULL DEFAULT 0,
    committee_seconds REAL NOT NULL DEFAULT 0,
    total_seconds REAL NOT NULL DEFAULT 0,

    cache_hit INTEGER NOT NULL DEFAULT 0
        CHECK (cache_hit IN (0, 1)),

    status TEXT NOT NULL DEFAULT 'completed'
        CHECK (
            status IN (
                'started',
                'completed',
                'partial',
                'failed'
            )
        ),

    error_message TEXT,
    metadata_json TEXT,

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS
idx_intelligence_runs_generated_at
ON intelligence_runs(generated_at);

CREATE INDEX IF NOT EXISTS
idx_intelligence_runs_market_regime
ON intelligence_runs(market_regime);

CREATE INDEX IF NOT EXISTS
idx_intelligence_runs_status
ON intelligence_runs(status);


CREATE TABLE IF NOT EXISTS prediction_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    run_id TEXT NOT NULL,
    symbol TEXT NOT NULL,

    rank_position INTEGER,

    recommendation TEXT,
    signal TEXT,

    prediction_score REAL,
    confidence REAL,
    probability REAL,

    current_price REAL,
    predicted_price REAL,
    target_price REAL,
    expected_return REAL,

    risk_level TEXT,
    prediction_horizon TEXT,

    reasons_json TEXT,
    indicators_json TEXT,
    payload_json TEXT,

    generated_at TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (run_id)
        REFERENCES intelligence_runs(run_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,

    UNIQUE (run_id, symbol)
);

CREATE INDEX IF NOT EXISTS
idx_prediction_snapshots_symbol
ON prediction_snapshots(symbol);

CREATE INDEX IF NOT EXISTS
idx_prediction_snapshots_generated_at
ON prediction_snapshots(generated_at);

CREATE INDEX IF NOT EXISTS
idx_prediction_snapshots_recommendation
ON prediction_snapshots(recommendation);

CREATE INDEX IF NOT EXISTS
idx_prediction_snapshots_score
ON prediction_snapshots(prediction_score);


CREATE TABLE IF NOT EXISTS committee_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    run_id TEXT NOT NULL,
    symbol TEXT NOT NULL,

    rank_position INTEGER,

    decision TEXT,
    committee_score REAL,
    confidence REAL,
    conviction_level TEXT,
    risk_level TEXT,

    technical_vote TEXT,
    quantitative_vote TEXT,
    institutional_vote TEXT,
    risk_vote TEXT,
    learning_vote TEXT,

    entry_price REAL,
    target_price REAL,
    stop_loss REAL,
    expected_return REAL,

    votes_json TEXT,
    reasons_json TEXT,
    payload_json TEXT,

    generated_at TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (run_id)
        REFERENCES intelligence_runs(run_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,

    UNIQUE (run_id, symbol)
);

CREATE INDEX IF NOT EXISTS
idx_committee_snapshots_symbol
ON committee_snapshots(symbol);

CREATE INDEX IF NOT EXISTS
idx_committee_snapshots_generated_at
ON committee_snapshots(generated_at);

CREATE INDEX IF NOT EXISTS
idx_committee_snapshots_decision
ON committee_snapshots(decision);

CREATE INDEX IF NOT EXISTS
idx_committee_snapshots_score
ON committee_snapshots(committee_score);


CREATE TABLE IF NOT EXISTS market_regime_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    run_id TEXT NOT NULL UNIQUE,

    generated_at TEXT NOT NULL,

    regime TEXT NOT NULL,
    confidence REAL,

    risk_level TEXT,
    volatility_level TEXT,
    breadth_score REAL,
    momentum_score REAL,
    trend_score REAL,

    bullish_count INTEGER,
    bearish_count INTEGER,
    neutral_count INTEGER,

    reasons_json TEXT,
    payload_json TEXT,

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (run_id)
        REFERENCES intelligence_runs(run_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS
idx_market_regime_history_generated_at
ON market_regime_history(generated_at);

CREATE INDEX IF NOT EXISTS
idx_market_regime_history_regime
ON market_regime_history(regime);
