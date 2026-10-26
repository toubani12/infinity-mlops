package io.infinity.core.messaging;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.JsonNode;
import io.infinity.core.modelops.AgentStep;
import io.infinity.core.modelops.AgentStepEvent;
import java.time.Instant;
import java.util.UUID;

@JsonIgnoreProperties(ignoreUnknown = true)
public record AgentEventMessage(
        @JsonProperty("run_id") UUID runId,
        @JsonProperty("event_id") UUID eventId,
        @JsonProperty("timestamp") Instant timestamp,
        @JsonProperty("step") String step,
        @JsonProperty("decision") String decision,
        @JsonProperty("requires_approval") Boolean requiresApproval,
        @JsonProperty("message") String message,
        @JsonProperty("payload") JsonNode payload) {

    public AgentStepEvent toStepEvent() {
        if (runId == null || eventId == null || timestamp == null || step == null || requiresApproval == null
                || payload == null || !payload.isObject()) {
            throw new InvalidMessageException("agent.events is missing a required field");
        }
        AgentStep known = AgentStep.fromWire(step)
                .orElseThrow(() -> new InvalidMessageException("agent.events has an unknown step: " + step));
        return new AgentStepEvent(runId, eventId, timestamp, known, decision, requiresApproval, message, payload);
    }
}
