package io.infinity.core.alert;

import java.time.Instant;
import java.util.UUID;

public record AlertResponse(
        UUID id, UUID transactionId, double fraudScore, AlertStatus status, Instant createdAt, Instant updatedAt) {

    public static AlertResponse from(Alert alert) {
        return new AlertResponse(
                alert.getId(),
                alert.getTransactionId(),
                alert.getFraudScore(),
                alert.getStatus(),
                alert.getCreatedAt(),
                alert.getUpdatedAt());
    }
}
