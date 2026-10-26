package io.infinity.core.stream;

import java.time.Duration;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.boot.context.properties.bind.DefaultValue;

@ConfigurationProperties("infinity.stream")
public record StreamProperties(
        @DefaultValue("30m") Duration timeout,
        @DefaultValue("3s") Duration reconnect,
        @DefaultValue("15000") long heartbeatMs) {
}
