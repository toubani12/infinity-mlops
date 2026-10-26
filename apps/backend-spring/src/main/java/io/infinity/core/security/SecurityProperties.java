package io.infinity.core.security;

import java.time.Duration;
import java.util.List;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.boot.context.properties.bind.DefaultValue;

@ConfigurationProperties("infinity.security")
public record SecurityProperties(
        String jwtSecret,
        @DefaultValue("http://localhost:3000") List<String> allowedOrigins,
        @DefaultValue("8h") Duration tokenTtl) {
}
