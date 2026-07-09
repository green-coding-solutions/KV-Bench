# Tuning tiers

KV-Bench studies **energy vs. tuning effort**: the same workload is run against each store at
increasing levels of configuration effort. Only the *store configuration* changes between tiers —
the benchmark flow, the resource budget (4 CPU / 8 GB) and the workload knobs are held fixed, so
a T0→T1 delta isolates the effect of tuning.

The tuning lives in the generated `benchmarks/<benchmark>/<store>.t1.yml` files as a `command:`
override merged over the store's compose service (image / cpus / mem_limit / healthcheck are
inherited unchanged). To change it, edit `T1_COMMAND` in [`gen_scenarios.py`](gen_scenarios.py)
and regenerate.

## T0 — default (stock container)

Every store runs its upstream image with **no configuration**. This is the "out of the box"
baseline. Note that "stock" is not the same as "sensible" — see the threats to validity below.

## T1 — envelope-sized

Each store's own rules-of-thumb, sized to the fixed 4-CPU / 8-GB container. Durability/persistence
is left at each engine's default so the T0→T1 delta is pure resource sizing, not a safety trade.

| Store | T1 configuration | Rationale |
|-------|------------------|-----------|
| Redis | `--maxmemory 6gb --maxmemory-policy allkeys-lru --io-threads 4` | Bound memory below the container limit; enable Redis 6+ threaded I/O on the 4 cores |
| Valkey | `--maxmemory 6gb --maxmemory-policy allkeys-lru --io-threads 4` | Same as Redis (Valkey is the BSD fork) |
| KeyDB | `--maxmemory 6gb --maxmemory-policy allkeys-lru --server-threads 4` | KeyDB's multithreading knob is `server-threads`, not `io-threads` |
| Dragonfly | `--maxmemory=6gb --proactor_threads=4 --cache_mode=true` | Bound memory; pin proactor threads to the cores; cache-mode LRU eviction |
| Memcached | `-m 6144 -t 4` | Raise the slab budget from the 64 MB default to ~6 GB; 4 worker threads |
| PostgreSQL | `shared_buffers=2GB`, `effective_cache_size=6GB`, SSD I/O costs, parallel workers = cores | Standard PGTune-style sizing (25 %/75 % RAM), same as DBMS-bench's `pg.t1` |

`maxmemory` is set to 6 GB (not the full 8 GB `mem_limit`) to leave headroom for the process's
own overhead and avoid the container OOM-killer — the same reason Postgres's `shared_buffers` is
25 % of RAM.

## Threats to validity

- **Stock Memcached caps at 64 MB.** The default `memcached` command is `-m 64`, far below the
  ~1 GB YCSB working set, so under T0 almost every read misses and evictions dominate. YCSB still
  completes its operations (a miss is a valid op), so the functional unit is unaffected, but the
  T0 Memcached number reflects a cache that cannot hold the data. This is the intended untuned
  baseline; T1 (`-m 6144`) is where Memcached can actually cache the dataset. Read the two tiers
  together.
- **Eviction policy under memory pressure.** T1 sets `allkeys-lru` on the RESP stores so a
  working set at/above the `maxmemory` bound evicts rather than erroring. T0 has no `maxmemory`, so
  the in-memory stores grow until the 8 GB container limit — at the 1 GB dataset this is fine, but
  raising `recordcount` could OOM a T0 in-memory store before T1.
- **`latest` image tags.** KeyDB and Dragonfly have no clean semver tags on their registries, so
  `compose.yml` pins them to `latest`. For a reproducible paper build, resolve and pin the image
  digests first. Redis/Valkey/Memcached/Postgres are pinned to explicit versions.
- **YCSB workload E is excluded.** The default flow runs A, B, C, F, D. Workload E is scan-heavy
  and the YCSB Memcached binding does not implement scans, so including it would make the stores
  do unequal work. If you drop Memcached from a run you can add E back (it needs its own load
  because it inserts with a scan-oriented key order).
- **PostgreSQL is not a native KV store.** It is measured through YCSB's `postgrenosql` binding
  (one JSONB row per record). Its numbers reflect a general-purpose relational engine emulating a
  KV store — informative as a baseline, not a like-for-like in-memory comparison. JDBC round-trip
  overhead is part of what is measured.
- **pgbench is co-located (pgjsonb only).** The PostgreSQL JSONB-query benchmark runs `pgbench`
  inside `postgres_container` (the postgres image ships pgbench), so the client shares the store's
  4-CPU budget rather than running in a separate unconstrained driver like YCSB/memtier. This
  slightly understates PostgreSQL's achievable query throughput, but it is a *constant* across the
  compared runs (T0 vs T1, or index vs no-index), so it does not bias those comparisons. The
  measured energy includes the co-located client's small overhead. Do not compare `jsonb_queries`
  numbers against the driver-separated YCSB/memtier results.
- **The pgjsonb index is the point, not a tier.** `docs_field0_idx` (a btree expression index on
  `doc ->> 'field0'`) is created in the flow itself, not as a T1 knob — without it the equality
  lookup is a full sequential scan over 1,000,000 rows. To measure the index's effect, run the
  scenario with the `CREATE INDEX` step removed as an ad-hoc baseline; expect orders-of-magnitude
  fewer `jsonb_queries`.
- **Driver placement.** The load drivers (`ycsb`, `memtier`) are left unconstrained and run in the
  same compose network as the store. On a single-host measurement the driver competes with the
  store for the machine's remaining cores; keep the driver's thread/client counts (the fairness
  knobs) well below the host core count so the store, not the driver, is the bottleneck.

## Planned tiers (not yet implemented)

- **T2 — workload-aware**: per-workload tuning (e.g. Redis `appendonly`/`save` policy for the
  write-heavy workloads, Postgres `work_mem`/`synchronous_commit` trade-offs), mirroring
  DBMS-bench's T2.
