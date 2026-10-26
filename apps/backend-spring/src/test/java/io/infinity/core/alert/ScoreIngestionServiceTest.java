package io.infinity.core.alert;

import static org.assertj.core.api.Assertions.assertThat;

import io.infinity.core.transaction.Transaction;
import io.infinity.core.transaction.TransactionFixtures;
import io.infinity.core.transaction.TransactionRepository;
import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.boot.test.autoconfigure.jdbc.AutoConfigureTestDatabase;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Import;
import org.springframework.test.context.ActiveProfiles;

@DataJpaTest(properties = "infinity.alerts.threshold=0.8")
@ActiveProfiles("test")
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
@Import({ScoreIngestionService.class, ScoreIngestionServiceTest.Support.class})
class ScoreIngestionServiceTest {

    static final Instant NOW = Instant.parse("2026-10-26T10:00:00Z");

    @TestConfiguration
    @EnableConfigurationProperties(AlertProperties.class)
    static class Support {
        @Bean
        Clock clock() {
            return Clock.fixed(NOW, ZoneOffset.UTC);
        }

        @Bean
        MeterRegistry meterRegistry() {
            return new SimpleMeterRegistry();
        }
    }

    @Autowired
    private ScoreIngestionService service;

    @Autowired
    private TransactionRepository transactions;

    @Autowired
    private AlertRepository alerts;

    @Test
    void storesScoreWithoutAlertBelowThreshold() {
        UUID id = storedTransaction();

        Optional<ScoreIngestionService.Outcome> outcome = service.apply(update(id, 0.42));

        assertThat(outcome).isPresent();
        assertThat(outcome.get().createdAlert()).isNull();
        Transaction scored = transactions.findById(id).orElseThrow();
        assertThat(scored.getFraudScore()).isEqualTo(0.42);
        assertThat(scored.getFraud()).isFalse();
        assertThat(scored.getModelVersion()).isEqualTo("3");
        assertThat(scored.getScoredAt()).isEqualTo(NOW.minusMillis(41));
        assertThat(alerts.count()).isZero();
    }

    @Test
    void opensAlertAtThreshold() {
        UUID id = storedTransaction();

        Alert alert = service.apply(update(id, 0.8)).orElseThrow().createdAlert();

        assertThat(alert).isNotNull();
        assertThat(alert.getStatus()).isEqualTo(AlertStatus.OPEN);
        assertThat(alert.getCreatedAt()).isEqualTo(NOW);
        assertThat(alerts.existsByTransactionId(id)).isTrue();
    }

    @Test
    void replayedScoreKeepsASingleAlert() {
        UUID id = storedTransaction();

        service.apply(update(id, 0.97));
        Optional<ScoreIngestionService.Outcome> replay = service.apply(update(id, 0.97));

        assertThat(replay.orElseThrow().createdAlert()).isNull();
        assertThat(alerts.count()).isEqualTo(1);
    }

    @Test
    void ignoresScoresForUnknownTransactions() {
        assertThat(service.apply(update(UUID.randomUUID(), 0.99))).isEmpty();
        assertThat(alerts.count()).isZero();
    }

    private UUID storedTransaction() {
        UUID id = UUID.randomUUID();
        transactions.save(TransactionFixtures.transaction(id, NOW.minusSeconds(1)));
        return id;
    }

    private static ScoreUpdate update(UUID id, double score) {
        return new ScoreUpdate(id, score, score >= 0.5, "3", NOW.minusMillis(41));
    }
}
