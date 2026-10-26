package io.infinity.core.alert;

import java.time.Instant;
import java.util.UUID;

public record ScoreUpdate(UUID transactionId, double fraudScore, boolean fraud, String modelVersion, Instant scoredAt) {
}
