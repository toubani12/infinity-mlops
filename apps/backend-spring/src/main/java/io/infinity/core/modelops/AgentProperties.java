package io.infinity.core.modelops;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.boot.context.properties.bind.DefaultValue;

@ConfigurationProperties("infinity.agent")
public record AgentProperties(@DefaultValue("50") double maxP95LatencyMs) {
}
