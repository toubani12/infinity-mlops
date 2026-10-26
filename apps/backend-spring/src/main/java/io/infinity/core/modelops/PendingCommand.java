package io.infinity.core.modelops;

import jakarta.persistence.Column;
import jakarta.persistence.Embeddable;
import java.time.Instant;
import java.util.UUID;

/** The decision sent on agent.commands, kept until the agent confirms it with approved or rejected. */
@Embeddable
public record PendingCommand(
        @Column(name = "command_id") UUID commandId,
        @Column(name = "command_action") String action,
        @Column(name = "command_actor") String actor,
        @Column(name = "command_reason") String reason,
        @Column(name = "command_sent_at") Instant sentAt) {
}
