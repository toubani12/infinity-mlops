CREATE TABLE drift_report (
    report_id          UUID PRIMARY KEY,
    detected_at        TIMESTAMP WITH TIME ZONE NOT NULL,
    window_start       TIMESTAMP WITH TIME ZONE NOT NULL,
    window_end         TIMESTAMP WITH TIME ZONE NOT NULL,
    window_rows        INTEGER NOT NULL CHECK (window_rows >= 0),
    drift_share        DOUBLE PRECISION NOT NULL CHECK (drift_share BETWEEN 0 AND 1),
    drifted_features   VARCHAR(64) ARRAY NOT NULL,
    missing_features   VARCHAR(64) ARRAY NOT NULL,
    out_of_range_share DOUBLE PRECISION,
    pr_auc             DOUBLE PRECISION,
    reference_pr_auc   DOUBLE PRECISION,
    recall_at_p90      DOUBLE PRECISION,
    labeled_rows       INTEGER,
    model_version      VARCHAR(64),
    report_uri         VARCHAR(1024),
    received_at        TIMESTAMP WITH TIME ZONE NOT NULL
);

CREATE INDEX idx_drift_report_detected_at ON drift_report (detected_at DESC);

CREATE TABLE model_version_event (
    event_id         UUID PRIMARY KEY,
    occurred_at      TIMESTAMP WITH TIME ZONE NOT NULL,
    run_id           UUID,
    model_name       VARCHAR(128) NOT NULL,
    version          VARCHAR(64) NOT NULL,
    alias            VARCHAR(32) NOT NULL,
    previous_version VARCHAR(64),
    reason           VARCHAR(16),
    received_at      TIMESTAMP WITH TIME ZONE NOT NULL
);

CREATE INDEX idx_model_version_event_occurred_at ON model_version_event (occurred_at DESC);
