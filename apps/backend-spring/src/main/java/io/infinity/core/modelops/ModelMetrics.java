package io.infinity.core.modelops;

import com.fasterxml.jackson.databind.JsonNode;
import jakarta.persistence.Embeddable;
import org.springframework.lang.Nullable;

@Embeddable
public record ModelMetrics(String version, Double prAuc, Double recallAtP90, Double p95LatencyMs) {

    @Nullable
    static ModelMetrics fromPayload(@Nullable JsonNode node) {
        if (node == null || !node.isObject()) {
            return null;
        }
        return new ModelMetrics(text(node, "version"), number(node, "pr_auc"), number(node, "recall_at_p90"),
                number(node, "p95_latency_ms"));
    }

    @Nullable
    static String text(JsonNode node, String field) {
        JsonNode value = node.get(field);
        return value == null || value.isNull() ? null : value.asText();
    }

    @Nullable
    private static Double number(JsonNode node, String field) {
        JsonNode value = node.get(field);
        return value != null && value.isNumber() ? value.asDouble() : null;
    }
}
