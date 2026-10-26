package io.infinity.core.alert;

import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.ArgumentMatchers.isNull;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.patch;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import io.infinity.core.config.ConflictException;
import io.infinity.core.config.NotFoundException;
import java.time.Instant;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.data.domain.PageImpl;
import org.springframework.data.domain.PageRequest;
import org.springframework.http.MediaType;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

@WebMvcTest(AlertController.class)
class AlertControllerTest {

    private static final Instant T0 = Instant.parse("2026-10-26T10:00:00Z");

    @Autowired
    private MockMvc mvc;

    @MockitoBean
    private AlertService service;

    @Test
    void listsAlertsFilteredByStatus() throws Exception {
        Alert alert = new Alert(UUID.randomUUID(), UUID.randomUUID(), 0.88, T0);
        when(service.list(eq(AlertStatus.OPEN), eq(0), eq(50)))
                .thenReturn(new PageImpl<>(List.of(alert), PageRequest.of(0, 50), 1));

        mvc.perform(get("/api/alerts").param("status", "OPEN"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.content[0].status").value("OPEN"))
                .andExpect(jsonPath("$.content[0].fraudScore").value(0.88))
                .andExpect(jsonPath("$.totalElements").value(1));
    }

    @Test
    void listsAllAlertsWithoutStatus() throws Exception {
        when(service.list(isNull(), eq(0), eq(50))).thenReturn(new PageImpl<>(List.of(), PageRequest.of(0, 50), 0));

        mvc.perform(get("/api/alerts")).andExpect(status().isOk()).andExpect(jsonPath("$.content").isEmpty());
    }

    @Test
    void rejectsUnknownStatusFilter() throws Exception {
        mvc.perform(get("/api/alerts").param("status", "SNOOZED")).andExpect(status().isBadRequest());
    }

    @Test
    void updatesStatus() throws Exception {
        Alert alert = new Alert(UUID.randomUUID(), UUID.randomUUID(), 0.88, T0);
        alert.moveTo(AlertStatus.ACKNOWLEDGED, T0.plusSeconds(5));
        when(service.updateStatus(alert.getId(), AlertStatus.ACKNOWLEDGED)).thenReturn(alert);

        mvc.perform(patch("/api/alerts/" + alert.getId())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"status\":\"ACKNOWLEDGED\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("ACKNOWLEDGED"))
                .andExpect(jsonPath("$.updatedAt").value("2026-10-26T10:00:05Z"));
    }

    @Test
    void requiresStatusInBody() throws Exception {
        mvc.perform(patch("/api/alerts/" + UUID.randomUUID()).contentType(MediaType.APPLICATION_JSON).content("{}"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.errors.status").exists());
    }

    @Test
    void mapsServiceErrorsToProblems() throws Exception {
        UUID missing = UUID.randomUUID();
        UUID closed = UUID.randomUUID();
        when(service.updateStatus(missing, AlertStatus.CLOSED)).thenThrow(new NotFoundException("Alert not found"));
        when(service.updateStatus(closed, AlertStatus.OPEN)).thenThrow(new ConflictException("Alert is CLOSED"));

        mvc.perform(patch("/api/alerts/" + missing).contentType(MediaType.APPLICATION_JSON).content("{\"status\":\"CLOSED\"}"))
                .andExpect(status().isNotFound());
        mvc.perform(patch("/api/alerts/" + closed).contentType(MediaType.APPLICATION_JSON).content("{\"status\":\"OPEN\"}"))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.detail").value("Alert is CLOSED"));
    }
}
