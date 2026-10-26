-- Kept to SQL that both PostgreSQL and H2 (PostgreSQL mode, used by the slice tests) accept.

CREATE TABLE transactions (
    transaction_id UUID PRIMARY KEY,
    occurred_at    TIMESTAMP WITH TIME ZONE NOT NULL,
    received_at    TIMESTAMP WITH TIME ZONE NOT NULL,
    amount         DOUBLE PRECISION NOT NULL CHECK (amount >= 0),
    features       DOUBLE PRECISION ARRAY NOT NULL CHECK (CARDINALITY(features) = 28),
    label          SMALLINT CHECK (label IN (0, 1)),
    fraud_score    DOUBLE PRECISION CHECK (fraud_score BETWEEN 0 AND 1),
    is_fraud       BOOLEAN,
    model_version  VARCHAR(64),
    scored_at      TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_transactions_received_at ON transactions (received_at DESC);
CREATE INDEX idx_transactions_fraud_received_at ON transactions (is_fraud, received_at DESC);

CREATE TABLE alerts (
    id             UUID PRIMARY KEY,
    transaction_id UUID NOT NULL UNIQUE REFERENCES transactions (transaction_id),
    fraud_score    DOUBLE PRECISION NOT NULL CHECK (fraud_score BETWEEN 0 AND 1),
    status         VARCHAR(16) NOT NULL CHECK (status IN ('OPEN', 'ACKNOWLEDGED', 'CLOSED')),
    created_at     TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_at     TIMESTAMP WITH TIME ZONE NOT NULL
);

CREATE INDEX idx_alerts_status_created_at ON alerts (status, created_at DESC);
