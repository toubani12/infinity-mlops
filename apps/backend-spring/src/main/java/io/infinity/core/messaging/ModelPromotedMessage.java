package io.infinity.core.messaging;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;
import io.infinity.core.modelops.ModelVersionEvent;
import java.time.Instant;
import java.util.UUID;

@JsonIgnoreProperties(ignoreUnknown = true)
public record ModelPromotedMessage(
        @JsonProperty("event_id") UUID eventId,
        @JsonProperty("timestamp") Instant timestamp,
        @JsonProperty("run_id") UUID runId,
        @JsonProperty("model_name") String modelName,
        @JsonProperty("version") String version,
        @JsonProperty("alias") String alias,
        @JsonProperty("previous_version") String previousVersion,
        @JsonProperty("reason") String reason) {

    public ModelVersionEvent toEvent(Instant receivedAt) {
        if (eventId == null || timestamp == null || modelName == null || version == null || alias == null) {
            throw new InvalidMessageException("model.promoted is missing a required field");
        }
        return new ModelVersionEvent(
                eventId, timestamp, runId, modelName, version, alias, previousVersion, reason, receivedAt);
    }
}
