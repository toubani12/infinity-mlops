package io.infinity.core.messaging;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;
import io.infinity.core.modelops.DriftReport;
import java.time.Instant;
import java.util.List;
import java.util.UUID;

@JsonIgnoreProperties(ignoreUnknown = true)
public record DriftDetectedMessage(
        @JsonProperty("report_id") UUID reportId,
        @JsonProperty("detected_at") Instant detectedAt,
        @JsonProperty("window") Window window,
        @JsonProperty("drift_share") Double driftShare,
        @JsonProperty("drifted_features") List<String> driftedFeatures,
        @JsonProperty("missing_features") List<String> missingFeatures,
        @JsonProperty("out_of_range_share") Double outOfRangeShare,
        @JsonProperty("metrics") Metrics metrics,
        @JsonProperty("model_version") String modelVersion,
        @JsonProperty("report_uri") String reportUri) {

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record Window(
            @JsonProperty("start") Instant start,
            @JsonProperty("end") Instant end,
            @JsonProperty("rows") Integer rows) {
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record Metrics(
            @JsonProperty("pr_auc") Double prAuc,
            @JsonProperty("reference_pr_auc") Double referencePrAuc,
            @JsonProperty("recall_at_p90") Double recallAtP90,
            @JsonProperty("labeled_rows") Integer labeledRows) {
    }

    public DriftReport toReport(Instant receivedAt) {
        if (reportId == null || detectedAt == null || window == null || window.start() == null
                || window.end() == null || window.rows() == null || driftShare == null || driftedFeatures == null
                || metrics == null) {
            throw new InvalidMessageException("drift.detected is missing a required field");
        }
        return new DriftReport(
                reportId,
                detectedAt,
                new DriftReport.Window(window.start(), window.end(), window.rows()),
                driftShare,
                driftedFeatures,
                missingFeatures == null ? List.of() : missingFeatures,
                outOfRangeShare,
                new DriftReport.Quality(
                        metrics.prAuc(), metrics.referencePrAuc(), metrics.recallAtP90(), metrics.labeledRows()),
                modelVersion,
                reportUri,
                receivedAt);
    }
}
