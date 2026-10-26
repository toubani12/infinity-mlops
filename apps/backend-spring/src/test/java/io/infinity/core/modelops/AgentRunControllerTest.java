package io.infinity.core.modelops;

import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import io.infinity.core.security.Role;
import io.infinity.core.security.TokenService;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.data.domain.PageImpl;
import org.springframework.data.domain.PageRequest;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
class AgentRunControllerTest {

    private static final UUID RUN_ID = UUID.fromString("5b2c7d8e-9f0a-4b1c-8d2e-3f4a5b6c7d8e");

    @Autowired
    private MockMvc mvc;

    @Autowired
    private TokenService tokens;

    @MockitoBean
    private AgentRunService service;

    private AgentRun waitingRun() {
        AgentRun run = new AgentRun(RUN_ID, AgentRunFixtures.T0);
        for (AgentStepEvent event : AgentRunFixtures.untilApproval(RUN_ID)) {
            run.apply(event);
        }
        return run;
    }

    @Test
    void listsRunsAndShowsOneWithItsTimeline() throws Exception {
        AgentRun run = waitingRun();
        when(service.list(AgentRunStatus.AWAITING_APPROVAL, 0, 20))
                .thenReturn(new PageImpl<>(List.of(run), PageRequest.of(0, 20), 1));
        when(service.detail(RUN_ID)).thenReturn(AgentRunDetailResponse.from(run, List.of(new AgentRunEvent(
                AgentRunFixtures.untilApproval(RUN_ID)[5], 6, AgentRunFixtures.metricsPayload(),
                AgentRunFixtures.T0)), 50));

        mvc.perform(as(get("/api/agent/runs").param("status", "AWAITING_APPROVAL"), Role.ANALYST))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.content[0].runId").value(RUN_ID.toString()))
                .andExpect(jsonPath("$.content[0].status").value("AWAITING_APPROVAL"))
                .andExpect(jsonPath("$.content[0].challengerVersion").value("4"));
        mvc.perform(as(get("/api/agent/runs/" + RUN_ID), Role.ANALYST))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.run.lastStep").value("approval_requested"))
                .andExpect(jsonPath("$.champion.prAuc").value(0.71))
                .andExpect(jsonPath("$.challenger.p95LatencyMs").value(6.4))
                .andExpect(jsonPath("$.gate.passed").value(true))
                .andExpect(jsonPath("$.gate.maxP95LatencyMs").value(50.0))
                .andExpect(jsonPath("$.events[0].requiresApproval").value(true))
                .andExpect(jsonPath("$.events[0].payload.challenger.version").value("4"));
    }

    @Test
    void refusesAnonymousReaders() throws Exception {
        mvc.perform(get("/api/agent/runs")).andExpect(status().isUnauthorized());
    }

    private MockHttpServletRequestBuilder as(MockHttpServletRequestBuilder request, Role role) {
        return request.header("Authorization", "Bearer " + tokens.issue("badr", role).token());
    }
}
