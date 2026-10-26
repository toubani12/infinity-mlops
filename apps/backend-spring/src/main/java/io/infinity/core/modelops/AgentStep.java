package io.infinity.core.modelops;

import com.fasterxml.jackson.annotation.JsonValue;
import java.util.Arrays;
import java.util.Locale;
import java.util.Optional;

public enum AgentStep {
    RECEIVED,
    QUALIFIED,
    ESCALATED,
    RETRAIN_STARTED,
    RETRAIN_FINISHED,
    EVALUATED,
    APPROVAL_REQUESTED,
    APPROVED,
    REJECTED,
    PROMOTED,
    ROLLED_BACK,
    FAILED,
    COMPLETED;

    @JsonValue
    public String wireName() {
        return name().toLowerCase(Locale.ROOT);
    }

    public static Optional<AgentStep> fromWire(String value) {
        return Arrays.stream(values()).filter(step -> step.wireName().equals(value)).findFirst();
    }
}
