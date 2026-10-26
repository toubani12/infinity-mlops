package io.infinity.core.security;

import com.fasterxml.jackson.annotation.JsonValue;
import java.util.Locale;

public enum Role {
    ANALYST,
    ADMIN;

    @JsonValue
    public String claimValue() {
        return name().toLowerCase(Locale.ROOT);
    }
}
