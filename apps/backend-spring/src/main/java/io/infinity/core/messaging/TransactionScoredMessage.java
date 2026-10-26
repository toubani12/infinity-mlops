package io.infinity.core.messaging;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;
import io.infinity.core.alert.ScoreUpdate;
import java.time.Instant;
import java.util.UUID;

@JsonIgnoreProperties(ignoreUnknown = true)
public record TransactionScoredMessage(
        @JsonProperty("transaction_id") UUID transactionId,
        @JsonProperty("timestamp") Instant timestamp,
        @JsonProperty("fraud_score") Double fraudScore,
        @JsonProperty("is_fraud") Boolean fraud,
        @JsonProperty("threshold") Double threshold,
        @JsonProperty("model_name") String modelName,
        @JsonProperty("model_version") String modelVersion,
        @JsonProperty("latency_ms") Double latencyMs) {

    public ScoreUpdate toScoreUpdate() {
        if (transactionId == null || timestamp == null || fraud == null || modelVersion == null) {
            throw new InvalidMessageException("transaction.scored is missing a required field");
        }
        if (fraudScore == null || fraudScore < 0 || fraudScore > 1) {
            throw new InvalidMessageException("transaction.scored fraud_score must be within [0, 1]");
        }
        return new ScoreUpdate(transactionId, fraudScore, fraud, modelVersion, timestamp);
    }
}
