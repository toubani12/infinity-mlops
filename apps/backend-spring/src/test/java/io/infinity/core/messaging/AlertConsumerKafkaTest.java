package io.infinity.core.messaging;

import static org.assertj.core.api.Assertions.assertThat;
import static org.awaitility.Awaitility.await;

import io.infinity.core.alert.AlertRepository;
import io.infinity.core.transaction.Transaction;
import io.infinity.core.transaction.TransactionFixtures;
import io.infinity.core.transaction.TransactionRepository;
import io.infinity.core.transaction.TransactionService;
import java.time.Duration;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.test.context.EmbeddedKafka;
import org.springframework.test.context.ActiveProfiles;

@SpringBootTest(properties = {
        "spring.kafka.bootstrap-servers=${spring.embedded.kafka.brokers}",
        "spring.kafka.listener.auto-startup=true",
        "infinity.alerts.threshold=0.5"
})
@ActiveProfiles("test")
@EmbeddedKafka(partitions = 1, topics = Topics.TRANSACTION_SCORED)
class AlertConsumerKafkaTest {

    @Autowired
    private TransactionService transactionService;

    @Autowired
    private TransactionRepository transactions;

    @Autowired
    private AlertRepository alerts;

    @Autowired
    private KafkaTemplate<String, String> kafka;

    @Test
    void scoresTransactionAndOpensOneAlertDespitePoisonAndDuplicates() {
        Transaction created = transactionService.create(TransactionFixtures.request(null, 950.0));
        String id = created.getId().toString();
        String scored = """
                {"transaction_id":"%s","timestamp":"2026-10-26T09:15:00.041Z","fraud_score":0.93,
                 "is_fraud":true,"threshold":0.5,"model_name":"fraud-xgb","model_version":"4","latency_ms":3.1}
                """.formatted(id);
        assertThat(ContractSchemas.validate("transaction.scored", scored)).isEmpty();

        kafka.send(Topics.TRANSACTION_SCORED, id, "not json");
        kafka.send(Topics.TRANSACTION_SCORED, id, scored);
        kafka.send(Topics.TRANSACTION_SCORED, id, scored);

        await().atMost(Duration.ofSeconds(20)).untilAsserted(() -> {
            assertThat(transactions.findById(created.getId()).orElseThrow().getModelVersion()).isEqualTo("4");
            assertThat(alerts.existsByTransactionId(created.getId())).isTrue();
        });
        await().during(Duration.ofSeconds(1)).atMost(Duration.ofSeconds(5))
                .untilAsserted(() -> assertThat(alerts.count()).isEqualTo(1));
    }
}
