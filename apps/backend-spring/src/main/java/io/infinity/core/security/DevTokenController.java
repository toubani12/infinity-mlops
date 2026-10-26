package io.infinity.core.security;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import java.time.Instant;
import org.springframework.context.annotation.Profile;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

@RestController
@Profile("local")
public class DevTokenController {

    public record DevTokenRequest(@NotBlank @Size(max = 64) String username, @NotNull Role role) {
    }

    public record DevTokenResponse(String token, Instant expiresAt) {
    }

    private final TokenService tokens;

    public DevTokenController(TokenService tokens) {
        this.tokens = tokens;
    }

    @PostMapping("/api/auth/dev-token")
    public DevTokenResponse issue(@Valid @RequestBody DevTokenRequest request) {
        TokenService.IssuedToken issued = tokens.issue(request.username(), request.role());
        return new DevTokenResponse(issued.token(), issued.expiresAt());
    }
}
