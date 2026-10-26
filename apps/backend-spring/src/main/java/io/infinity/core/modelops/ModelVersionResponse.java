package io.infinity.core.modelops;

import java.time.Instant;
import java.util.UUID;

public record ModelVersionResponse(
        UUID eventId,
        Instant timestamp,
        UUID runId,
        String modelName,
        String version,
        String alias,
        String previousVersion,
        String reason) {

    public static ModelVersionResponse from(ModelVersionEvent e) {
        return new ModelVersionResponse(e.getId(), e.getOccurredAt(), e.getRunId(), e.getModelName(), e.getVersion(),
                e.getAlias(), e.getPreviousVersion(), e.getReason());
    }
}
