package io.infinity.core.messaging;

import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

@Component
@ConditionalOnProperty(prefix = "infinity.outbox", name = "enabled", havingValue = "true", matchIfMissing = true)
public class TransactionRawScheduler {

    private final TransactionRawRelay relay;

    public TransactionRawScheduler(TransactionRawRelay relay) {
        this.relay = relay;
    }

    @Scheduled(fixedDelayString = "${infinity.outbox.poll-interval-ms:200}")
    void run() {
        relay.publishPending();
    }
}
