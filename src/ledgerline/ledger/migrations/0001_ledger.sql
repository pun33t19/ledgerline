-- Ledger v1: an append-only, hash-chained table (ADR-007, ADR-008).
--
-- Two layers stop rewriting:
--   1. privileges: the application role may only INSERT and SELECT entries;
--   2. a trigger rejects UPDATE, DELETE and TRUNCATE for everyone, including the owner.
-- A superuser can still get around both (e.g. by disabling triggers). That is
-- what the hash chain is for: such an edit is *detected* by `ledgerline verify`.

CREATE TABLE ledger_entries (
    run_id      text        NOT NULL,
    seq         bigint      NOT NULL CHECK (seq >= 1),
    entry_hash  char(64)    NOT NULL,
    prev_hash   char(64)    NOT NULL,
    entry       jsonb       NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (run_id, seq),
    UNIQUE (run_id, prev_hash)  -- one successor per entry: the chain can't fork
);

-- Raw arguments, only when the proxy runs with --keep-args. Kept apart from the
-- chain so they can be deleted (erasure requests) without breaking any hash:
-- the entry keeps only an HMAC of them.
CREATE TABLE ledger_args (
    run_id text   NOT NULL,
    seq    bigint NOT NULL,
    args   jsonb  NOT NULL,
    PRIMARY KEY (run_id, seq),
    FOREIGN KEY (run_id, seq) REFERENCES ledger_entries (run_id, seq)
);

CREATE FUNCTION ledger_append_only() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'ledger_entries is append-only: % is not allowed', TG_OP
        USING ERRCODE = 'insufficient_privilege';
END
$$;

CREATE TRIGGER ledger_entries_no_rewrite
    BEFORE UPDATE OR DELETE ON ledger_entries
    FOR EACH ROW EXECUTE FUNCTION ledger_append_only();

CREATE TRIGGER ledger_entries_no_truncate
    BEFORE TRUNCATE ON ledger_entries
    FOR EACH STATEMENT EXECUTE FUNCTION ledger_append_only();

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'ledgerline_app') THEN
        CREATE ROLE ledgerline_app NOLOGIN;
    END IF;
END
$$;

REVOKE ALL ON ledger_entries, ledger_args FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO ledgerline_app;
GRANT SELECT, INSERT ON ledger_entries TO ledgerline_app;
GRANT SELECT, INSERT, DELETE ON ledger_args TO ledgerline_app;
