package io.infinity.core.modelops;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import io.infinity.core.config.NotFoundException;
import java.time.Instant;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.jdbc.AutoConfigureTestDatabase;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;
import org.springframework.context.annotation.Import;
import org.springframework.test.context.ActiveProfiles;

@DataJpaTest
@ActiveProfiles("test")
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
@Import(ModelOpsService.class)
class ModelOpsServiceTest {

    static final Instant T0 = Instant.parse("2026-10-26T10:00:00Z");

    @Autowired
    private ModelOpsService service;

    @Test
    void storesDriftReportsOnceAndListsNewestFirst() {
        DriftReport older = report(UUID.randomUUID(), T0.minusSeconds(3600), List.of("v4"), null);
        DriftReport newer = report(UUID.randomUUID(), T0, List.of("v10", "amount"), 0.71);

        assertThat(service.recordDrift(older)).isTrue();
        assertThat(service.recordDrift(newer)).isTrue();
        assertThat(service.recordDrift(report(newer.getId(), T0, List.of(), null))).isFalse();

        List<DriftReport> reports = service.driftReports(0, 10).getContent();
        assertThat(reports).extracting(DriftReport::getId).containsExactly(newer.getId(), older.getId());
        DriftReport stored = service.driftReport(newer.getId());
        assertThat(stored.getDriftedFeatures()).containsExactly("v10", "amount");
        assertThat(stored.getMissingFeatures()).isEmpty();
        assertThat(stored.getQuality().prAuc()).isEqualTo(0.71);
        assertThat(stored.getWindow().start()).isEqualTo(T0.minusSeconds(3600));
    }

    @Test
    void failsOnUnknownReport() {
        assertThatThrownBy(() -> service.driftReport(UUID.randomUUID())).isInstanceOf(NotFoundException.class);
    }

    @Test
    void storesModelVersionEventsOnce() {
        ModelVersionEvent promotion = event(T0.minusSeconds(60), "4", "3", "promotion");
        ModelVersionEvent rollback = event(T0, "3", "4", "rollback");

        service.recordModelVersion(promotion);
        service.recordModelVersion(rollback);
        assertThat(service.recordModelVersion(promotion)).isFalse();

        assertThat(service.modelVersions(0, 10).getContent())
                .extracting(ModelVersionEvent::getVersion).containsExactly("3", "4");
    }

    static DriftReport report(UUID id, Instant detectedAt, List<String> drifted, Double prAuc) {
        return new DriftReport(id, detectedAt,
                new DriftReport.Window(detectedAt.minusSeconds(3600), detectedAt, 12000), 0.36, drifted, List.of(),
                0.0, new DriftReport.Quality(prAuc, 0.84, 0.52, 3100), "3", "s3://drift-reports/x.html", T0);
    }

    static ModelVersionEvent event(Instant at, String version, String previous, String reason) {
        return new ModelVersionEvent(UUID.randomUUID(), at, UUID.randomUUID(), "fraud-xgb", version, "champion",
                previous, reason, T0);
    }
}
