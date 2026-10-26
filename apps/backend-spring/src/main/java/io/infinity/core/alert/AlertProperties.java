package io.infinity.core.alert;

import jakarta.validation.constraints.DecimalMax;
import jakarta.validation.constraints.DecimalMin;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.boot.context.properties.bind.DefaultValue;
import org.springframework.validation.annotation.Validated;

@Validated
@ConfigurationProperties("infinity.alerts")
public record AlertProperties(@DefaultValue("0.5") @DecimalMin("0") @DecimalMax("1") double threshold) {
}
