package io.infinity.core.modelops;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

public record DriftReportResponse(
        UUID reportId,
        Instant detectedAt,
        Instant windowStart,
        Instant windowEnd,
        int windowRows,
        double driftShare,
        List<String> driftedFeatures,
        List<String> missingFeatures,
        Double outOfRangeShare,
        Double prAuc,
        Double referencePrAuc,
        Double recallAtP90,
        Integer labeledRows,
        String modelVersion,
        String reportUri) {

    public static DriftReportResponse from(DriftReport r) {
        DriftReport.Window window = r.getWindow();
        DriftReport.Quality quality = r.getQuality();
        return new DriftReportResponse(r.getId(), r.getDetectedAt(), window.start(), window.end(), window.rows(),
                r.getDriftShare(), r.getDriftedFeatures(), r.getMissingFeatures(), r.getOutOfRangeShare(),
                quality.prAuc(), quality.referencePrAuc(), quality.recallAtP90(), quality.labeledRows(),
                r.getModelVersion(), r.getReportUri());
    }
}
