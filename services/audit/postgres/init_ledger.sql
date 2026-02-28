-- This runs automatically when the postgres container starts for the first time.

-- Create the publication. A publication is a named set of tables
-- whose changes will be streamed. We only want the outbox table.
-- Debezium will create the replication slot itself when it connects.
CREATE PUBLICATION debezium_outbox_pub
    FOR TABLE journaux_outbox;
 
-- Grant the ledger_user user replication privileges.
-- In production, create a dedicated replication user instead.
ALTER ROLE ledger_user REPLICATION LOGIN;
