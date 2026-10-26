package io.infinity.core.modelops;

import static io.infinity.core.modelops.AgentStep.APPROVAL_REQUESTED;
import static io.infinity.core.modelops.AgentStep.APPROVED;
import static io.infinity.core.modelops.AgentStep.COMPLETED;
import static io.infinity.core.modelops.AgentStep.ESCALATED;
import static io.infinity.core.modelops.AgentStep.EVALUATED;
import static io.infinity.core.modelops.AgentStep.FAILED;
import static io.infinity.core.modelops.AgentStep.PROMOTED;
import static io.infinity.core.modelops.AgentStep.QUALIFIED;
import static io.infinity.core.modelops.AgentStep.RECEIVED;
import static io.infinity.core.modelops.AgentStep.REJECTED;
import static io.infinity.core.modelops.AgentStep.RETRAIN_FINISHED;
import static io.infinity.core.modelops.AgentStep.RETRAIN_STARTED;
import static org.assertj.core.api.Assertions.assertThat;

import java.util.List;
import org.junit.jupiter.api.Test;

class AgentRunStatusTest {

    private record Step(AgentStep step, String decision) {
    }

    private static AgentRunStatus replay(Step... steps) {
        AgentRunStatus status = AgentRunStatus.RUNNING;
        for (Step s : steps) {
            status = status.after(s.step(), s.decision());
        }
        return status;
    }

    private static Step s(AgentStep step, String decision) {
        return new Step(step, decision);
    }

    private static final List<Step> UNTIL_EVALUATED = List.of(s(RECEIVED, null), s(QUALIFIED, "real_drift"),
            s(RETRAIN_STARTED, "real_drift"), s(RETRAIN_FINISHED, null));

    private static AgentRunStatus afterTraining(Step... rest) {
        List<Step> all = new java.util.ArrayList<>(UNTIL_EVALUATED);
        all.addAll(List.of(rest));
        return replay(all.toArray(Step[]::new));
    }

    @Test
    void followsEveryPathOfTheAgentReadme() {
        assertThat(replay(s(RECEIVED, null), s(QUALIFIED, "noise"), s(COMPLETED, "noise")))
                .isEqualTo(AgentRunStatus.NOISE);
        assertThat(replay(s(RECEIVED, null), s(QUALIFIED, "data_incident"), s(ESCALATED, "data_incident"),
                s(COMPLETED, "data_incident"))).isEqualTo(AgentRunStatus.ESCALATED);
        assertThat(replay(s(RECEIVED, null), s(QUALIFIED, "real_drift"), s(RETRAIN_STARTED, "real_drift"),
                s(FAILED, null))).isEqualTo(AgentRunStatus.FAILED);
        assertThat(afterTraining(s(EVALUATED, "keep_champion"), s(COMPLETED, "keep_champion")))
                .isEqualTo(AgentRunStatus.KEPT_CHAMPION);
        assertThat(afterTraining(s(EVALUATED, "promote"), s(APPROVAL_REQUESTED, "promote")))
                .isEqualTo(AgentRunStatus.AWAITING_APPROVAL);
        assertThat(afterTraining(s(EVALUATED, "promote"), s(APPROVAL_REQUESTED, "promote"), s(APPROVED, "promote")))
                .isEqualTo(AgentRunStatus.RUNNING);
        assertThat(afterTraining(s(EVALUATED, "promote"), s(APPROVAL_REQUESTED, "promote"), s(APPROVED, "promote"),
                s(PROMOTED, "promote"), s(COMPLETED, "promote"))).isEqualTo(AgentRunStatus.PROMOTED);
        assertThat(afterTraining(s(EVALUATED, "promote"), s(APPROVAL_REQUESTED, "promote"),
                s(REJECTED, "keep_champion"), s(COMPLETED, "keep_champion"))).isEqualTo(AgentRunStatus.REJECTED);
    }

    @Test
    void keepsWaitingWhenAnotherAlertIsAttached() {
        assertThat(AgentRunStatus.AWAITING_APPROVAL.after(RECEIVED, null)).isEqualTo(AgentRunStatus.AWAITING_APPROVAL);
    }

    @Test
    void neverLeavesAFinalStatus() {
        assertThat(AgentRunStatus.FAILED.after(COMPLETED, "promote")).isEqualTo(AgentRunStatus.FAILED);
        assertThat(AgentRunStatus.PROMOTED.after(AgentStep.ROLLED_BACK, null)).isEqualTo(AgentRunStatus.PROMOTED);
        assertThat(AgentRunStatus.RUNNING.after(COMPLETED, null)).isEqualTo(AgentRunStatus.RUNNING);
        assertThat(AgentRunStatus.NOISE.isFinal()).isTrue();
        assertThat(AgentRunStatus.AWAITING_APPROVAL.isFinal()).isFalse();
    }

    @Test
    void readsWireNames() {
        assertThat(AgentStep.fromWire("approval_requested")).contains(APPROVAL_REQUESTED);
        assertThat(AgentStep.fromWire("APPROVED")).isEmpty();
        assertThat(APPROVAL_REQUESTED.wireName()).isEqualTo("approval_requested");
    }
}
