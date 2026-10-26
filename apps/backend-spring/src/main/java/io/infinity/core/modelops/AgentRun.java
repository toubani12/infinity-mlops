package io.infinity.core.modelops;

import com.fasterxml.jackson.databind.JsonNode;
import jakarta.persistence.AttributeOverride;
import jakarta.persistence.AttributeOverrides;
import jakarta.persistence.Column;
import jakarta.persistence.Embedded;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import jakarta.persistence.Version;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;
import org.springframework.lang.Nullable;

@Entity
@Table(name = "agent_run")
public class AgentRun {

    static final int MAX_TEXT = 4000;

    @Id
    @Column(name = "run_id")
    private UUID id;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private AgentRunStatus status;

    @Column(name = "report_id")
    private UUID reportId;

    @Column(name = "started_at", nullable = false)
    private Instant startedAt;

    @Column(name = "updated_at", nullable = false)
    private Instant updatedAt;

    @Column(name = "last_step", nullable = false)
    private String lastStep;

    @Column(name = "last_decision")
    private String lastDecision;

    @Column(name = "last_message")
    private String lastMessage;

    @Column(name = "event_count", nullable = false)
    private int eventCount;

    @Embedded
    @AttributeOverrides({
            @AttributeOverride(name = "version", column = @Column(name = "champion_version")),
            @AttributeOverride(name = "prAuc", column = @Column(name = "champion_pr_auc")),
            @AttributeOverride(name = "recallAtP90", column = @Column(name = "champion_recall_at_p90")),
            @AttributeOverride(name = "p95LatencyMs", column = @Column(name = "champion_p95_latency_ms"))
    })
    private ModelMetrics champion;

    @Embedded
    @AttributeOverrides({
            @AttributeOverride(name = "version", column = @Column(name = "challenger_version")),
            @AttributeOverride(name = "prAuc", column = @Column(name = "challenger_pr_auc")),
            @AttributeOverride(name = "recallAtP90", column = @Column(name = "challenger_recall_at_p90")),
            @AttributeOverride(name = "p95LatencyMs", column = @Column(name = "challenger_p95_latency_ms"))
    })
    private ModelMetrics challenger;

    @Column(name = "gate_passed")
    private Boolean gatePassed;

    @JdbcTypeCode(SqlTypes.ARRAY)
    @Column(name = "gate_reasons")
    private String[] gateReasons;

    @Column(name = "decided_by")
    private String decidedBy;

    @Column(name = "decision_reason")
    private String decisionReason;

    @Column(name = "promoted_version")
    private String promotedVersion;

    @Version
    @Column(name = "row_version")
    private Long rowVersion;

    protected AgentRun() {
    }

    public AgentRun(UUID id, Instant startedAt) {
        this.id = id;
        this.status = AgentRunStatus.RUNNING;
        this.startedAt = startedAt;
        this.updatedAt = startedAt;
        this.lastStep = AgentStep.RECEIVED.wireName();
    }

    /** Folds one step into the run and returns the step's position in the run's timeline. */
    int apply(AgentStepEvent event) {
        JsonNode payload = event.payload();
        status = status.after(event.step(), event.decision());
        lastStep = event.step().wireName();
        lastMessage = truncate(event.message());
        if (event.decision() != null) {
            lastDecision = event.decision();
        }
        if (event.timestamp().isAfter(updatedAt)) {
            updatedAt = event.timestamp();
        }
        if (reportId == null && ModelMetrics.text(payload, "report_id") instanceof String report) {
            reportId = parseUuid(report);
        }
        recordMetrics(payload);
        switch (event.step()) {
            case APPROVED, REJECTED -> {
                decidedBy = ModelMetrics.text(payload, "actor");
                decisionReason = ModelMetrics.text(payload, "reason");
            }
            case PROMOTED -> promotedVersion = ModelMetrics.text(payload, "version");
            default -> {
            }
        }
        eventCount++;
        return eventCount;
    }

    private void recordMetrics(JsonNode payload) {
        ModelMetrics championMetrics = ModelMetrics.fromPayload(payload.get("champion"));
        ModelMetrics challengerMetrics = ModelMetrics.fromPayload(payload.get("challenger"));
        if (championMetrics != null) {
            champion = championMetrics;
        }
        if (challengerMetrics != null) {
            challenger = challengerMetrics;
        }
        JsonNode gate = payload.get("gate");
        if (gate != null && gate.isObject()) {
            gatePassed = gate.path("passed").asBoolean(false);
            List<String> reasons = new ArrayList<>();
            gate.path("reasons").forEach(reason -> reasons.add(reason.asText()));
            gateReasons = reasons.toArray(String[]::new);
        }
    }

    @Nullable
    static String truncate(@Nullable String text) {
        return text == null || text.length() <= MAX_TEXT ? text : text.substring(0, MAX_TEXT);
    }

    @Nullable
    private static UUID parseUuid(String value) {
        try {
            return UUID.fromString(value);
        } catch (IllegalArgumentException e) {
            return null;
        }
    }

    public UUID getId() {
        return id;
    }

    public AgentRunStatus getStatus() {
        return status;
    }

    public UUID getReportId() {
        return reportId;
    }

    public Instant getStartedAt() {
        return startedAt;
    }

    public Instant getUpdatedAt() {
        return updatedAt;
    }

    public String getLastStep() {
        return lastStep;
    }

    public String getLastDecision() {
        return lastDecision;
    }

    public String getLastMessage() {
        return lastMessage;
    }

    public ModelMetrics getChampion() {
        return champion;
    }

    public ModelMetrics getChallenger() {
        return challenger;
    }

    public Boolean getGatePassed() {
        return gatePassed;
    }

    public List<String> getGateReasons() {
        return gateReasons == null ? List.of() : List.of(gateReasons);
    }

    public String getDecidedBy() {
        return decidedBy;
    }

    public String getDecisionReason() {
        return decisionReason;
    }

    public String getPromotedVersion() {
        return promotedVersion;
    }
}
