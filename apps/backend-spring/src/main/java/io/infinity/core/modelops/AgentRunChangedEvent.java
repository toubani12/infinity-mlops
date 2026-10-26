package io.infinity.core.modelops;

import org.springframework.lang.Nullable;

/** {@code event} is null when the run changed without a new step, e.g. a decision was sent. */
public record AgentRunChangedEvent(AgentRunResponse run, @Nullable AgentRunEventResponse event) {
}
