package io.infinity.core.modelops;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "agent_run_event")
public class AgentRunEvent {

    @Id
    @Column(name = "event_id")
    private UUID id;

    @Column(name = "run_id", nullable = false)
    private UUID runId;

    @Column(nullable = false)
    private int seq;

    @Column(name = "occurred_at", nullable = false)
    private Instant occurredAt;

    @Column(nullable = false)
    private String step;

    private String decision;

    @Column(name = "requires_approval", nullable = false)
    private boolean requiresApproval;

    private String message;

    @Column(nullable = false)
    private String payload;

    @Column(name = "received_at", nullable = false)
    private Instant receivedAt;

    protected AgentRunEvent() {
    }

    public AgentRunEvent(AgentStepEvent event, int seq, String payload, Instant receivedAt) {
        this.id = event.eventId();
        this.runId = event.runId();
        this.seq = seq;
        this.occurredAt = event.timestamp();
        this.step = event.step().wireName();
        this.decision = event.decision();
        this.requiresApproval = event.requiresApproval();
        this.message = AgentRun.truncate(event.message());
        this.payload = payload;
        this.receivedAt = receivedAt;
    }

    public UUID getId() {
        return id;
    }

    public UUID getRunId() {
        return runId;
    }

    public int getSeq() {
        return seq;
    }

    public Instant getOccurredAt() {
        return occurredAt;
    }

    public String getStep() {
        return step;
    }

    public String getDecision() {
        return decision;
    }

    public boolean isRequiresApproval() {
        return requiresApproval;
    }

    public String getMessage() {
        return message;
    }

    public String getPayload() {
        return payload;
    }
}
