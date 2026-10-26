package io.infinity.core.modelops;

import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface ModelVersionEventRepository extends JpaRepository<ModelVersionEvent, UUID> {
}
