package io.infinity.core.modelops;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "model_version_event")
public class ModelVersionEvent {

    @Id
    @Column(name = "event_id")
    private UUID id;

    @Column(name = "occurred_at", nullable = false)
    private Instant occurredAt;

    @Column(name = "run_id")
    private UUID runId;

    @Column(name = "model_name", nullable = false)
    private String modelName;

    @Column(nullable = false)
    private String version;

    @Column(nullable = false)
    private String alias;

    @Column(name = "previous_version")
    private String previousVersion;

    private String reason;

    @Column(name = "received_at", nullable = false)
    private Instant receivedAt;

    protected ModelVersionEvent() {
    }

    public ModelVersionEvent(UUID id, Instant occurredAt, UUID runId, String modelName, String version, String alias,
            String previousVersion, String reason, Instant receivedAt) {
        this.id = id;
        this.occurredAt = occurredAt;
        this.runId = runId;
        this.modelName = modelName;
        this.version = version;
        this.alias = alias;
        this.previousVersion = previousVersion;
        this.reason = reason;
        this.receivedAt = receivedAt;
    }

    public UUID getId() {
        return id;
    }

    public Instant getOccurredAt() {
        return occurredAt;
    }

    public UUID getRunId() {
        return runId;
    }

    public String getModelName() {
        return modelName;
    }

    public String getVersion() {
        return version;
    }

    public String getAlias() {
        return alias;
    }

    public String getPreviousVersion() {
        return previousVersion;
    }

    public String getReason() {
        return reason;
    }

    public Instant getReceivedAt() {
        return receivedAt;
    }
}
