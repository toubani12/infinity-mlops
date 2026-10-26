package io.infinity.core.alert;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import io.infinity.core.config.ConflictException;
import io.infinity.core.config.NotFoundException;
import io.infinity.core.transaction.TransactionFixtures;
import io.infinity.core.transaction.TransactionRepository;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.jdbc.AutoConfigureTestDatabase;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Import;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.test.context.ActiveProfiles;

@DataJpaTest
@ActiveProfiles("test")
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
@Import({AlertService.class, AlertServiceTest.FixedClock.class})
class AlertServiceTest {

    static final Instant NOW = Instant.parse("2026-10-26T10:00:00Z");

    @TestConfiguration
    static class FixedClock {
        @Bean
        Clock clock() {
            return Clock.fixed(NOW, ZoneOffset.UTC);
        }
    }

    @Autowired
    private AlertService service;

    @Autowired
    private AlertRepository alerts;

    @Autowired
    private TransactionRepository transactions;

    private Alert open;
    private Alert acknowledged;

    @BeforeEach
    void seed() {
        open = alerts.save(new Alert(UUID.randomUUID(), newTransaction(), 0.91, NOW.minusSeconds(30)));
        acknowledged = new Alert(UUID.randomUUID(), newTransaction(), 0.75, NOW.minusSeconds(10));
        acknowledged.moveTo(AlertStatus.ACKNOWLEDGED, NOW.minusSeconds(5));
        alerts.save(acknowledged);
    }

    @Test
    void listsByStatusNewestFirst() {
        assertThat(service.list(null, 0, 10).getContent())
                .extracting(Alert::getId).containsExactly(acknowledged.getId(), open.getId());
        assertThat(service.list(AlertStatus.OPEN, 0, 10).getContent())
                .extracting(Alert::getId).containsExactly(open.getId());
    }

    @Test
    void acknowledgesOpenAlert() {
        Alert updated = service.updateStatus(open.getId(), AlertStatus.ACKNOWLEDGED);

        assertThat(updated.getStatus()).isEqualTo(AlertStatus.ACKNOWLEDGED);
        assertThat(updated.getUpdatedAt()).isEqualTo(NOW);
    }

    @Test
    void refusesToReopen() {
        assertThatThrownBy(() -> service.updateStatus(acknowledged.getId(), AlertStatus.OPEN))
                .isInstanceOf(ConflictException.class);
    }

    @Test
    void failsOnUnknownAlert() {
        assertThatThrownBy(() -> service.updateStatus(UUID.randomUUID(), AlertStatus.CLOSED))
                .isInstanceOf(NotFoundException.class);
    }

    @Test
    void allowsOneAlertPerTransaction() {
        Alert duplicate = new Alert(UUID.randomUUID(), open.getTransactionId(), 0.99, NOW);

        assertThatThrownBy(() -> alerts.saveAndFlush(duplicate)).isInstanceOf(DataIntegrityViolationException.class);
    }

    private UUID newTransaction() {
        UUID id = UUID.randomUUID();
        transactions.save(TransactionFixtures.transaction(id, NOW.minusSeconds(60)));
        return id;
    }
}
