package io.infinity.core.alert;

import io.infinity.core.config.ConflictException;
import io.infinity.core.config.NotFoundException;
import java.time.Clock;
import java.util.UUID;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Sort;
import org.springframework.lang.Nullable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class AlertService {

    private static final Sort NEWEST_FIRST = Sort.by(Sort.Direction.DESC, "createdAt");

    private final AlertRepository repository;
    private final Clock clock;

    public AlertService(AlertRepository repository, Clock clock) {
        this.repository = repository;
        this.clock = clock;
    }

    @Transactional(readOnly = true)
    public Page<Alert> list(@Nullable AlertStatus status, int page, int size) {
        PageRequest pageable = PageRequest.of(page, size, NEWEST_FIRST);
        return status == null ? repository.findAll(pageable) : repository.findByStatus(status, pageable);
    }

    @Transactional
    public Alert updateStatus(UUID id, AlertStatus target) {
        Alert alert = repository.findById(id).orElseThrow(() -> new NotFoundException("Alert " + id + " not found"));
        if (!alert.getStatus().canMoveTo(target)) {
            throw new ConflictException("Alert " + id + " is " + alert.getStatus() + " and cannot move to " + target);
        }
        alert.moveTo(target, clock.instant());
        return alert;
    }
}
