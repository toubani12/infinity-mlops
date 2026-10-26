package io.infinity.core.alert;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.time.Instant;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class AlertStatusTest {

    private static final Instant T0 = Instant.parse("2026-10-26T10:00:00Z");

    @Test
    void movesForwardOnly() {
        assertThat(AlertStatus.OPEN.canMoveTo(AlertStatus.ACKNOWLEDGED)).isTrue();
        assertThat(AlertStatus.OPEN.canMoveTo(AlertStatus.CLOSED)).isTrue();
        assertThat(AlertStatus.ACKNOWLEDGED.canMoveTo(AlertStatus.CLOSED)).isTrue();
        assertThat(AlertStatus.ACKNOWLEDGED.canMoveTo(AlertStatus.OPEN)).isFalse();
        assertThat(AlertStatus.CLOSED.canMoveTo(AlertStatus.ACKNOWLEDGED)).isFalse();
    }

    @Test
    void sameStatusKeepsUpdatedAt() {
        Alert alert = new Alert(UUID.randomUUID(), UUID.randomUUID(), 0.9, T0);

        alert.moveTo(AlertStatus.OPEN, T0.plusSeconds(60));
        assertThat(alert.getUpdatedAt()).isEqualTo(T0);

        alert.moveTo(AlertStatus.CLOSED, T0.plusSeconds(120));
        assertThat(alert.getUpdatedAt()).isEqualTo(T0.plusSeconds(120));
        assertThatThrownBy(() -> alert.moveTo(AlertStatus.OPEN, T0)).isInstanceOf(IllegalStateException.class);
    }
}
