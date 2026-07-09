# KV-Bench

A tool that benchmarks various key-value stores against each other and looks at energy usage,
using the [Green Metrics Tool](https://www.green-coding.io/) (GMT). It is the key-value-store
sibling of [DBMS-bench](../DBMS-bench) and follows the same conventions.

The `compose.yml` defines all the containers we benchmark: the standard upstream image for each
store plus one load-driver container per benchmark family.

- [YCSB](https://github.com/brianfrankcooper/YCSB) — the Yahoo! Cloud Serving Benchmark
  (Cooper et al., SoCC 2010), the canonical peer-reviewed cloud/KV benchmark. One built image
  (`ribalba/ycsb`) drives every store via the appropriate binding, so the same driver runs the
  same workloads everywhere — see [YCSB setup](#ycsb-setup).
- [memtier_benchmark](https://github.com/RedisLabs/memtier_benchmark) — Redis Inc.'s
  industry-standard RESP/Memcached throughput+latency generator. Uses the official
  `redislabs/memtier_benchmark` image.

## Stores under test

| Store | Image | Role |
|-------|-------|------|
| **Redis** | `redis:8.2` | Original in-memory KV store (now AGPLv3) |
| **Valkey** | `valkey/valkey:9.1` | Linux Foundation fork of Redis (BSD) |
| **KeyDB** | `eqalpha/keydb:latest` | Multithreaded Redis fork (Snap) |
| **Dragonfly** | `docker.dragonflydb.io/dragonflydb/dragonfly:latest` | Modern C++ shared-nothing rewrite |
| **Memcached** | `memcached:1.6-bookworm` | Classic multithreaded cache |
| **PostgreSQL** | `postgres:18.4-trixie` | Relational engine used *as a KV store* (JSONB) |

Redis, Valkey, KeyDB and Dragonfly all speak the Redis protocol (RESP), so they share the same
YCSB `redis` binding and the same memtier configuration — a clean Redis-vs-forks-vs-rewrite
comparison. Memcached uses YCSB's `memcached` binding / memtier's `memcache_text` protocol.
PostgreSQL is benchmarked through YCSB's `postgrenosql` binding, which stores every record as a
row in a single `usertable(YCSB_KEY text PRIMARY KEY, YCSB_VALUE jsonb)` — i.e. Postgres exercised
as a key-value/document store, not relationally. PostgreSQL therefore appears only in the YCSB
family (it has no RESP/Memcached protocol, so no memtier profile).

> KeyDB and Dragonfly publish no clean semver Docker tags, so they use `latest`. Pin them to a
> digest before a paper run for reproducibility.

## Layout

The repo is split into two trees, exactly like DBMS-bench:

- `benchmarks/` holds the GMT usage scenarios, one folder per benchmark family
  (`benchmarks/ycsb/`, `benchmarks/memtier/`, `benchmarks/pgjsonb/`).
- `db/` holds the per-store driver configuration, one folder per store
  (`db/redis/ycsb/redis_ycsb.properties`, `db/redis/memtier/redis_memtier.env`, …).

For each store and benchmark there is a `benchmarks/<benchmark>/<store>.yml` (e.g.
`benchmarks/ycsb/redis.yml`, `benchmarks/memtier/valkey.yml`) that you run with GMT to get
energy readings.

### Generated scenarios

Six stores × two drivers × two tuning tiers is too much near-identical YAML to keep in sync by
hand, so the usage scenarios are **generated** by [`gen_scenarios.py`](gen_scenarios.py) and
committed. The generator is the source of truth for the benchmark *flow* (which guarantees every
store runs byte-identical steps); the per-store *configuration* lives in `db/<store>/…`.

```sh
./gen_scenarios.py          # regenerate benchmarks/*/*.yml + the compose.yml copies
./gen_scenarios.py --check  # CI: fail if the committed files are stale
```

Each benchmark directory keeps its **own copy of `compose.yml`** (`benchmarks/ycsb/compose.yml`,
`benchmarks/memtier/compose.yml`): GMT's `!include` only resolves files inside the scenario's own
directory. `gen_scenarios.py` writes those copies from the root `compose.yml`, which is the single
source of truth. `check_repo.py` enforces that they never drift.

## The benchmarks

### YCSB (`benchmarks/ycsb/`)

Loads a ~1 GB dataset (1,000,000 records × 10 × 100-byte fields) and then runs the YCSB **core
workloads** in the canonical single-load order:

- **A** — 50/50 read/update
- **B** — 95/5 read-heavy
- **C** — 100% read
- **F** — read-modify-write
- **D** — read-latest (inserts new records last)

The SCI functional unit is `ycsb_ops` — YCSB operations completed across the five measured run
phases (energy per operation). Workload **E** (short scans) is omitted from the default flow: the
Memcached binding cannot scan, so including it would make the stores do unequal work. See
[TUNING.md](TUNING.md).

### memtier (`benchmarks/memtier/`)

Warms up by populating the whole key range, then runs a mixed GET/SET workload (`--ratio=1:10`,
50 clients × 4 threads, 60 s) at max throughput. The SCI functional unit is `memtier_ops` —
operations completed in the measured run. Covers the RESP family + Memcached (not PostgreSQL).

### PostgreSQL JSONB query (`benchmarks/pgjsonb/`) — PostgreSQL only

Where the YCSB/memtier benchmarks fetch a value *by key*, this one queries by a key *inside* the
value — the thing pure KV stores cannot do and PostgreSQL's document-store side can. It loads
1,000,000 JSONB documents (`{"field0": "key<i>", "category": …, "payload": …}`), builds a **btree
expression index** on the inner key (`CREATE INDEX … ON docs ((doc ->> 'field0'))`), and then runs
`pgbench` (bundled in the postgres image) doing indexed equality lookups on that inner key for 60 s
(8 clients × 4 jobs). The SCI functional unit is `jsonb_queries` — indexed lookups completed.

This is intentionally **not** part of the cross-store comparison: YCSB's key-only `postgrenosql`
binding never issues such a query, and there is no Redis/Memcached analog. `pgbench` runs
co-located inside `postgres_container`; see [TUNING.md](TUNING.md) for that trade-off.

There are two variants (each with a `.t1.yml` tier), differing only in the table they run against:

- **`pg.yml`** — a bespoke document table `docs(id bigint PK, doc jsonb)`.
- **`pgkv.yml`** — the **PostgreSQL key-value store** schema `usertable(YCSB_KEY text PK,
  YCSB_VALUE jsonb)` — the exact layout YCSB's `postgrenosql` binding uses to model Postgres as a
  KV store — indexed and queried on the inner key `YCSB_VALUE ->> 'field0'`. This measures the same
  indexed-JSONB-lookup workload on the same representation the rest of KV-Bench uses for Postgres.

Both share the `jsonb_queries` functional unit and the pgbench knobs in `db/pg/pgjsonb/pg_pgjsonb.env`;
their query scripts are `db/pg/pgjsonb/query.sql` and `query_kv.sql`.

## Tuning tiers

To study energy vs. tuning effort, each scenario comes in tiers. Tier files sit next to the
default and share the default's flow (only the *store configuration* changes between tiers), so
`run_on_cluster.py` discovers them automatically:

- **T0 — default**: `benchmarks/<benchmark>/<store>.yml` (stock container).
- **T1 — envelope-sized**: `benchmarks/<benchmark>/<store>.t1.yml` — each store's own
  rules-of-thumb sized to the fixed 4-CPU / 8-GB container (Redis/Valkey `maxmemory=6gb` +
  I/O threads, Memcached `-m 6144 -t 4`, Postgres `shared_buffers=2GB`, …). Durability is left
  at default so the T0→T1 delta is pure resource sizing.

```sh
# default vs. envelope-sized, Redis YCSB
./run_on_cluster.py --machine-id N --filter 'ycsb/redis.yml'
./run_on_cluster.py --machine-id N --filter 'ycsb/redis.t1.yml'
./run_on_cluster.py --machine-id N -t 0                    # every T0 scenario
./run_on_cluster.py --machine-id N -t 1                    # every T1 scenario
./run_on_cluster.py --machine-id N -t 0 -n                 # preview without submitting
```

See [TUNING.md](TUNING.md) for per-store settings, provenance and threats to validity (stock
Memcached's 64 MB cap, `maxmemory-policy` eviction, `latest` image tags).

## YCSB setup

The YCSB scenarios are driven by a `ycsb` container built from
[`benchmarks/ycsb/Dockerfile`](benchmarks/ycsb/Dockerfile): it bakes YCSB with the redis,
memcached and postgrenosql bindings (the release tarball bundles each binding's client driver,
including the Postgres JDBC driver) and idles via `sleep infinity` so GMT can exec the measured
runs into it. Build + push it once, like DBMS-bench's driver images:

```sh
docker login                          # as the account that owns the image (ribalba)
./benchmarks/ycsb/build-image.sh      # builds + pushes ribalba/ycsb:latest
YCSB_VERSION=0.17.0 ./benchmarks/ycsb/build-image.sh   # pin a version for a paper build
```

The memtier scenarios need no build — they use the upstream `redislabs/memtier_benchmark:latest`
image (its entrypoint is overridden to idle so GMT can exec into it).

## Consistency checks

`check_repo.py` enforces that the comparison stays fair:

```sh
python3 check_repo.py
```

1. Every `compose.yml` copy is byte-identical to the root.
2. Every store service has the same `cpus` / `mem_limit`.
3. Every store's YCSB properties / memtier env agree on the fairness knobs (record & operation
   counts, client & thread counts, …).
4. The generated scenarios are up to date.

## Some background reading

- YCSB paper (Cooper et al., SoCC 2010): https://doi.org/10.1145/1807128.1807152
- YCSB core workloads: https://github.com/brianfrankcooper/YCSB/wiki/Core-Workloads
- memtier_benchmark: https://github.com/RedisLabs/memtier_benchmark
- Valkey (the Redis fork): https://valkey.io/
- Dragonfly: https://www.dragonflydb.io/
- YCSB postgrenosql binding: https://github.com/brianfrankcooper/YCSB/tree/master/postgrenosql
