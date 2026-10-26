package io.infinity.core.messaging;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.infinity.core.transaction.Transaction;
import io.infinity.core.transaction.TransactionRepository;
import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.MeterRegistry;
import java.time.Clock;
import java.time.Instant;
import java.util.List;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.data.domain.Limit;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

/**
 * Publishes committed transactions that have no {@code published_at} yet. Delivery is at least once: a crash
 * between the broker ack and the commit republishes the row, which consumers absorb by keying on transaction_id.
 */
@Component
public class TransactionRawRelay {

    private static final Logger log = LoggerFactory.getLogger(TransactionRawRelay.class);

    private final TransactionRepository repository;
    private final KafkaTemplate<String, String> kafka;
    private final ObjectMapper json;
    private final Clock clock;
    private final OutboxProperties properties;
    private final Counter published;
    private final Counter failed;

    public TransactionRawRelay(
            TransactionRepository repository,
            KafkaTemplate<String, String> kafka,
            ObjectMapper json,
            Clock clock,
            OutboxProperties properties,
            MeterRegistry meters) {
        this.repository = repository;
        this.kafka = kafka;
        this.json = json;
        this.clock = clock;
        this.properties = properties;
        this.published = meters.counter("infinity.outbox.published", "topic", Topics.TRANSACTION_RAW);
        this.failed = meters.counter("infinity.outbox.failed", "topic", Topics.TRANSACTION_RAW);
    }

    @Transactional
    public int publishPending() {
        List<Transaction> pending =
                repository.findByPublishedAtIsNullOrderByReceivedAtAsc(Limit.of(properties.batchSize()));
        if (pending.isEmpty()) {
            return 0;
        }
        List<CompletableFuture<?>> sends = pending.stream().<CompletableFuture<?>>map(this::send).toList();
        long deadline = System.nanoTime() + properties.sendTimeout().toNanos();
        Instant now = clock.instant();
        int ok = 0;
        Throwable lastError = null;
        for (int i = 0; i < pending.size(); i++) {
            try {
                sends.get(i).get(Math.max(0, deadline - System.nanoTime()), TimeUnit.NANOSECONDS);
                pending.get(i).markPublished(now);
                ok++;
            } catch (ExecutionException e) {
                lastError = e.getCause();
            } catch (TimeoutException e) {
                lastError = e;
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                lastError = e;
                break;
            }
        }
        int failures = pending.size() - ok;
        published.increment(ok);
        if (failures > 0) {
            failed.increment(failures);
            log.warn("{} of {} transaction.raw sends failed, rows stay pending for the next run",
                    failures, pending.size(), lastError);
        }
        return ok;
    }

    private CompletableFuture<?> send(Transaction transaction) {
        try {
            String value = json.writeValueAsString(TransactionRawMessage.payload(transaction));
            return kafka.send(Topics.TRANSACTION_RAW, transaction.getId().toString(), value);
        } catch (JsonProcessingException | RuntimeException e) {
            return CompletableFuture.failedFuture(e);
        }
    }
}
