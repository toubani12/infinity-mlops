package io.infinity.core.transaction;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.PositiveOrZero;
import java.time.Instant;
import java.util.Map;
import java.util.UUID;

public record CreateTransactionRequest(
        UUID transactionId,
        Instant timestamp,
        @NotNull @PositiveOrZero Double amount,
        @NotNull @ValidFeatures Map<String, Double> features,
        @Min(0) @Max(1) Integer label) {
}
