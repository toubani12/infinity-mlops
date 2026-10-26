package io.infinity.core.stream;

import static org.assertj.core.api.Assertions.assertThat;
import static org.awaitility.Awaitility.await;

import io.infinity.core.alert.AlertStatus;
import io.infinity.core.alert.ScoreIngestionService;
import io.infinity.core.alert.ScoreUpdate;
import io.infinity.core.modelops.AgentRunFixtures;
import io.infinity.core.modelops.AgentRunService;
import io.infinity.core.modelops.AgentStep;
import io.infinity.core.security.Role;
import io.infinity.core.security.TokenService;
import io.infinity.core.transaction.Transaction;
import io.infinity.core.transaction.TransactionFixtures;
import io.infinity.core.transaction.TransactionService;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.BlockingQueue;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.TimeUnit;
import java.util.stream.Stream;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.test.context.ActiveProfiles;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@ActiveProfiles("test")
class StreamIntegrationTest {

    @LocalServerPort
    private int port;

    @Autowired
    private TokenService tokens;

    @Autowired
    private TransactionService transactions;

    @Autowired
    private ScoreIngestionService scores;

    @Autowired
    private AgentRunService agentRuns;

    @Autowired
    private SseBroadcaster broadcaster;

    private final HttpClient http = HttpClient.newHttpClient();
    private final List<Stream<String>> open = new ArrayList<>();

    @AfterEach
    void closeStreams() {
        open.forEach(Stream::close);
    }

    @Test
    void refusesAnonymousSubscribers() throws Exception {
        HttpResponse<Void> response = http.send(
                HttpRequest.newBuilder(uri("/api/stream/alerts", null)).build(), HttpResponse.BodyHandlers.discarding());

        assertThat(response.statusCode()).isEqualTo(401);
    }

    @Test
    void streamsScoredTransactionsAndAlertsAfterCommit() throws Exception {
        String token = tokens.issue("ana", Role.ANALYST).token();
        BlockingQueue<String> transactionLines = subscribe("/api/stream/transactions", token);
        BlockingQueue<String> alertLines = subscribe("/api/stream/alerts", token);
        await().atMost(Duration.ofSeconds(5)).until(() ->
                broadcaster.subscriberCount(StreamChannel.TRANSACTIONS) == 1
                        && broadcaster.subscriberCount(StreamChannel.ALERTS) == 1);

        Transaction created = transactions.create(TransactionFixtures.request(null, 2500.0));
        scores.apply(new ScoreUpdate(created.getId(), 0.91, true, "4", Instant.parse("2026-10-26T10:00:00Z")));

        List<String> transactionEvent = nextEvent(transactionLines);
        assertThat(transactionEvent).contains("event:transaction", "id:" + created.getId());
        assertThat(dataOf(transactionEvent)).contains("\"fraudScore\":0.91", "\"isFraud\":true", "\"modelVersion\":\"4\"");

        List<String> alertEvent = nextEvent(alertLines);
        assertThat(alertEvent).contains("event:alert");
        assertThat(dataOf(alertEvent))
                .contains("\"transactionId\":\"" + created.getId() + "\"", "\"status\":\"" + AlertStatus.OPEN + "\"");
    }

    @Test
    void streamsAgentStepsWithTheRunStatus() throws Exception {
        BlockingQueue<String> lines = subscribe("/api/stream/agent", tokens.issue("ana", Role.ANALYST).token());
        await().atMost(Duration.ofSeconds(5)).until(() -> broadcaster.subscriberCount(StreamChannel.AGENT) == 1);

        UUID runId = UUID.randomUUID();
        agentRuns.record(AgentRunFixtures.step(runId, 0, AgentStep.RECEIVED, null, "{\"drift_share\":0.36}"));

        List<String> event = nextEvent(lines);
        assertThat(event).contains("event:agent");
        assertThat(dataOf(event)).contains("\"runId\":\"" + runId + "\"", "\"status\":\"RUNNING\"",
                "\"step\":\"received\"", "\"payload\":{\"drift_share\":0.36}");
    }

    private BlockingQueue<String> subscribe(String path, String token) throws Exception {
        HttpResponse<Stream<String>> response = http.send(
                HttpRequest.newBuilder(uri(path, token)).header("Accept", "text/event-stream").build(),
                HttpResponse.BodyHandlers.ofLines());
        assertThat(response.statusCode()).isEqualTo(200);
        assertThat(response.headers().firstValue("Content-Type")).hasValueSatisfying(
                type -> assertThat(type).startsWith("text/event-stream"));
        BlockingQueue<String> lines = new LinkedBlockingQueue<>();
        Stream<String> body = response.body();
        open.add(body);
        Thread.ofVirtual().start(() -> body.forEach(lines::add));
        return lines;
    }

    private static List<String> nextEvent(BlockingQueue<String> lines) throws InterruptedException {
        List<String> event = new ArrayList<>();
        long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(10);
        while (System.nanoTime() < deadline) {
            String line = lines.poll(200, TimeUnit.MILLISECONDS);
            if (line == null) {
                continue;
            }
            if (line.isEmpty()) {
                if (event.stream().anyMatch(l -> l.startsWith("event:"))) {
                    return event;
                }
                event.clear();
            } else {
                event.add(line);
            }
        }
        throw new AssertionError("No event received, partial: " + event);
    }

    private static String dataOf(List<String> event) {
        return event.stream().filter(l -> l.startsWith("data:")).map(l -> l.substring(5)).findFirst().orElse("");
    }

    private URI uri(String path, String token) {
        return URI.create("http://localhost:" + port + path + (token == null ? "" : "?access_token=" + token));
    }
}
