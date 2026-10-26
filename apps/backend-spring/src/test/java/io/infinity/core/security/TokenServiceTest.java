package io.infinity.core.security;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;

class TokenServiceTest {

    private final JwtConfig config = new JwtConfig();
    private final SecurityProperties properties =
            new SecurityProperties("unit-secret-0123456789-0123456789-xyz", List.of(), Duration.ofHours(1));

    @Test
    void issuesTokensCarryingTheRole() {
        var key = config.jwtSigningKey(properties);
        Instant now = Instant.now();
        TokenService service = new TokenService(config.jwtEncoder(key), properties, Clock.fixed(now, ZoneOffset.UTC));
        JwtDecoder decoder = config.jwtDecoder(key);

        TokenService.IssuedToken issued = service.issue("badr", Role.ADMIN);
        Jwt jwt = decoder.decode(issued.token());
        JwtAuthenticationToken authentication = JwtConfig.toAuthentication(jwt);

        assertThat(jwt.getSubject()).isEqualTo("badr");
        assertThat(jwt.getClaimAsStringList("roles")).containsExactly("admin");
        assertThat(issued.expiresAt()).isEqualTo(now.plus(Duration.ofHours(1)));
        assertThat(authentication.getName()).isEqualTo("badr");
        assertThat(authentication.getAuthorities()).extracting(Object::toString).containsExactly("ROLE_ADMIN");
    }

    @Test
    void refusesShortSecrets() {
        assertThatThrownBy(() -> config.jwtSigningKey(new SecurityProperties("short", List.of(), Duration.ofHours(1))))
                .hasMessageContaining("JWT_SECRET");
        assertThatThrownBy(() -> config.jwtSigningKey(new SecurityProperties(null, List.of(), Duration.ofHours(1))))
                .isInstanceOf(IllegalStateException.class);
    }
}
