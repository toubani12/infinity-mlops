package io.infinity.core.modelops;

import java.util.List;

public record AgentRunDetailResponse(
        AgentRunResponse run,
        ModelMetrics champion,
        ModelMetrics challenger,
        Gate gate,
        List<AgentRunEventResponse> events) {

    /** {@code passed} stays null until the agent has evaluated the challenger. */
    public record Gate(Boolean passed, List<String> reasons, double maxP95LatencyMs) {
    }

    public static AgentRunDetailResponse from(AgentRun run, List<AgentRunEvent> events, double maxP95LatencyMs) {
        return new AgentRunDetailResponse(AgentRunResponse.from(run), run.getChampion(), run.getChallenger(),
                new Gate(run.getGatePassed(), run.getGateReasons(), maxP95LatencyMs),
                events.stream().map(AgentRunEventResponse::from).toList());
    }
}
