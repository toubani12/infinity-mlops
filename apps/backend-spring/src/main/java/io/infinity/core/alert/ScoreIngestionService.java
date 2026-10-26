package io.infinity.core.alert;

import io.infinity.core.transaction.Transaction;
import io.infinity.core.transaction.TransactionRepository;
import io.infinity.core.transaction.TransactionResponse;
import io.infinity.core.transaction.TransactionScoredEvent;
import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.MeterRegistry;
import java.time.Clock;
import java.util.Optional;
import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.lang.Nullable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class ScoreIngestionService {

    private static final Logger log = LoggerFactory.getLogger(ScoreIngestionService.class);

    public record Outcome(Transaction transaction, @Nullable Alert createdAlert) {
    }

    private final TransactionRepository transactions;
    private final AlertRepository alerts;
    private final AlertProperties properties;
    private final Clock clock;
    private final ApplicationEventPublisher events;
    private final Counter alertsCreated;
    private final Counter unknownTransactions;

    public ScoreIngestionService(
            TransactionRepository transactions,
            AlertRepository alerts,
            AlertProperties properties,
            Clock clock,
            ApplicationEventPublisher events,
            MeterRegistry meters) {
        this.transactions = transactions;
        this.alerts = alerts;
        this.properties = properties;
        this.clock = clock;
        this.events = events;
        this.alertsCreated = meters.counter("infinity.alerts.created");
        this.unknownTransactions = meters.counter("infinity.scores.unknown.transaction");
    }

    /**
     * Safe to replay: the score is overwritten with the same values and at most one alert exists per transaction
     * (checked here, enforced by the unique constraint on alerts.transaction_id).
     */
    @Transactional
    public Optional<Outcome> apply(ScoreUpdate update) {
        Optional<Transaction> found = transactions.findById(update.transactionId());
        if (found.isEmpty()) {
            unknownTransactions.increment();
            log.warn("Ignoring score for unknown transaction {}", update.transactionId());
            return Optional.empty();
        }
        Transaction transaction = found.get();
        transaction.applyScore(update.fraudScore(), update.fraud(), update.modelVersion(), update.scoredAt());
        events.publishEvent(new TransactionScoredEvent(TransactionResponse.from(transaction)));
        Alert alert = raiseAlertIfNeeded(transaction.getId(), update.fraudScore());
        if (alert != null) {
            events.publishEvent(new AlertChangedEvent(AlertResponse.from(alert)));
        }
        return Optional.of(new Outcome(transaction, alert));
    }

    @Nullable
    private Alert raiseAlertIfNeeded(UUID transactionId, double fraudScore) {
        if (fraudScore < properties.threshold() || alerts.existsByTransactionId(transactionId)) {
            return null;
        }
        alertsCreated.increment();
        return alerts.save(new Alert(UUID.randomUUID(), transactionId, fraudScore, clock.instant()));
    }
}
