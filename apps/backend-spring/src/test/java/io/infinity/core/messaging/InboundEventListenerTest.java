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
import java.time.Instant;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

class InboundEventListenerTest {

    private final ObjectMapper json = JsonMapper.builder().findAndAddModules().build();
    private final ScoreIngestionService scores = mock(ScoreIngestionService.class);
    private final InboundEventListener listener = new InboundEventListener(json, scores);

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
}
