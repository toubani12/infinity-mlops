package io.infinity.core.transaction;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.fasterxml.jackson.databind.ObjectMapper;
import io.infinity.core.config.ConflictException;
import io.infinity.core.config.NotFoundException;
import java.time.Instant;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.data.domain.PageImpl;
import org.springframework.data.domain.PageRequest;
import org.springframework.http.MediaType;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

@WebMvcTest(TransactionController.class)
@AutoConfigureMockMvc(addFilters = false)
class TransactionControllerTest {

    private static final UUID ID = UUID.fromString("7f8d4c2e-1b3a-4e5f-9a6b-0c1d2e3f4a5b");

    @Autowired
    private MockMvc mvc;

    @Autowired
    private ObjectMapper json;

    @MockitoBean
    private TransactionService service;

    @Test
    void createsTransaction() throws Exception {
        when(service.create(any())).thenReturn(TransactionFixtures.transaction(ID, Instant.parse("2026-10-26T09:15:00Z")));

        mvc.perform(post("/api/transactions")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(json.writeValueAsString(body(149.62, TransactionFixtures.features()))))
                .andExpect(status().isCreated())
                .andExpect(header().string("Location", "/api/transactions/" + ID))
                .andExpect(jsonPath("$.transactionId").value(ID.toString()))
                .andExpect(jsonPath("$.timestamp").value("2026-10-26T09:15:00Z"))
                .andExpect(jsonPath("$.features.v28").isNumber())
                .andExpect(jsonPath("$.fraudScore").isEmpty());
    }

    @Test
    void rejectsMissingFeatureWithProblemDetail() throws Exception {
        Map<String, Double> features = TransactionFixtures.features();
        features.remove("v12");

        mvc.perform(post("/api/transactions")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(json.writeValueAsString(body(10.0, features))))
                .andExpect(status().isBadRequest())
                .andExpect(header().string("Content-Type", MediaType.APPLICATION_PROBLEM_JSON_VALUE))
                .andExpect(jsonPath("$.status").value(400))
                .andExpect(jsonPath("$.errors.features").exists());
        verify(service, never()).create(any());
    }

    @Test
    void rejectsNegativeAmountAndUnknownFeature() throws Exception {
        Map<String, Double> features = TransactionFixtures.features();
        features.put("v29", 1.0);

        mvc.perform(post("/api/transactions")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(json.writeValueAsString(body(-1.0, features))))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.errors.amount").exists())
                .andExpect(jsonPath("$.errors.features").exists());
    }

    @Test
    void reportsDuplicateIdAsConflict() throws Exception {
        when(service.create(any())).thenThrow(new ConflictException("Transaction " + ID + " already exists"));

        mvc.perform(post("/api/transactions")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(json.writeValueAsString(body(1.0, TransactionFixtures.features()))))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.detail").value("Transaction " + ID + " already exists"));
    }

    @Test
    void listsFraudOnlyPage() throws Exception {
        Transaction transaction = TransactionFixtures.transaction(ID, Instant.parse("2026-10-26T09:15:00Z"));
        transaction.applyScore(0.97, true, "3", Instant.parse("2026-10-26T09:15:01Z"));
        when(service.list(eq(true), eq(1), eq(20)))
                .thenReturn(new PageImpl<>(List.of(transaction), PageRequest.of(1, 20), 21));

        mvc.perform(get("/api/transactions").param("fraudOnly", "true").param("page", "1").param("size", "20"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.content[0].isFraud").value(true))
                .andExpect(jsonPath("$.content[0].modelVersion").value("3"))
                .andExpect(jsonPath("$.page").value(1))
                .andExpect(jsonPath("$.totalElements").value(21))
                .andExpect(jsonPath("$.totalPages").value(2));
    }

    @Test
    void rejectsOversizedPage() throws Exception {
        mvc.perform(get("/api/transactions").param("size", "500"))
                .andExpect(status().isBadRequest());
    }

    @Test
    void returnsNotFoundProblem() throws Exception {
        when(service.get(ID)).thenThrow(new NotFoundException("Transaction " + ID + " not found"));

        mvc.perform(get("/api/transactions/" + ID))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.title").value("Not Found"));
    }

    private static Map<String, Object> body(double amount, Map<String, Double> features) {
        Map<String, Object> body = new HashMap<>();
        body.put("amount", amount);
        body.put("features", features);
        return body;
    }
}
