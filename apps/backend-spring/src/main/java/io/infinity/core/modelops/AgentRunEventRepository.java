package io.infinity.core.modelops;

import java.util.List;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface AgentRunEventRepository extends JpaRepository<AgentRunEvent, UUID> {

    List<AgentRunEvent> findByRunIdOrderBySeqAsc(UUID runId);
}
