package io.infinity.core.modelops;

import io.infinity.core.config.NotFoundException;
import java.util.UUID;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Sort;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class ModelOpsService {

    private final DriftReportRepository driftReports;
    private final ModelVersionEventRepository modelVersions;

    public ModelOpsService(DriftReportRepository driftReports, ModelVersionEventRepository modelVersions) {
        this.driftReports = driftReports;
        this.modelVersions = modelVersions;
    }

    @Transactional
    public boolean recordDrift(DriftReport report) {
        if (driftReports.existsById(report.getId())) {
            return false;
        }
        driftReports.save(report);
        return true;
    }

    @Transactional
    public boolean recordModelVersion(ModelVersionEvent event) {
        if (modelVersions.existsById(event.getId())) {
            return false;
        }
        modelVersions.save(event);
        return true;
    }

    @Transactional(readOnly = true)
    public Page<DriftReport> driftReports(int page, int size) {
        return driftReports.findAll(PageRequest.of(page, size, Sort.by(Sort.Direction.DESC, "detectedAt")));
    }

    @Transactional(readOnly = true)
    public DriftReport driftReport(UUID id) {
        return driftReports.findById(id).orElseThrow(() -> new NotFoundException("Drift report " + id + " not found"));
    }

    @Transactional(readOnly = true)
    public Page<ModelVersionEvent> modelVersions(int page, int size) {
        return modelVersions.findAll(PageRequest.of(page, size, Sort.by(Sort.Direction.DESC, "occurredAt")));
    }
}
