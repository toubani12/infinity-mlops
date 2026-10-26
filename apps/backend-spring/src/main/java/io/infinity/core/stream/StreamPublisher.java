package io.infinity.core.stream;

import io.infinity.core.alert.AlertChangedEvent;
import io.infinity.core.transaction.TransactionScoredEvent;
import org.springframework.stereotype.Component;
import org.springframework.transaction.event.TransactionalEventListener;

@Component
public class StreamPublisher {

    private final SseBroadcaster broadcaster;

    public StreamPublisher(SseBroadcaster broadcaster) {
        this.broadcaster = broadcaster;
    }

    @TransactionalEventListener(fallbackExecution = true)
    public void onTransactionScored(TransactionScoredEvent event) {
        broadcaster.publish(StreamChannel.TRANSACTIONS, "transaction",
                event.transaction().transactionId().toString(), event.transaction());
    }

    @TransactionalEventListener(fallbackExecution = true)
    public void onAlertChanged(AlertChangedEvent event) {
        broadcaster.publish(StreamChannel.ALERTS, "alert", event.alert().id().toString(), event.alert());
    }
}
