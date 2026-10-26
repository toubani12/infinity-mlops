package io.infinity.core.modelops;

import io.infinity.core.config.PageResponse;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import java.util.UUID;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api")
public class ModelOpsController {

    private final ModelOpsService service;

    public ModelOpsController(ModelOpsService service) {
        this.service = service;
    }

    @GetMapping("/drift/reports")
    public PageResponse<DriftReportResponse> driftReports(
            @RequestParam(defaultValue = "0") @Min(0) int page,
            @RequestParam(defaultValue = "20") @Min(1) @Max(200) int size) {
        return PageResponse.of(service.driftReports(page, size), DriftReportResponse::from);
    }

    @GetMapping("/drift/reports/{id}")
    public DriftReportResponse driftReport(@PathVariable UUID id) {
        return DriftReportResponse.from(service.driftReport(id));
    }

    @GetMapping("/models/versions")
    public PageResponse<ModelVersionResponse> modelVersions(
            @RequestParam(defaultValue = "0") @Min(0) int page,
            @RequestParam(defaultValue = "20") @Min(1) @Max(200) int size) {
        return PageResponse.of(service.modelVersions(page, size), ModelVersionResponse::from);
    }
}
