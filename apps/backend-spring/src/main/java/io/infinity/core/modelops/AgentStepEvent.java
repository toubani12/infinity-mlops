package io.infinity.core.modelops;

import com.fasterxml.jackson.databind.JsonNode;
import java.time.Instant;
import java.util.UUID;
import org.springframework.lang.Nullable;

public record AgentStepEvent(
        UUID runId,
        UUID eventId,
        Instant timestamp,
        AgentStep step,
        @Nullable String decision,
        boolean requiresApproval,
        @Nullable String message,
        JsonNode payload) {
}
