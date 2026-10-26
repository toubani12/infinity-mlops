package io.infinity.core.transaction;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.Instant;
import java.util.UUID;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

@Entity
@Table(name = "transactions")
public class Transaction {

    @Id
    @Column(name = "transaction_id")
    private UUID id;

    @Column(name = "occurred_at", nullable = false)
    private Instant occurredAt;

    @Column(name = "received_at", nullable = false)
    private Instant receivedAt;

    @Column(nullable = false)
    private double amount;

    @JdbcTypeCode(SqlTypes.ARRAY)
    @Column(nullable = false)
    private double[] features;

    private Integer label;

    @Column(name = "fraud_score")
    private Double fraudScore;

    @Column(name = "is_fraud")
    private Boolean fraud;

    @Column(name = "model_version")
    private String modelVersion;

    @Column(name = "scored_at")
    private Instant scoredAt;

    @Column(name = "published_at")
    private Instant publishedAt;

    protected Transaction() {
    }

    public Transaction(UUID id, Instant occurredAt, Instant receivedAt, double amount, double[] features, Integer label) {
        this.id = id;
        this.occurredAt = occurredAt;
        this.receivedAt = receivedAt;
        this.amount = amount;
        this.features = features.clone();
        this.label = label;
    }

    public void applyScore(double fraudScore, boolean fraud, String modelVersion, Instant scoredAt) {
        this.fraudScore = fraudScore;
        this.fraud = fraud;
        this.modelVersion = modelVersion;
        this.scoredAt = scoredAt;
    }

    public void markPublished(Instant at) {
        this.publishedAt = at;
    }

    public UUID getId() {
        return id;
    }

    public Instant getOccurredAt() {
        return occurredAt;
    }

    public Instant getReceivedAt() {
        return receivedAt;
    }

    public double getAmount() {
        return amount;
    }

    public double[] getFeatures() {
        return features.clone();
    }

    public Integer getLabel() {
        return label;
    }

    public Double getFraudScore() {
        return fraudScore;
    }

    public Boolean getFraud() {
        return fraud;
    }

    public String getModelVersion() {
        return modelVersion;
    }

    public Instant getScoredAt() {
        return scoredAt;
    }

    public Instant getPublishedAt() {
        return publishedAt;
    }
}
