package io.infinity.core.modelops;

import io.infinity.core.config.PageResponse;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import java.util.UUID;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/agent/runs")
public class AgentRunController {

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
}
