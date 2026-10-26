package io.infinity.core.messaging;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

import com.fasterxml.jackson.databind.ObjectMapper;
import io.infinity.core.transaction.Transaction;
import io.infinity.core.transaction.TransactionFixtures;
import io.infinity.core.transaction.TransactionRepository;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import org.apache.kafka.common.errors.TimeoutException;
import org.junit.jupiter.api.Test;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.support.SendResult;

class TransactionRawRelayTest {

    private static final Instant NOW = Instant.parse("2026-10-26T10:00:00Z");

    private final TransactionRepository repository = mock(TransactionRepository.class);
    @SuppressWarnings("unchecked")
    private final KafkaTemplate<String, String> kafka = mock(KafkaTemplate.class);
    private final SimpleMeterRegistry meters = new SimpleMeterRegistry();
    private final TransactionRawRelay relay = new TransactionRawRelay(repository, kafka, new ObjectMapper(),
            Clock.fixed(NOW, ZoneOffset.UTC), new OutboxProperties(true, 100, Duration.ofSeconds(1)), meters);

    @Test
    void marksAcknowledgedRowsAndKeepsFailedOnesPending() {
        Transaction ok = TransactionFixtures.transaction(UUID.randomUUID(), NOW.minusSeconds(2));
        Transaction ko = TransactionFixtures.transaction(UUID.randomUUID(), NOW.minusSeconds(1));
        when(repository.findByPublishedAtIsNullOrderByReceivedAtAsc(any())).thenReturn(List.of(ok, ko));
        when(kafka.send(eq(Topics.TRANSACTION_RAW), eq(ok.getId().toString()), anyString()))
                .thenReturn(CompletableFuture.completedFuture(new SendResult<>(null, null)));
        when(kafka.send(eq(Topics.TRANSACTION_RAW), eq(ko.getId().toString()), anyString()))
                .thenReturn(CompletableFuture.failedFuture(new TimeoutException("broker down")));

        int published = relay.publishPending();

        assertThat(published).isEqualTo(1);
        assertThat(ok.getPublishedAt()).isEqualTo(NOW);
        assertThat(ko.getPublishedAt()).isNull();
        assertThat(meters.counter("infinity.outbox.failed", "topic", Topics.TRANSACTION_RAW).count()).isEqualTo(1);
    }

    @Test
    void treatsSynchronousSendErrorsAsFailures() {
        Transaction pending = TransactionFixtures.transaction(UUID.randomUUID(), NOW);
        when(repository.findByPublishedAtIsNullOrderByReceivedAtAsc(any())).thenReturn(List.of(pending));
        when(kafka.send(anyString(), anyString(), anyString())).thenThrow(new IllegalStateException("producer closed"));

        assertThat(relay.publishPending()).isZero();
        assertThat(pending.getPublishedAt()).isNull();
    }

    @Test
    void timesOutSendsThatNeverComplete() {
        Transaction pending = TransactionFixtures.transaction(UUID.randomUUID(), NOW);
        when(repository.findByPublishedAtIsNullOrderByReceivedAtAsc(any())).thenReturn(List.of(pending));
        when(kafka.send(anyString(), anyString(), anyString())).thenReturn(new CompletableFuture<>());

        assertThat(relay.publishPending()).isZero();
        assertThat(pending.getPublishedAt()).isNull();
    }

    @Test
    void doesNothingWithoutPendingRows() {
        when(repository.findByPublishedAtIsNullOrderByReceivedAtAsc(any())).thenReturn(List.of());

        assertThat(relay.publishPending()).isZero();
        verifyNoInteractions(kafka);
    }
}
