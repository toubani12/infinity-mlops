package io.infinity.core.modelops;

import java.time.Instant;
import java.util.Locale;
import java.util.UUID;
import org.springframework.lang.Nullable;

public record AgentCommand(
        UUID runId, UUID commandId, Instant timestamp, Action action, String actor, @Nullable String reason) {

    public enum Action {
        APPROVE,
        REJECT;

        public String wireName() {
            return name().toLowerCase(Locale.ROOT);
        }
    }
}
