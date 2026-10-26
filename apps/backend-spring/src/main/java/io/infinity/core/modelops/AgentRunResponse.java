package io.infinity.core.modelops;

import java.time.Instant;
import java.util.UUID;

public record AgentRunResponse(
        UUID runId,
        AgentRunStatus status,
        UUID reportId,
        Instant startedAt,
        Instant updatedAt,
        String lastStep,
        String lastDecision,
        String lastMessage,
        String championVersion,
        String challengerVersion,
        String decidedBy,
        String decisionReason,
        String promotedVersion) {

    public static AgentRunResponse from(AgentRun run) {
        return new AgentRunResponse(run.getId(), run.getStatus(), run.getReportId(), run.getStartedAt(),
                run.getUpdatedAt(), run.getLastStep(), run.getLastDecision(), run.getLastMessage(),
                run.getChampion() == null ? null : run.getChampion().version(),
                run.getChallenger() == null ? null : run.getChallenger().version(),
                run.getDecidedBy(), run.getDecisionReason(), run.getPromotedVersion());
    }
}
