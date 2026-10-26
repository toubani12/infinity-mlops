package io.infinity.core.messaging;

import io.infinity.core.transaction.Features;
import io.infinity.core.transaction.Transaction;
import java.util.LinkedHashMap;
import java.util.Map;

public final class TransactionRawMessage {

    private TransactionRawMessage() {
    }

    public static Map<String, Object> payload(Transaction transaction) {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("transaction_id", transaction.getId().toString());
        payload.put("timestamp", transaction.getOccurredAt().toString());
        payload.put("amount", transaction.getAmount());
        payload.putAll(Features.toMap(transaction.getFeatures()));
        if (transaction.getLabel() != null) {
            payload.put("label", transaction.getLabel());
        }
        return payload;
    }
}
