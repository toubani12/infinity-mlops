package io.infinity.core.modelops;

import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import io.infinity.core.config.NotFoundException;
import java.time.Instant;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.data.domain.PageImpl;
import org.springframework.data.domain.PageRequest;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

@WebMvcTest(ModelOpsController.class)
@AutoConfigureMockMvc(addFilters = false)
class ModelOpsControllerTest {

    private static final Instant T0 = Instant.parse("2026-10-26T10:00:00Z");

    @Autowired
    private MockMvc mvc;

    @MockitoBean
    private ModelOpsService service;

    @Test
    void listsDriftReports() throws Exception {
        DriftReport report = ModelOpsServiceTest.report(UUID.randomUUID(), T0, List.of("v4", "amount"), 0.71);
        when(service.driftReports(0, 20)).thenReturn(new PageImpl<>(List.of(report), PageRequest.of(0, 20), 1));

        mvc.perform(get("/api/drift/reports"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.content[0].reportId").value(report.getId().toString()))
                .andExpect(jsonPath("$.content[0].windowRows").value(12000))
                .andExpect(jsonPath("$.content[0].windowStart").value("2026-10-26T09:00:00Z"))
                .andExpect(jsonPath("$.content[0].driftedFeatures[1]").value("amount"))
                .andExpect(jsonPath("$.content[0].prAuc").value(0.71))
                .andExpect(jsonPath("$.content[0].referencePrAuc").value(0.84));
    }

    @Test
    void returnsOneReportOr404() throws Exception {
        DriftReport report = ModelOpsServiceTest.report(UUID.randomUUID(), T0, List.of("v4"), null);
        UUID missing = UUID.randomUUID();
        when(service.driftReport(report.getId())).thenReturn(report);
        when(service.driftReport(missing)).thenThrow(new NotFoundException("Drift report not found"));

        mvc.perform(get("/api/drift/reports/" + report.getId()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.prAuc").isEmpty());
        mvc.perform(get("/api/drift/reports/" + missing)).andExpect(status().isNotFound());
    }

    @Test
    void listsModelVersions() throws Exception {
        ModelVersionEvent event = ModelOpsServiceTest.event(T0, "4", "3", "promotion");
        when(service.modelVersions(1, 5)).thenReturn(new PageImpl<>(List.of(event), PageRequest.of(1, 5), 6));

        mvc.perform(get("/api/models/versions").param("page", "1").param("size", "5"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.content[0].version").value("4"))
                .andExpect(jsonPath("$.content[0].previousVersion").value("3"))
                .andExpect(jsonPath("$.content[0].timestamp").value("2026-10-26T10:00:00Z"))
                .andExpect(jsonPath("$.totalPages").value(2));
    }
}
