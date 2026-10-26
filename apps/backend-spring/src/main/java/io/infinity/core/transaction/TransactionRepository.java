package io.infinity.core.transaction;

import java.util.List;
import java.util.UUID;
import org.springframework.data.domain.Limit;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;

public interface TransactionRepository extends JpaRepository<Transaction, UUID> {

    Page<Transaction> findByFraudTrue(Pageable pageable);

    List<Transaction> findByPublishedAtIsNullOrderByReceivedAtAsc(Limit limit);
}
