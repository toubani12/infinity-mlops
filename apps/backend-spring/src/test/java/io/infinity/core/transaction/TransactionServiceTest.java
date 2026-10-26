package io.infinity.core.transaction;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import io.infinity.core.config.ConflictException;
import io.infinity.core.config.NotFoundException;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.jdbc.AutoConfigureTestDatabase;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Import;
import org.springframework.data.domain.Page;
import org.springframework.test.context.ActiveProfiles;

@DataJpaTest
@ActiveProfiles("test")
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
@Import({TransactionService.class, TransactionServiceTest.FixedClock.class})
class TransactionServiceTest {

    static final Instant NOW = Instant.parse("2026-10-26T10:00:00Z");

    @TestConfiguration
    static class FixedClock {
        @Bean
        Clock clock() {
            return Clock.fixed(NOW, ZoneOffset.UTC);
        }
    }

    @Autowired
    private TransactionService service;

    @Autowired
    private TransactionRepository repository;

    @Test
    void generatesIdAndTimestampWhenAbsent() {
        Transaction created = service.create(TransactionFixtures.request(null, 42.5));

        Transaction stored = repository.findById(created.getId()).orElseThrow();
        assertThat(stored.getOccurredAt()).isEqualTo(NOW);
        assertThat(stored.getReceivedAt()).isEqualTo(NOW);
        assertThat(stored.getAmount()).isEqualTo(42.5);
        assertThat(stored.getFeatures()).containsExactly(Features.toArray(TransactionFixtures.features()));
        assertThat(stored.getFraudScore()).isNull();
    }

    @Test
    void keepsClientIdTimestampAndLabel() {
        UUID id = UUID.randomUUID();
        Instant at = Instant.parse("2026-10-25T08:00:00Z");

        service.create(new CreateTransactionRequest(id, at, 3.0, TransactionFixtures.features(), 1));

        Transaction stored = service.get(id);
        assertThat(stored.getOccurredAt()).isEqualTo(at);
        assertThat(stored.getLabel()).isEqualTo(1);
    }

    @Test
    void rejectsDuplicateId() {
        UUID id = UUID.randomUUID();
        service.create(TransactionFixtures.request(id, 1.0));

        assertThatThrownBy(() -> service.create(TransactionFixtures.request(id, 2.0)))
                .isInstanceOf(ConflictException.class);
    }

    @Test
    void failsOnUnknownId() {
        assertThatThrownBy(() -> service.get(UUID.randomUUID())).isInstanceOf(NotFoundException.class);
    }

    @Test
    void filtersFraudulentTransactions() {
        Transaction fraud = TransactionFixtures.transaction(UUID.randomUUID(), NOW.minusSeconds(5));
        fraud.applyScore(0.93, true, "3", NOW);
        Transaction legit = TransactionFixtures.transaction(UUID.randomUUID(), NOW.minusSeconds(3));
        legit.applyScore(0.01, false, "3", NOW);
        repository.saveAll(List.of(fraud, legit));

        Page<Transaction> fraudOnly = service.list(true, 0, 10);
        Page<Transaction> all = service.list(false, 0, 10);

        assertThat(fraudOnly.getContent()).extracting(Transaction::getId).containsExactly(fraud.getId());
        assertThat(all.getContent()).extracting(Transaction::getId).containsExactly(legit.getId(), fraud.getId());
    }
}
