package io.infinity.core.alert;

import jakarta.validation.constraints.NotNull;

public record UpdateAlertRequest(@NotNull AlertStatus status) {
}
