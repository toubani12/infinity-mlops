package io.infinity.core;

import static org.hamcrest.Matchers.containsString;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.fasterxml.jackson.databind.ObjectMapper;
import io.infinity.core.security.Role;
import io.infinity.core.security.TokenService;
import io.infinity.core.transaction.TransactionFixtures;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.actuate.observability.AutoConfigureObservability;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

@SpringBootTest
@AutoConfigureMockMvc
@AutoConfigureObservability
@ActiveProfiles("test")
class BackendApplicationTest {

    @Autowired
    private MockMvc mvc;

    @Autowired
    private ObjectMapper json;

    @Autowired
    private TokenService tokens;

    @Test
    void exposesHealthAndPrometheus() throws Exception {
        mvc.perform(get("/actuator/health")).andExpect(status().isOk()).andExpect(jsonPath("$.status").value("UP"));
        mvc.perform(get("/actuator/prometheus"))
                .andExpect(status().isOk())
                .andExpect(content().string(containsString("jvm_memory_used_bytes")));
    }

    @Test
    void storesAndListsTransaction() throws Exception {
        String body = json.writeValueAsString(Map.of("amount", 12.5, "features", TransactionFixtures.features()));

        String bearer = "Bearer " + tokens.issue("ana", Role.ANALYST).token();

        mvc.perform(post("/api/transactions").header("Authorization", bearer)
                        .contentType(MediaType.APPLICATION_JSON).content(body))
                .andExpect(status().isCreated());
        mvc.perform(get("/api/transactions").header("Authorization", bearer))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.content[0].amount").value(12.5));
    }

    @Test
    void doesNotIssueDevTokensOutsideTheLocalProfile() throws Exception {
        mvc.perform(post("/api/auth/dev-token").contentType(MediaType.APPLICATION_JSON)
                        .content("{\"username\":\"ana\",\"role\":\"admin\"}"))
                .andExpect(status().isNotFound());
    }
}
