package io.infinity.core.modelops;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.Instant;
import java.util.List;
import java.util.UUID;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

@Entity
@Table(name = "drift_report")
public class DriftReport {

    @Id
    @Column(name = "report_id")
    private UUID id;

    @Column(name = "detected_at", nullable = false)
    private Instant detectedAt;

    @Column(name = "window_start", nullable = false)
    private Instant windowStart;

    @Column(name = "window_end", nullable = false)
    private Instant windowEnd;

    @Column(name = "window_rows", nullable = false)
    private int windowRows;

    @Column(name = "drift_share", nullable = false)
    private double driftShare;

    @JdbcTypeCode(SqlTypes.ARRAY)
    @Column(name = "drifted_features", nullable = false)
    private String[] driftedFeatures;

    @JdbcTypeCode(SqlTypes.ARRAY)
    @Column(name = "missing_features", nullable = false)
    private String[] missingFeatures;

    @Column(name = "out_of_range_share")
    private Double outOfRangeShare;

    @Column(name = "pr_auc")
    private Double prAuc;

    @Column(name = "reference_pr_auc")
    private Double referencePrAuc;

    @Column(name = "recall_at_p90")
    private Double recallAtP90;

    @Column(name = "labeled_rows")
    private Integer labeledRows;

    @Column(name = "model_version")
    private String modelVersion;

    @Column(name = "report_uri")
    private String reportUri;

    @Column(name = "received_at", nullable = false)
    private Instant receivedAt;

    protected DriftReport() {
    }

    public DriftReport(UUID id, Instant detectedAt, Window window, double driftShare, List<String> driftedFeatures,
            List<String> missingFeatures, Double outOfRangeShare, Quality quality, String modelVersion,
            String reportUri, Instant receivedAt) {
        this.id = id;
        this.detectedAt = detectedAt;
        this.windowStart = window.start();
        this.windowEnd = window.end();
        this.windowRows = window.rows();
        this.driftShare = driftShare;
        this.driftedFeatures = driftedFeatures.toArray(String[]::new);
        this.missingFeatures = missingFeatures.toArray(String[]::new);
        this.outOfRangeShare = outOfRangeShare;
        this.prAuc = quality.prAuc();
        this.referencePrAuc = quality.referencePrAuc();
        this.recallAtP90 = quality.recallAtP90();
        this.labeledRows = quality.labeledRows();
        this.modelVersion = modelVersion;
        this.reportUri = reportUri;
        this.receivedAt = receivedAt;
    }

    public record Window(Instant start, Instant end, int rows) {
    }

    public record Quality(Double prAuc, Double referencePrAuc, Double recallAtP90, Integer labeledRows) {
    }

    public UUID getId() {
        return id;
    }

    public Instant getDetectedAt() {
        return detectedAt;
    }

    public Window getWindow() {
        return new Window(windowStart, windowEnd, windowRows);
    }

    public double getDriftShare() {
        return driftShare;
    }

    public List<String> getDriftedFeatures() {
        return List.of(driftedFeatures);
    }

    public List<String> getMissingFeatures() {
        return List.of(missingFeatures);
    }

    public Double getOutOfRangeShare() {
        return outOfRangeShare;
    }

    public Quality getQuality() {
        return new Quality(prAuc, referencePrAuc, recallAtP90, labeledRows);
    }

    public String getModelVersion() {
        return modelVersion;
    }

    public String getReportUri() {
        return reportUri;
    }

    public Instant getReceivedAt() {
        return receivedAt;
    }
}
