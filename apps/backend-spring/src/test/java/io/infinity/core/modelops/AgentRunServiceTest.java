package io.infinity.core.modelops;

import static io.infinity.core.modelops.AgentRunFixtures.step;
import static io.infinity.core.modelops.AgentRunFixtures.untilApproval;
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import io.infinity.core.config.ClockConfig;
import io.infinity.core.config.ConflictException;
import io.infinity.core.config.NotFoundException;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicBoolean;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.autoconfigure.jackson.JacksonAutoConfiguration;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.boot.test.autoconfigure.jdbc.AutoConfigureTestDatabase;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Import;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.event.ApplicationEvents;
import org.springframework.test.context.event.RecordApplicationEvents;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

@DataJpaTest
@ActiveProfiles("test")
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
@Import({AgentRunService.class, ClockConfig.class, JacksonAutoConfiguration.class, AgentRunServiceTest.Fakes.class})
@RecordApplicationEvents
class AgentRunServiceTest {

    @TestConfiguration
    @EnableConfigurationProperties(AgentProperties.class)
    static class Fakes {

        @Bean
        RecordingSender recordingSender() {
            return new RecordingSender();
        }
    }

    static class RecordingSender implements AgentCommandSender {

        final List<AgentCommand> sent = new ArrayList<>();
        final AtomicBoolean brokerDown = new AtomicBoolean();

        @Override
        public void send(AgentCommand command) {
            if (brokerDown.get()) {
                throw new CommandNotSentException(new IllegalStateException("broker down"));
            }
            sent.add(command);
        }
    }

    @Autowired
    private AgentRunService service;

    @Autowired
    private AgentRunRepository runs;

    @Autowired
    private RecordingSender sender;

    @Autowired
    private ApplicationEvents applicationEvents;

    @BeforeEach
    void resetSender() {
        sender.sent.clear();
        sender.brokerDown.set(false);
    }

    @Test
    void foldsStepsIntoAWaitingRunWithMetricsAndTimeline() {
        UUID runId = UUID.randomUUID();
        for (AgentStepEvent event : untilApproval(runId)) {
            assertThat(service.record(event)).isTrue();
        }

        AgentRunDetailResponse detail = service.detail(runId);
        assertThat(detail.run().status()).isEqualTo(AgentRunStatus.AWAITING_APPROVAL);
        assertThat(detail.run().reportId()).hasToString(AgentRunFixtures.REPORT_ID);
        assertThat(detail.run().startedAt()).isEqualTo(AgentRunFixtures.T0);
        assertThat(detail.run().updatedAt()).isEqualTo(AgentRunFixtures.T0.plusSeconds(301));
        assertThat(detail.champion()).isEqualTo(new ModelMetrics("3", 0.71, 0.52, 6.1));
        assertThat(detail.challenger().prAuc()).isEqualTo(0.83);
        assertThat(detail.gate().passed()).isTrue();
        assertThat(detail.gate().reasons()).hasSize(2);
        assertThat(detail.gate().maxP95LatencyMs()).isEqualTo(50.0);
        assertThat(detail.events()).extracting(AgentRunEventResponse::step).containsExactly(
                "received", "qualified", "retrain_started", "retrain_finished", "evaluated", "approval_requested");
        assertThat(detail.events()).extracting(AgentRunEventResponse::seq).containsExactly(1, 2, 3, 4, 5, 6);
        assertThat(detail.events().get(2).payload()).contains("retrain-5b2c7d8e");
        assertThat(applicationEvents.stream(AgentRunChangedEvent.class)).hasSize(6);
    }

    @Test
    void ignoresRedeliveredEventsAndAttachedAlerts() {
        UUID runId = UUID.randomUUID();
        AgentStepEvent[] steps = untilApproval(runId);
        for (AgentStepEvent event : steps) {
            service.record(event);
        }

        assertThat(service.record(steps[5])).isFalse();
        service.record(step(runId, 400, AgentStep.RECEIVED, null, "{\"attached\":true}"));

        AgentRunDetailResponse detail = service.detail(runId);
        assertThat(detail.run().status()).isEqualTo(AgentRunStatus.AWAITING_APPROVAL);
        assertThat(detail.events()).hasSize(7);
    }

    @Test
    void recordsTheOutcomeOfAnApprovedRun() {
        UUID runId = UUID.randomUUID();
        for (AgentStepEvent event : untilApproval(runId)) {
            service.record(event);
        }
        service.decide(runId, AgentCommand.Action.APPROVE, "badr", null);
        assertThat(runs.findById(runId).orElseThrow().getPendingCommand().actor()).isEqualTo("badr");

        service.record(step(runId, 320, AgentStep.APPROVED, "promote", "{\"actor\":\"badr\",\"reason\":null}"));
        service.record(step(runId, 321, AgentStep.PROMOTED, "promote", "{\"version\":\"4\",\"previous_version\":\"3\"}"));
        service.record(step(runId, 321, AgentStep.COMPLETED, "promote", "{}"));

        AgentRun run = runs.findById(runId).orElseThrow();
        assertThat(run.getStatus()).isEqualTo(AgentRunStatus.PROMOTED);
        assertThat(run.getPendingCommand()).isNull();
        assertThat(run.getDecidedBy()).isEqualTo("badr");
        assertThat(run.getPromotedVersion()).isEqualTo("4");
        assertThat(service.list(AgentRunStatus.PROMOTED, 0, 10).getContent()).extracting(AgentRun::getId)
                .contains(runId);
    }

    @Test
    void failsOnUnknownRun() {
        assertThatThrownBy(() -> service.detail(UUID.randomUUID())).isInstanceOf(NotFoundException.class);
    }

    @Test
    void sendsOneCommandPerWaitingRun() {
        UUID runId = UUID.randomUUID();
        for (AgentStepEvent event : untilApproval(runId)) {
            service.record(event);
        }

        AgentRun run = service.decide(runId, AgentCommand.Action.REJECT, "badr", "latency budget too tight");

        assertThat(run.getStatus()).isEqualTo(AgentRunStatus.AWAITING_APPROVAL);
        assertThat(sender.sent).singleElement().satisfies(command -> {
            assertThat(command.runId()).isEqualTo(runId);
            assertThat(command.action()).isEqualTo(AgentCommand.Action.REJECT);
            assertThat(command.reason()).isEqualTo("latency budget too tight");
        });
        assertThatThrownBy(() -> service.decide(runId, AgentCommand.Action.APPROVE, "other", null))
                .isInstanceOf(ConflictException.class).hasMessageContaining("already sent");
        assertThat(sender.sent).hasSize(1);
    }

    @Test
    void refusesDecisionsOnRunsThatDoNotWait() {
        UUID runId = UUID.randomUUID();
        service.record(step(runId, 0, AgentStep.RECEIVED, null, "{}"));

        assertThatThrownBy(() -> service.decide(runId, AgentCommand.Action.APPROVE, "badr", null))
                .isInstanceOf(ConflictException.class).hasMessageContaining("RUNNING");
        assertThatThrownBy(() -> service.decide(UUID.randomUUID(), AgentCommand.Action.APPROVE, "badr", null))
                .isInstanceOf(NotFoundException.class);
        assertThat(sender.sent).isEmpty();
    }

    @Test
    @Transactional(propagation = Propagation.NOT_SUPPORTED)
    void leavesTheRunUntouchedWhenTheCommandCannotBeSent() {
        UUID runId = UUID.randomUUID();
        for (AgentStepEvent event : untilApproval(runId)) {
            service.record(event);
        }
        sender.brokerDown.set(true);

        assertThatThrownBy(() -> service.decide(runId, AgentCommand.Action.APPROVE, "badr", null))
                .isInstanceOf(CommandNotSentException.class);

        assertThat(runs.findById(runId).orElseThrow().getPendingCommand()).isNull();
        sender.brokerDown.set(false);
        service.decide(runId, AgentCommand.Action.APPROVE, "badr", null);
        assertThat(sender.sent).hasSize(1);
    }
}
