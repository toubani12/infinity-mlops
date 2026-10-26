package io.infinity.core.messaging;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.infinity.core.modelops.AgentCommand;
import io.infinity.core.modelops.AgentCommandSender;
import io.infinity.core.modelops.AgentProperties;
import io.infinity.core.modelops.CommandNotSentException;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Component;

@Component
public class AgentCommandPublisher implements AgentCommandSender {

    private final KafkaTemplate<String, String> kafka;
    private final ObjectMapper json;
    private final AgentProperties properties;

    public AgentCommandPublisher(KafkaTemplate<String, String> kafka, ObjectMapper json, AgentProperties properties) {
        this.kafka = kafka;
        this.json = json;
        this.properties = properties;
    }

    @Override
    public void send(AgentCommand command) {
        try {
            String value = json.writeValueAsString(payload(command));
            kafka.send(Topics.AGENT_COMMANDS, command.runId().toString(), value)
                    .get(properties.commandTimeout().toMillis(), TimeUnit.MILLISECONDS);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new CommandNotSentException(e);
        } catch (JsonProcessingException | ExecutionException | TimeoutException | RuntimeException e) {
            throw new CommandNotSentException(e);
        }
    }

    static Map<String, Object> payload(AgentCommand command) {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("run_id", command.runId().toString());
        payload.put("command_id", command.commandId().toString());
        payload.put("timestamp", command.timestamp().toString());
        payload.put("action", command.action().wireName());
        payload.put("actor", command.actor());
        payload.put("reason", command.reason());
        return payload;
    }
}
