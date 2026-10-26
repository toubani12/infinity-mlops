package io.infinity.core.security;

import static org.hamcrest.Matchers.containsString;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.options;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.nimbusds.jose.jwk.source.ImmutableSecret;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.List;
import javax.crypto.spec.SecretKeySpec;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.security.oauth2.jose.jws.MacAlgorithm;
import org.springframework.security.oauth2.jwt.JwsHeader;
import org.springframework.security.oauth2.jwt.JwtClaimsSet;
import org.springframework.security.oauth2.jwt.JwtEncoder;
import org.springframework.security.oauth2.jwt.JwtEncoderParameters;
import org.springframework.security.oauth2.jwt.NimbusJwtEncoder;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles({"test", "local"})
class SecurityIntegrationTest {

    @Autowired
    private MockMvc mvc;

    @Autowired
    private TokenService tokens;

    @Autowired
    private JwtEncoder encoder;

    @Autowired
    private ObjectMapper json;

    @Test
    void rejectsMissingForgedAndExpiredTokens() throws Exception {
        mvc.perform(get("/api/alerts")).andExpect(status().isUnauthorized());

        JwtEncoder forger = new NimbusJwtEncoder(new ImmutableSecret<>(new SecretKeySpec(
                "another-secret-0123456789-0123456789".getBytes(StandardCharsets.UTF_8), "HmacSHA256")));
        mvc.perform(get("/api/alerts").header("Authorization", bearer(sign(forger, List.of("admin"), Instant.now()))))
                .andExpect(status().isUnauthorized());

        String expired = sign(encoder, List.of("analyst"), Instant.now().minusSeconds(3600));
        mvc.perform(get("/api/alerts").header("Authorization", bearer(expired)))
                .andExpect(status().isUnauthorized())
                .andExpect(header().string("WWW-Authenticate", containsString("invalid_token")));
    }

    @Test
    void forbidsTokensWithoutAKnownRole() throws Exception {
        String noRole = sign(encoder, List.of(), Instant.now().plusSeconds(600));
        String viewer = sign(encoder, List.of("viewer"), Instant.now().plusSeconds(600));

        mvc.perform(get("/api/alerts").header("Authorization", bearer(noRole))).andExpect(status().isForbidden());
        mvc.perform(get("/api/alerts").header("Authorization", bearer(viewer))).andExpect(status().isForbidden());
    }

    @Test
    void letsAnalystsAndAdminsReadTheApi() throws Exception {
        for (Role role : Role.values()) {
            mvc.perform(get("/api/alerts").header("Authorization", bearer(tokens.issue("ana", role).token())))
                    .andExpect(status().isOk());
        }
    }

    @Test
    void keepsHealthAndMetricsPublic() throws Exception {
        mvc.perform(get("/actuator/health")).andExpect(status().isOk());
        mvc.perform(get("/actuator/health/liveness")).andExpect(status().isOk());
        mvc.perform(get("/actuator/env")).andExpect(status().isUnauthorized());
    }

    @Test
    void issuesUsableDevTokens() throws Exception {
        MvcResult result = mvc.perform(post("/api/auth/dev-token").contentType(MediaType.APPLICATION_JSON)
                        .content("{\"username\":\"badr\",\"role\":\"admin\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.expiresAt").exists())
                .andReturn();
        String token = json.readTree(result.getResponse().getContentAsString()).get("token").asText();

        mvc.perform(get("/api/models/versions").header("Authorization", bearer(token))).andExpect(status().isOk());
        mvc.perform(post("/api/auth/dev-token").contentType(MediaType.APPLICATION_JSON)
                        .content("{\"username\":\"badr\",\"role\":\"root\"}"))
                .andExpect(status().isBadRequest());
        mvc.perform(post("/api/auth/dev-token").contentType(MediaType.APPLICATION_JSON)
                        .content("{\"username\":\"\",\"role\":\"analyst\"}"))
                .andExpect(status().isBadRequest());
    }

    @Test
    void acceptsQueryTokensOnlyOnStreams() throws Exception {
        String token = tokens.issue("ana", Role.ANALYST).token();

        mvc.perform(get("/api/alerts").param("access_token", token)).andExpect(status().isUnauthorized());
        mvc.perform(get("/api/stream/unknown")).andExpect(status().isUnauthorized());
        mvc.perform(get("/api/stream/unknown").param("access_token", token)).andExpect(status().isNotFound());
    }

    @Test
    void allowsCorsPreflightFromTheFrontendOnly() throws Exception {
        mvc.perform(options("/api/alerts")
                        .header("Origin", "http://localhost:3000")
                        .header("Access-Control-Request-Method", "PATCH")
                        .header("Access-Control-Request-Headers", "authorization,content-type"))
                .andExpect(status().isOk())
                .andExpect(header().string("Access-Control-Allow-Origin", "http://localhost:3000"));
        mvc.perform(options("/api/alerts")
                        .header("Origin", "https://evil.example")
                        .header("Access-Control-Request-Method", "GET"))
                .andExpect(status().isForbidden());
    }

    private static String sign(JwtEncoder encoder, List<String> roles, Instant expiresAt) {
        JwtClaimsSet claims = JwtClaimsSet.builder()
                .subject("someone")
                .issuedAt(expiresAt.minusSeconds(60))
                .expiresAt(expiresAt)
                .claim("roles", roles)
                .build();
        return encoder.encode(JwtEncoderParameters.from(JwsHeader.with(MacAlgorithm.HS256).build(), claims))
                .getTokenValue();
    }

    private static String bearer(String token) {
        return "Bearer " + token;
    }
}
