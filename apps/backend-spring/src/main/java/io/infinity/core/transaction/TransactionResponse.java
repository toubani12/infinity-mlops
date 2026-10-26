package io.infinity.core.transaction;

import java.time.Instant;
import java.util.Map;
import java.util.UUID;

public record TransactionResponse(
        UUID transactionId,
        Instant timestamp,
        Instant receivedAt,
        double amount,
        Map<String, Double> features,
        Integer label,
        Double fraudScore,
        Boolean isFraud,
        String modelVersion,
        Instant scoredAt) {

    public static TransactionResponse from(Transaction t) {
        return new TransactionResponse(
                t.getId(),
                t.getOccurredAt(),
                t.getReceivedAt(),
                t.getAmount(),
                Features.toMap(t.getFeatures()),
                t.getLabel(),
                t.getFraudScore(),
                t.getFraud(),
                t.getModelVersion(),
                t.getScoredAt());
    }
}
