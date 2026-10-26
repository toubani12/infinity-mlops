package io.infinity.core.modelops;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.UncheckedIOException;
import java.time.Instant;
import java.util.UUID;

public final class AgentRunFixtures {

    public static final Instant T0 = Instant.parse("2026-10-26T10:00:00Z");
    public static final String REPORT_ID = "1c9e6f50-2d7a-4b8e-8f3c-5a6b7c8d9e0f";
    private static final ObjectMapper JSON = new ObjectMapper();

    private AgentRunFixtures() {
    }

    public static AgentStepEvent step(UUID runId, int second, AgentStep step, String decision, String payload) {
        try {
            JsonNode node = JSON.readTree(payload);
            return new AgentStepEvent(runId, UUID.randomUUID(), T0.plusSeconds(second), step, decision,
                    step == AgentStep.APPROVAL_REQUESTED, step.wireName() + " message", node);
        } catch (com.fasterxml.jackson.core.JsonProcessingException e) {
            throw new UncheckedIOException(e);
        }
    }

    public static String metricsPayload() {
        return """
                {"report_id":"%s","champion":{"version":"3","pr_auc":0.71,"recall_at_p90":0.52,"p95_latency_ms":6.1},
                 "challenger":{"version":"4","pr_auc":0.83,"recall_at_p90":0.68,"p95_latency_ms":6.4}}
                """.formatted(REPORT_ID);
    }

    /** The steps of a run that passed the gate, up to the approval request. */
    public static AgentStepEvent[] untilApproval(UUID runId) {
        String report = "{\"report_id\":\"" + REPORT_ID + "\"}";
        String evaluated = metricsPayload().replace("}}", "},\"gate\":{\"passed\":true,"
                + "\"reasons\":[\"pr_auc 0.830 > champion 0.710\",\"p95 latency 6.4 ms < 50 ms\"]}}");
        return new AgentStepEvent[] {
            step(runId, 0, AgentStep.RECEIVED, null, report),
            step(runId, 1, AgentStep.QUALIFIED, "real_drift", report),
            step(runId, 2, AgentStep.RETRAIN_STARTED, "real_drift", "{\"job_name\":\"retrain-5b2c7d8e\"}"),
            step(runId, 300, AgentStep.RETRAIN_FINISHED, null, "{\"status\":\"succeeded\"}"),
            step(runId, 301, AgentStep.EVALUATED, "promote", evaluated),
            step(runId, 301, AgentStep.APPROVAL_REQUESTED, "promote", metricsPayload()),
        };
    }
}
