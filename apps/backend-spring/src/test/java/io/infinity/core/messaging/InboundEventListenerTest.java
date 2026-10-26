package io.infinity.core.messaging;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.json.JsonMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import io.infinity.core.alert.ScoreIngestionService;
import io.infinity.core.alert.ScoreUpdate;
import io.infinity.core.modelops.DriftReport;
import io.infinity.core.modelops.ModelOpsService;
import io.infinity.core.modelops.ModelVersionEvent;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

class InboundEventListenerTest {

    private final ObjectMapper json = JsonMapper.builder().findAndAddModules().build();
    private final ScoreIngestionService scores = mock(ScoreIngestionService.class);
    private final ModelOpsService modelOps = mock(ModelOpsService.class);
    private final Instant now = Instant.parse("2026-10-26T10:00:05Z");
    private final InboundEventListener listener =
            new InboundEventListener(json, scores, modelOps, Clock.fixed(now, ZoneOffset.UTC));

    @Test
    void mapsTheContractExampleToAScoreUpdate() {
        listener.onTransactionScored(ContractSchemas.example("transaction.scored"));

        ArgumentCaptor<ScoreUpdate> captor = ArgumentCaptor.forClass(ScoreUpdate.class);
        verify(scores).apply(captor.capture());
        ScoreUpdate update = captor.getValue();
        assertThat(update.transactionId()).isEqualTo(UUID.fromString("7f8d4c2e-1b3a-4e5f-9a6b-0c1d2e3f4a5b"));
        assertThat(update.fraudScore()).isEqualTo(0.0123);
        assertThat(update.fraud()).isFalse();
        assertThat(update.modelVersion()).isEqualTo("3");
        assertThat(update.scoredAt()).isEqualTo(Instant.parse("2026-10-26T09:15:00.041Z"));
    }

    @Test
    void rejectsUnreadableAndIncompletePayloads() throws Exception {
        assertThatThrownBy(() -> listener.onTransactionScored("{not json"))
                .isInstanceOf(InvalidMessageException.class);

        ObjectNode missingVersion = (ObjectNode) json.readTree(ContractSchemas.example("transaction.scored"));
        missingVersion.remove("model_version");
        assertThatThrownBy(() -> listener.onTransactionScored(missingVersion.toString()))
                .isInstanceOf(InvalidMessageException.class);

        ObjectNode outOfRange = (ObjectNode) json.readTree(ContractSchemas.example("transaction.scored"));
        outOfRange.put("fraud_score", 1.2);
        assertThatThrownBy(() -> listener.onTransactionScored(outOfRange.toString()))
                .hasMessageContaining("fraud_score");

        verify(scores, never()).apply(any());
    }

    @Test
    void mapsTheDriftExampleToAReport() {
        listener.onDriftDetected(ContractSchemas.example("drift.detected"));

        ArgumentCaptor<DriftReport> captor = ArgumentCaptor.forClass(DriftReport.class);
        verify(modelOps).recordDrift(captor.capture());
        DriftReport report = captor.getValue();
        assertThat(report.getId()).isEqualTo(UUID.fromString("1c9e6f50-2d7a-4b8e-8f3c-5a6b7c8d9e0f"));
        assertThat(report.getWindow().rows()).isEqualTo(12000);
        assertThat(report.getDriftShare()).isEqualTo(0.36);
        assertThat(report.getDriftedFeatures()).containsExactly("v4", "v10", "v12", "v14", "amount");
        assertThat(report.getQuality().referencePrAuc()).isEqualTo(0.84);
        assertThat(report.getReceivedAt()).isEqualTo(now);
    }

    @Test
    void rejectsDriftWithoutWindow() throws Exception {
        ObjectNode payload = (ObjectNode) json.readTree(ContractSchemas.example("drift.detected"));
        payload.remove("window");

        assertThatThrownBy(() -> listener.onDriftDetected(payload.toString())).isInstanceOf(InvalidMessageException.class);
        verify(modelOps, never()).recordDrift(any());
    }

    @Test
    void mapsTheModelPromotedExample() throws Exception {
        listener.onModelPromoted(ContractSchemas.example("model.promoted"));

        ArgumentCaptor<ModelVersionEvent> captor = ArgumentCaptor.forClass(ModelVersionEvent.class);
        verify(modelOps).recordModelVersion(captor.capture());
        ModelVersionEvent event = captor.getValue();
        assertThat(event.getVersion()).isEqualTo("4");
        assertThat(event.getPreviousVersion()).isEqualTo("3");
        assertThat(event.getReason()).isEqualTo("promotion");
        assertThat(event.getRunId()).isNotNull();

        ObjectNode noVersion = (ObjectNode) json.readTree(ContractSchemas.example("model.promoted"));
        noVersion.remove("version");
        assertThatThrownBy(() -> listener.onModelPromoted(noVersion.toString()))
                .isInstanceOf(InvalidMessageException.class);
    }
}
