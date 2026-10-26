package io.infinity.core.messaging;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.infinity.core.alert.ScoreIngestionService;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Component;

@Component
public class InboundEventListener {

    private final ObjectMapper json;
    private final ScoreIngestionService scores;

    public InboundEventListener(ObjectMapper json, ScoreIngestionService scores) {
        this.json = json;
        this.scores = scores;
    }

    @KafkaListener(topics = Topics.TRANSACTION_SCORED)
    public void onTransactionScored(String payload) {
        scores.apply(read(payload, TransactionScoredMessage.class).toScoreUpdate());
    }

    private <T> T read(String payload, Class<T> type) {
        try {
            return json.readValue(payload, type);
        } catch (JsonProcessingException e) {
            throw new InvalidMessageException("Unreadable " + type.getSimpleName(), e);
        }
    }
}
