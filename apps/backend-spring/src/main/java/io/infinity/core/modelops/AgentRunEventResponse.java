package io.infinity.core.modelops;

import com.fasterxml.jackson.annotation.JsonRawValue;
import java.time.Instant;
import java.util.UUID;

public record AgentRunEventResponse(
        UUID eventId,
        UUID runId,
        int seq,
        Instant timestamp,
        String step,
        String decision,
        boolean requiresApproval,
        String message,
        @JsonRawValue String payload) {

    public static AgentRunEventResponse from(AgentRunEvent e) {
        return new AgentRunEventResponse(e.getId(), e.getRunId(), e.getSeq(), e.getOccurredAt(), e.getStep(),
                e.getDecision(), e.isRequiresApproval(), e.getMessage(), e.getPayload());
    }
}
