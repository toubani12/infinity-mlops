-- The transactions table doubles as the outbox for transaction.raw: a row is pending until published_at is set.
ALTER TABLE transactions ADD COLUMN published_at TIMESTAMP WITH TIME ZONE;

CREATE INDEX idx_transactions_publication ON transactions (published_at, received_at);
