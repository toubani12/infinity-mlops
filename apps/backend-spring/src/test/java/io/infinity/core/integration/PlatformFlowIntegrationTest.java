package io.infinity.core.integration;

import static org.assertj.core.api.Assertions.assertThat;
import static org.awaitility.Awaitility.await;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.infinity.core.alert.AlertRepository;
import io.infinity.core.messaging.ContractSchemas;
import io.infinity.core.messaging.Topics;
import io.infinity.core.modelops.AgentRunStatus;
import io.infinity.core.security.Role;
import io.infinity.core.security.TokenService;
import io.infinity.core.transaction.TransactionFixtures;
import io.infinity.core.transaction.TransactionRepository;
import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.function.Predicate;
import java.util.stream.Stream;
import org.apache.kafka.clients.admin.NewTopic;
import org.apache.kafka.clients.consumer.Consumer;
import org.apache.kafka.clients.consumer.ConsumerConfig;
import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.apache.kafka.common.serialization.StringDeserializer;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.autoconfigure.kafka.KafkaConnectionDetails;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Import;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.kafka.config.TopicBuilder;
import org.springframework.kafka.core.DefaultKafkaConsumerFactory;
import org.springframework.kafka.core.KafkaAdmin;
import org.springframework.kafka.core.KafkaTemplate;
import org.testcontainers.junit.jupiter.Testcontainers;

/**
 * Runs the backend against real PostgreSQL and Kafka: the Flyway scripts on PostgreSQL, the outbox relay, the
 * consumers in group backend-spring and the agent command publisher. Skipped when no Docker daemon is reachable.
 */
@Tag("integration")
@Testcontainers(disabledWithoutDocker = true)
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT, properties = {
        "infinity.security.jwt-secret=integration-secret-0123456789-0123456789",
        "infinity.outbox.poll-interval-ms=100",
        "infinity.alerts.threshold=0.5"
})
@Import({PlatformContainers.class, PlatformFlowIntegrationTest.KafkaTopics.class})
class PlatformFlowIntegrationTest {

    @TestConfiguration(proxyBeanMethods = false)
    static class KafkaTopics {

        @Bean
        KafkaAdmin.NewTopics platformTopics() {
            return new KafkaAdmin.NewTopics(Stream.of(Topics.TRANSACTION_RAW, Topics.TRANSACTION_SCORED,
                            Topics.DRIFT_DETECTED, Topics.MODEL_PROMOTED, Topics.AGENT_EVENTS, Topics.AGENT_COMMANDS)
                    .map(name -> TopicBuilder.name(name).partitions(1).replicas(1).build())
                    .toArray(NewTopic[]::new));
        }
    }

    @Autowired
    private TestRestTemplate http;

    @Autowired
    private TokenService tokens;

    @Autowired
    private KafkaTemplate<String, String> kafka;

    @Autowired
    private KafkaConnectionDetails kafkaConnection;

    @Autowired
    private TransactionRepository transactions;

    @Autowired
    private AlertRepository alerts;

    @Autowired
    private ObjectMapper json;

    @Test
    void transactionGoesThroughTheOutboxAndItsScoreOpensAnAlert() throws Exception {
        Map<String, Object> body = Map.of("amount", 950.0, "features", TransactionFixtures.features(), "label", 1);
        ResponseEntity<JsonNode> created = http.exchange("/api/transactions", HttpMethod.POST,
                new HttpEntity<>(body, headers(Role.ANALYST)), JsonNode.class);
        assertThat(created.getStatusCode()).isEqualTo(HttpStatus.CREATED);
        String id = created.getBody().get("transactionId").asText();

        ConsumerRecord<String, String> raw = readUntil(Topics.TRANSACTION_RAW, record -> record.key().equals(id));
        assertThat(ContractSchemas.validate("transaction.raw", raw.value())).isEmpty();
        assertThat(json.readTree(raw.value()).get("label").asInt()).isEqualTo(1);
        await().atMost(Duration.ofSeconds(10)).untilAsserted(() ->
                assertThat(transactions.findById(UUID.fromString(id)).orElseThrow().getPublishedAt()).isNotNull());

        String scored = """
                {"transaction_id":"%s","timestamp":"%s","fraud_score":0.93,"is_fraud":true,"threshold":0.5,
                 "model_name":"fraud-xgb","model_version":"3","latency_ms":3.1}
                """.formatted(id, Instant.now());
        assertThat(ContractSchemas.validate("transaction.scored", scored)).isEmpty();
        kafka.send(Topics.TRANSACTION_SCORED, id, scored).get();

        await().atMost(Duration.ofSeconds(30)).untilAsserted(() ->
                assertThat(alerts.existsByTransactionId(UUID.fromString(id))).isTrue());
        JsonNode alerts = http.exchange("/api/alerts?status=OPEN", HttpMethod.GET,
                new HttpEntity<>(headers(Role.ANALYST)), JsonNode.class).getBody();
        assertThat(alerts.get("content").findValuesAsText("transactionId")).contains(id);
    }

    @Test
    void agentEventsDriveTheRunAndApprovalPublishesACommand() throws Exception {
        String runId = UUID.randomUUID().toString();
        for (String event : approvalPath(runId)) {
            assertThat(ContractSchemas.validate("agent.events", event)).isEmpty();
            kafka.send(Topics.AGENT_EVENTS, runId, event).get();
        }

        await().atMost(Duration.ofSeconds(30)).untilAsserted(() -> {
            JsonNode detail = getRun(runId);
            assertThat(detail.at("/run/status").asText()).isEqualTo(AgentRunStatus.AWAITING_APPROVAL.name());
            assertThat(detail.get("events")).hasSize(4);
        });
        assertThat(getRun(runId).at("/challenger/prAuc").asDouble()).isEqualTo(0.83);

        ResponseEntity<String> forbidden = http.exchange("/api/agent/runs/" + runId + "/approve", HttpMethod.POST,
                new HttpEntity<>(headers(Role.ANALYST)), String.class);
        assertThat(forbidden.getStatusCode()).isEqualTo(HttpStatus.FORBIDDEN);
        ResponseEntity<JsonNode> approved = http.exchange("/api/agent/runs/" + runId + "/approve", HttpMethod.POST,
                new HttpEntity<>(headers(Role.ADMIN)), JsonNode.class);
        assertThat(approved.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(approved.getBody().at("/pendingCommand/actor").asText()).isEqualTo("integration-admin");

        ConsumerRecord<String, String> command = readUntil(Topics.AGENT_COMMANDS, r -> r.key().equals(runId));
        assertThat(ContractSchemas.validate("agent.commands", command.value())).isEmpty();
        assertThat(json.readTree(command.value()).get("action").asText()).isEqualTo("approve");
        assertThat(http.exchange("/api/agent/runs/" + runId + "/reject", HttpMethod.POST,
                new HttpEntity<>(Map.of("reason", "changed my mind"), headers(Role.ADMIN)), String.class)
                .getStatusCode()).isEqualTo(HttpStatus.CONFLICT);

        String confirmed = event(runId, "approved", "promote", false,
                "{\"actor\":\"integration-admin\",\"reason\":null}");
        kafka.send(Topics.AGENT_EVENTS, runId, confirmed).get();
        await().atMost(Duration.ofSeconds(30)).untilAsserted(() -> {
            JsonNode run = getRun(runId).get("run");
            assertThat(run.get("decidedBy").asText()).isEqualTo("integration-admin");
            assertThat(run.get("pendingCommand").isNull()).isTrue();
        });
    }

    private List<String> approvalPath(String runId) {
        String metrics = """
                "champion":{"version":"3","pr_auc":0.71,"recall_at_p90":0.52,"p95_latency_ms":6.1},
                "challenger":{"version":"4","pr_auc":0.83,"recall_at_p90":0.68,"p95_latency_ms":6.4}""";
        return List.of(
                event(runId, "received", null, false, "{\"report_id\":\"" + UUID.randomUUID() + "\"}"),
                event(runId, "qualified", "real_drift", false, "{\"reasons\":[\"drift share 0.36 > 0.30\"]}"),
                event(runId, "evaluated", "promote", false,
                        "{" + metrics + ",\"gate\":{\"passed\":true,\"reasons\":[\"pr_auc 0.830 > champion 0.710\"]}}"),
                event(runId, "approval_requested", "promote", true, "{" + metrics + "}"));
    }

    private static String event(String runId, String step, String decision, boolean approval, String payload) {
        return """
                {"run_id":"%s","event_id":"%s","timestamp":"%s","step":"%s","decision":%s,
                 "requires_approval":%s,"message":"%s step","payload":%s}
                """.formatted(runId, UUID.randomUUID(), Instant.now(), step,
                decision == null ? "null" : "\"" + decision + "\"", approval, step, payload);
    }

    private JsonNode getRun(String runId) {
        return http.exchange("/api/agent/runs/" + runId, HttpMethod.GET, new HttpEntity<>(headers(Role.ANALYST)),
                JsonNode.class).getBody();
    }

    private HttpHeaders headers(Role role) {
        HttpHeaders headers = new HttpHeaders();
        headers.setBearerAuth(tokens.issue(role == Role.ADMIN ? "integration-admin" : "integration-analyst", role)
                .token());
        headers.setContentType(MediaType.APPLICATION_JSON);
        return headers;
    }

    private ConsumerRecord<String, String> readUntil(String topic, Predicate<ConsumerRecord<String, String>> match) {
        Map<String, Object> props = Map.of(
                ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG, String.join(",", kafkaConnection.getBootstrapServers()),
                ConsumerConfig.GROUP_ID_CONFIG, "it-" + UUID.randomUUID(),
                ConsumerConfig.AUTO_OFFSET_RESET_CONFIG, "earliest");
        try (Consumer<String, String> consumer = new DefaultKafkaConsumerFactory<>(
                props, new StringDeserializer(), new StringDeserializer()).createConsumer()) {
            consumer.subscribe(List.of(topic));
            List<ConsumerRecord<String, String>> seen = new ArrayList<>();
            long deadline = System.nanoTime() + Duration.ofSeconds(30).toNanos();
            while (System.nanoTime() < deadline) {
                for (ConsumerRecord<String, String> record : consumer.poll(Duration.ofSeconds(1))) {
                    if (match.test(record)) {
                        return record;
                    }
                    seen.add(record);
                }
            }
            throw new AssertionError("No matching record on " + topic + ", saw " + seen.size());
        }
    }
}
