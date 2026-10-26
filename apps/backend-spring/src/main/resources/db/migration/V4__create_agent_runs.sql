CREATE TABLE agent_run (
    run_id                     UUID PRIMARY KEY,
    status                     VARCHAR(24) NOT NULL CHECK (status IN ('RUNNING', 'AWAITING_APPROVAL', 'PROMOTED',
                                   'REJECTED', 'KEPT_CHAMPION', 'ESCALATED', 'FAILED', 'NOISE')),
    report_id                  UUID,
    started_at                 TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_at                 TIMESTAMP WITH TIME ZONE NOT NULL,
    last_step                  VARCHAR(32) NOT NULL,
    last_decision              VARCHAR(16),
    last_message               VARCHAR(4000),
    event_count                INTEGER NOT NULL,
    champion_version           VARCHAR(64),
    champion_pr_auc            DOUBLE PRECISION,
    champion_recall_at_p90     DOUBLE PRECISION,
    champion_p95_latency_ms    DOUBLE PRECISION,
    challenger_version         VARCHAR(64),
    challenger_pr_auc          DOUBLE PRECISION,
    challenger_recall_at_p90   DOUBLE PRECISION,
    challenger_p95_latency_ms  DOUBLE PRECISION,
    gate_passed                BOOLEAN,
    gate_reasons               VARCHAR(512) ARRAY,
    command_id                 UUID,
    command_action             VARCHAR(8) CHECK (command_action IN ('approve', 'reject')),
    command_actor              VARCHAR(128),
    command_reason             VARCHAR(500),
    command_sent_at            TIMESTAMP WITH TIME ZONE,
    decided_by                 VARCHAR(128),
    decision_reason            VARCHAR(500),
    promoted_version           VARCHAR(64),
    row_version                BIGINT NOT NULL
);

CREATE INDEX idx_agent_run_started_at ON agent_run (started_at DESC);
CREATE INDEX idx_agent_run_status_started_at ON agent_run (status, started_at DESC);

CREATE TABLE agent_run_event (
    event_id          UUID PRIMARY KEY,
    run_id            UUID NOT NULL REFERENCES agent_run (run_id),
    seq               INTEGER NOT NULL,
    occurred_at       TIMESTAMP WITH TIME ZONE NOT NULL,
    step              VARCHAR(32) NOT NULL,
    decision          VARCHAR(16),
    requires_approval BOOLEAN NOT NULL,
    message           VARCHAR(4000),
    payload           VARCHAR(16000) NOT NULL,
    received_at       TIMESTAMP WITH TIME ZONE NOT NULL,
    UNIQUE (run_id, seq)
);
