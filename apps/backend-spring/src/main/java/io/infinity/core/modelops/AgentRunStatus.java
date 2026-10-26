package io.infinity.core.modelops;

import org.springframework.lang.Nullable;

public enum AgentRunStatus {
    RUNNING,
    AWAITING_APPROVAL,
    PROMOTED,
    REJECTED,
    KEPT_CHAMPION,
    ESCALATED,
    FAILED,
    NOISE;

    public boolean isFinal() {
        return this != RUNNING && this != AWAITING_APPROVAL;
    }

    /**
     * A final status never changes again: the agent still publishes {@code completed} after {@code rejected} or
     * {@code escalated}, and a late {@code received} (an alert attached to the run) must not reopen it.
     */
    public AgentRunStatus after(AgentStep step, @Nullable String decision) {
        if (isFinal()) {
            return this;
        }
        return switch (step) {
            case APPROVAL_REQUESTED -> AWAITING_APPROVAL;
            case APPROVED -> RUNNING;
            case REJECTED -> REJECTED;
            case PROMOTED -> PROMOTED;
            case ESCALATED -> ESCALATED;
            case FAILED -> FAILED;
            case COMPLETED -> completedAs(decision);
            default -> this;
        };
    }

    private AgentRunStatus completedAs(@Nullable String decision) {
        if (decision == null) {
            return this;
        }
        return switch (decision) {
            case "noise" -> NOISE;
            case "data_incident" -> ESCALATED;
            case "keep_champion" -> KEPT_CHAMPION;
            case "promote" -> PROMOTED;
            default -> this;
        };
    }
}
