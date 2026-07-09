-- pgbench script: indexed equality lookup on a key *inside* a JSONB document.
--
-- Each row in `docs` is a JSONB document {"field0": "key<i>", "category": ..,
-- "payload": ..}. A btree expression index on (doc ->> 'field0') turns this
-- equality filter into an index scan — the whole point of the benchmark. The
-- :maxid variable is supplied by pgbench via `-D maxid=<rows-1>`.
\set k random(0, :maxid)
SELECT doc FROM docs WHERE doc ->> 'field0' = 'key' || :k;
