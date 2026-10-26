package io.infinity.core.modelops;

public interface AgentCommandSender {

    /** Returns once the broker acknowledged the command, throws {@link CommandNotSentException} otherwise. */
    void send(AgentCommand command);
}
