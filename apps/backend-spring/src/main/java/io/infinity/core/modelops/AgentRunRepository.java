package io.infinity.core.modelops;

import java.util.UUID;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;

public interface AgentRunRepository extends JpaRepository<AgentRun, UUID> {

    Page<AgentRun> findByStatus(AgentRunStatus status, Pageable pageable);
}
