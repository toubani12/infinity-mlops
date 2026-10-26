package io.infinity.core.messaging;

import static org.assertj.core.api.Assertions.assertThat;

import com.fasterxml.jackson.databind.ObjectMapper;
import io.infinity.core.transaction.Features;
import io.infinity.core.transaction.Transaction;
import io.infinity.core.transaction.TransactionFixtures;
import java.time.Instant;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class TransactionRawMessageTest {

    private final ObjectMapper json = new ObjectMapper();

    @Test
    void serializedPayloadMatchesTheV1Schema() throws Exception {
        Transaction transaction = TransactionFixtures.transaction(UUID.randomUUID(), Instant.parse("2026-10-26T09:15:00Z"));

        String payload = json.writeValueAsString(TransactionRawMessage.payload(transaction));

        assertThat(ContractSchemas.validate("transaction.raw", payload)).isEmpty();
        assertThat(ContractSchemas.readTree(payload).fieldNames()).toIterable()
                .startsWith("transaction_id", "timestamp", "amount", "v1")
                .doesNotContain("label", "V1", "Amount");
    }

    @Test
    void includesKnownLabel() throws Exception {
        Transaction transaction = new Transaction(UUID.randomUUID(), Instant.parse("2026-10-26T09:15:00Z"),
                Instant.parse("2026-10-26T09:15:00Z"), 0.0, Features.toArray(TransactionFixtures.features()), 1);

        String payload = json.writeValueAsString(TransactionRawMessage.payload(transaction));

        assertThat(ContractSchemas.validate("transaction.raw", payload)).isEmpty();
        assertThat(ContractSchemas.readTree(payload).get("label").asInt()).isEqualTo(1);
    }

    @Test
    void validatorRejectsPayloadsOutsideTheContract() throws Exception {
        assertThat(ContractSchemas.validate("transaction.raw", ContractSchemas.example("transaction.raw"))).isEmpty();

        Map<String, Object> payload = TransactionRawMessage.payload(
                TransactionFixtures.transaction(UUID.randomUUID(), Instant.parse("2026-10-26T09:15:00Z")));
        payload.remove("v5");
        payload.put("transaction_id", "not-a-uuid");

        assertThat(ContractSchemas.validate("transaction.raw", json.writeValueAsString(payload))).hasSize(2);
    }
}
