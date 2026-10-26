package io.infinity.core.alert;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "alerts")
public class Alert {

    @Id
    private UUID id;

    @Column(name = "transaction_id", nullable = false, unique = true)
    private UUID transactionId;

    @Column(name = "fraud_score", nullable = false)
    private double fraudScore;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 16)
    private AlertStatus status;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt;

    @Column(name = "updated_at", nullable = false)
    private Instant updatedAt;

    protected Alert() {
    }

    public Alert(UUID id, UUID transactionId, double fraudScore, Instant createdAt) {
        this.id = id;
        this.transactionId = transactionId;
        this.fraudScore = fraudScore;
        this.status = AlertStatus.OPEN;
        this.createdAt = createdAt;
        this.updatedAt = createdAt;
    }

    public void moveTo(AlertStatus target, Instant at) {
        if (!status.canMoveTo(target)) {
            throw new IllegalStateException("Alert " + id + " cannot move from " + status + " to " + target);
        }
        if (target != status) {
            status = target;
            updatedAt = at;
        }
    }

    public UUID getId() {
        return id;
    }

    public UUID getTransactionId() {
        return transactionId;
    }

    public double getFraudScore() {
        return fraudScore;
    }

    public AlertStatus getStatus() {
        return status;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }

    public Instant getUpdatedAt() {
        return updatedAt;
    }
}
