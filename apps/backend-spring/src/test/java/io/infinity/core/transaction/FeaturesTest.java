package io.infinity.core.transaction;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.Map;
import org.junit.jupiter.api.Test;

class FeaturesTest {

    @Test
    void roundTripsFeaturesInWireOrder() {
        Map<String, Double> features = TransactionFixtures.features();

        double[] values = Features.toArray(features);

        assertThat(values).hasSize(28);
        assertThat(values[0]).isEqualTo(features.get("v1"));
        assertThat(values[27]).isEqualTo(features.get("v28"));
        assertThat(Features.toMap(values)).containsExactlyEntriesOf(features);
    }

    @Test
    void rejectsIncompleteVectors() {
        Map<String, Double> features = TransactionFixtures.features();
        features.remove("v7");

        assertThatThrownBy(() -> Features.toArray(features)).hasMessageContaining("v7");
        assertThatThrownBy(() -> Features.toMap(new double[3])).isInstanceOf(IllegalArgumentException.class);
    }
}
