-- pgbench script: indexed equality lookup on a key *inside* the value of the
-- PostgreSQL key-value store table.
--
-- This is the KV-store variant of query.sql: it runs against usertable(YCSB_KEY
-- VARCHAR PRIMARY KEY, YCSB_VALUE jsonb) — the exact schema YCSB's postgrenosql
-- binding uses to model Postgres as a key-value store. A btree expression index
-- on (YCSB_VALUE ->> 'field0') turns this equality filter into an index scan.
-- The :maxid variable is supplied by pgbench via `-D maxid=<rows-1>`.
\set k random(0, :maxid)
SELECT YCSB_VALUE FROM usertable WHERE YCSB_VALUE ->> 'field0' = 'key' || :k;
