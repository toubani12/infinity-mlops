package io.infinity.core.transaction;

import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;

public final class TransactionFixtures {

    private TransactionFixtures() {
    }

    public static Map<String, Double> features() {
        Map<String, Double> features = new LinkedHashMap<>();
        for (int i = 1; i <= Features.COUNT; i++) {
            features.put("v" + i, i / 10.0 - 1.4);
        }
        return features;
    }

    public static CreateTransactionRequest request(UUID id, double amount) {
        return new CreateTransactionRequest(id, null, amount, features(), null);
    }

    public static Transaction transaction(UUID id, Instant at) {
        return new Transaction(id, at, at, 149.62, Features.toArray(features()), null);
    }
}
