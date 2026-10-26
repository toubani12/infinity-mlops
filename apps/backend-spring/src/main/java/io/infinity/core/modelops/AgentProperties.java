package io.infinity.core.modelops;

import java.time.Duration;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.boot.context.properties.bind.DefaultValue;

@ConfigurationProperties("infinity.agent")
public record AgentProperties(
        @DefaultValue("50") double maxP95LatencyMs,
        @DefaultValue("5s") Duration commandTimeout) {
}
