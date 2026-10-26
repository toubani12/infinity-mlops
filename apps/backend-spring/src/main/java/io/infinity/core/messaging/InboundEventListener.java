package io.infinity.core.messaging;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.infinity.core.alert.ScoreIngestionService;
import io.infinity.core.modelops.ModelOpsService;
import java.time.Clock;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Component;

@Component
public class InboundEventListener {

    private final ObjectMapper json;
    private final ScoreIngestionService scores;
    private final ModelOpsService modelOps;
    private final Clock clock;

    public InboundEventListener(
            ObjectMapper json, ScoreIngestionService scores, ModelOpsService modelOps, Clock clock) {
        this.json = json;
        this.scores = scores;
        this.modelOps = modelOps;
        this.clock = clock;
    }

    @KafkaListener(topics = Topics.TRANSACTION_SCORED)
    public void onTransactionScored(String payload) {
        scores.apply(read(payload, TransactionScoredMessage.class).toScoreUpdate());
    }

    @KafkaListener(topics = Topics.DRIFT_DETECTED)
    public void onDriftDetected(String payload) {
        modelOps.recordDrift(read(payload, DriftDetectedMessage.class).toReport(clock.instant()));
    }

    @KafkaListener(topics = Topics.MODEL_PROMOTED)
    public void onModelPromoted(String payload) {
        modelOps.recordModelVersion(read(payload, ModelPromotedMessage.class).toEvent(clock.instant()));
    }

    private <T> T read(String payload, Class<T> type) {
        try {
            return json.readValue(payload, type);
        } catch (JsonProcessingException e) {
            throw new InvalidMessageException("Unreadable " + type.getSimpleName(), e);
        }
    }
}
