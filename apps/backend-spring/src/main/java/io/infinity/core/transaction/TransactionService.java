package io.infinity.core.transaction;

import io.infinity.core.config.ConflictException;
import io.infinity.core.config.NotFoundException;
import java.time.Clock;
import java.time.Instant;
import java.util.UUID;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Sort;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class TransactionService {

    private static final Sort NEWEST_FIRST = Sort.by(Sort.Direction.DESC, "receivedAt");

    private final TransactionRepository repository;
    private final Clock clock;

    public TransactionService(TransactionRepository repository, Clock clock) {
        this.repository = repository;
        this.clock = clock;
    }

    @Transactional
    public Transaction create(CreateTransactionRequest request) {
        UUID id = request.transactionId() != null ? request.transactionId() : UUID.randomUUID();
        if (repository.existsById(id)) {
            throw new ConflictException("Transaction " + id + " already exists");
        }
        Instant now = clock.instant();
        Instant occurredAt = request.timestamp() != null ? request.timestamp() : now;
        Transaction transaction = new Transaction(
                id, occurredAt, now, request.amount(), Features.toArray(request.features()), request.label());
        return repository.save(transaction);
    }

    @Transactional(readOnly = true)
    public Transaction get(UUID id) {
        return repository.findById(id).orElseThrow(() -> new NotFoundException("Transaction " + id + " not found"));
    }

    @Transactional(readOnly = true)
    public Page<Transaction> list(boolean fraudOnly, int page, int size) {
        PageRequest pageable = PageRequest.of(page, size, NEWEST_FIRST);
        return fraudOnly ? repository.findByFraudTrue(pageable) : repository.findAll(pageable);
    }
}
