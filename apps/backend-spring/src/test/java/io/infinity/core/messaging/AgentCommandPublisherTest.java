package io.infinity.core.messaging;

import static org.assertj.core.api.Assertions.assertThat;

import com.fasterxml.jackson.databind.ObjectMapper;
import io.infinity.core.modelops.AgentCommand;
import io.infinity.core.modelops.AgentCommandSender;
import java.time.Duration;
import java.time.Instant;
import java.util.Map;
import java.util.UUID;
import org.apache.kafka.clients.consumer.Consumer;
import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.apache.kafka.common.serialization.StringDeserializer;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.kafka.core.DefaultKafkaConsumerFactory;
import org.springframework.kafka.test.EmbeddedKafkaBroker;
import org.springframework.kafka.test.context.EmbeddedKafka;
import org.springframework.kafka.test.utils.KafkaTestUtils;
import org.springframework.test.context.ActiveProfiles;

@SpringBootTest(properties = "spring.kafka.bootstrap-servers=${spring.embedded.kafka.brokers}")
@ActiveProfiles("test")
@EmbeddedKafka(partitions = 1, topics = Topics.AGENT_COMMANDS)
class AgentCommandPublisherTest {

    private static final Instant NOW = Instant.parse("2026-10-26T10:11:40.123Z");

    @Autowired
    private AgentCommandSender sender;

    @Autowired
    private EmbeddedKafkaBroker broker;

    @Autowired
    private ObjectMapper json;

    @Test
    void publishesCommandsKeyedByRunThatMatchTheContract() {
        UUID runId = UUID.randomUUID();
        sender.send(new AgentCommand(runId, UUID.randomUUID(), NOW, AgentCommand.Action.APPROVE, "badr", null));

        Map<String, Object> props = KafkaTestUtils.consumerProps("command-check", "false", broker);
        props.put("auto.offset.reset", "earliest");
        try (Consumer<String, String> consumer = new DefaultKafkaConsumerFactory<>(
                props, new StringDeserializer(), new StringDeserializer()).createConsumer()) {
            broker.consumeFromAnEmbeddedTopic(consumer, Topics.AGENT_COMMANDS);
            ConsumerRecord<String, String> record =
                    KafkaTestUtils.getSingleRecord(consumer, Topics.AGENT_COMMANDS, Duration.ofSeconds(10));

            assertThat(record.key()).isEqualTo(runId.toString());
            assertThat(ContractSchemas.validate("agent.commands", record.value())).isEmpty();
            assertThat(ContractSchemas.readTree(record.value()).get("actor").asText()).isEqualTo("badr");
        }
    }

    @Test
    void writesRejectionsWithTheirReason() throws Exception {
        AgentCommand reject = new AgentCommand(
                UUID.randomUUID(), UUID.randomUUID(), NOW, AgentCommand.Action.REJECT, "badr", "too slow");
        String payload = json.writeValueAsString(AgentCommandPublisher.payload(reject));

        assertThat(ContractSchemas.validate("agent.commands", payload)).isEmpty();
        assertThat(ContractSchemas.readTree(payload).get("action").asText()).isEqualTo("reject");

        String withoutReason = json.writeValueAsString(AgentCommandPublisher.payload(new AgentCommand(
                reject.runId(), reject.commandId(), NOW, AgentCommand.Action.REJECT, "badr", null)));
        assertThat(ContractSchemas.validate("agent.commands", withoutReason)).isNotEmpty();
    }
}
