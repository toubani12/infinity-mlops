package io.infinity.core.modelops;

import io.infinity.core.config.PageResponse;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import java.util.UUID;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/agent/runs")
public class AgentRunController {

    public record RejectRequest(@NotNull @Size(min = 3, max = 500) String reason) {

        public RejectRequest {
            reason = reason == null ? null : reason.strip();
        }
    }

    private final AgentRunService service;

    public AgentRunController(AgentRunService service) {
        this.service = service;
    }

    @GetMapping
    public PageResponse<AgentRunResponse> list(
            @RequestParam(required = false) AgentRunStatus status,
            @RequestParam(defaultValue = "0") @Min(0) int page,
            @RequestParam(defaultValue = "20") @Min(1) @Max(200) int size) {
        return PageResponse.of(service.list(status, page, size), AgentRunResponse::from);
    }

    @GetMapping("/{runId}")
    public AgentRunDetailResponse detail(@PathVariable UUID runId) {
        return service.detail(runId);
    }

    @PostMapping("/{runId}/approve")
    public AgentRunResponse approve(@PathVariable UUID runId, Authentication user) {
        return AgentRunResponse.from(service.decide(runId, AgentCommand.Action.APPROVE, user.getName(), null));
    }

    @PostMapping("/{runId}/reject")
    public AgentRunResponse reject(
            @PathVariable UUID runId, @Valid @RequestBody RejectRequest request, Authentication user) {
        return AgentRunResponse.from(
                service.decide(runId, AgentCommand.Action.REJECT, user.getName(), request.reason()));
    }
}
