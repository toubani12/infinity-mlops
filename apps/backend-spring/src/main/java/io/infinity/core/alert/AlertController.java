package io.infinity.core.alert;

import io.infinity.core.config.PageResponse;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import java.util.UUID;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/alerts")
public class AlertController {

    private final AlertService service;

    public AlertController(AlertService service) {
        this.service = service;
    }

    @GetMapping
    public PageResponse<AlertResponse> list(
            @RequestParam(defaultValue = "0") @Min(0) int page,
            @RequestParam(defaultValue = "50") @Min(1) @Max(200) int size,
            @RequestParam(required = false) AlertStatus status) {
        return PageResponse.of(service.list(status, page, size), AlertResponse::from);
    }

    @PatchMapping("/{id}")
    public AlertResponse update(@PathVariable UUID id, @Valid @RequestBody UpdateAlertRequest request) {
        return AlertResponse.from(service.updateStatus(id, request.status()));
    }
}
