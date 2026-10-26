package io.infinity.core.messaging;

import static org.assertj.core.api.Assertions.assertThat;

import io.infinity.core.transaction.Transaction;
import io.infinity.core.transaction.TransactionFixtures;
import io.infinity.core.transaction.TransactionRepository;
import io.infinity.core.transaction.TransactionService;
import java.time.Duration;
import java.util.Map;
import org.apache.kafka.clients.consumer.Consumer;
import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.apache.kafka.common.serialization.StringDeserializer;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.kafka.core.DefaultKafkaConsumerFactory;
import org.springframework.kafka.test.EmbeddedKafkaBroker;
import org.springframework.kafka.test.context.EmbeddedKafka;
import org.springframework.kafka.test.utils.KafkaTestUtils;
import org.springframework.test.context.ActiveProfiles;

@SpringBootTest(properties = "spring.kafka.bootstrap-servers=${spring.embedded.kafka.brokers}")
@ActiveProfiles("test")
@EmbeddedKafka(partitions = 1, topics = Topics.TRANSACTION_RAW)
class TransactionRawPublicationTest {

    @Autowired
    private TransactionService transactions;

    @Autowired
    private TransactionRepository repository;

    @Autowired
    private TransactionRawRelay relay;

    @Autowired
    private EmbeddedKafkaBroker broker;

    @Test
    void publishesCommittedTransactionKeyedByIdAndMarksIt() {
        Transaction created = transactions.create(TransactionFixtures.request(null, 88.0));

        assertThat(relay.publishPending()).isEqualTo(1);
        assertThat(relay.publishPending()).isZero();

        Map<String, Object> props = KafkaTestUtils.consumerProps("contract-check", "false", broker);
        props.put("auto.offset.reset", "earliest");
        try (Consumer<String, String> consumer = new DefaultKafkaConsumerFactory<>(
                props, new StringDeserializer(), new StringDeserializer()).createConsumer()) {
            broker.consumeFromAnEmbeddedTopic(consumer, Topics.TRANSACTION_RAW);
            ConsumerRecord<String, String> record =
                    KafkaTestUtils.getSingleRecord(consumer, Topics.TRANSACTION_RAW, Duration.ofSeconds(10));

            assertThat(record.key()).isEqualTo(created.getId().toString());
            assertThat(ContractSchemas.validate("transaction.raw", record.value())).isEmpty();
            assertThat(ContractSchemas.readTree(record.value()).get("amount").asDouble()).isEqualTo(88.0);
        }
        assertThat(repository.findById(created.getId()).orElseThrow().getPublishedAt()).isNotNull();
    }
}
