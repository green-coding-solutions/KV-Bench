#!/usr/bin/env python3
"""
check_repo.py — Consistency checks for the KV-Bench repo.

The whole point of this repo is a *fair* comparison between key-value stores:
every store has to run with the same resource budget and the same benchmark
parameters, otherwise the energy/throughput numbers are not comparable.

Because GMT refuses to `!include` a compose file from a parent directory, each
benchmark folder (``benchmarks/ycsb/``, ``benchmarks/memtier/``) carries its own
copy of ``compose.yml`` next to the usage scenarios. Copies drift, so this script
enforces:

  1. Every ``compose.yml`` in the repo is byte-for-byte identical to the root one.
  2. Inside ``compose.yml`` every store service gets the same resource budget
     (``cpus`` and ``mem_limit``); the load drivers are intentionally
     unconstrained and are skipped.
  3. For each benchmark, the per-store driver configs use the same fairness knobs
     (record/operation counts, client/thread counts, ...) across all stores.
  4. The generated usage scenarios are up to date (``gen_scenarios.py --check``).

Exit code is 0 when everything is consistent, 1 otherwise. Run it from anywhere.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent

# Stores that take part in a benchmark, keyed by the repo's short name. The value
# is the compose service name (differs only for Postgres).
STORE_SERVICE = {
    "redis": "redis",
    "valkey": "valkey",
    "keydb": "keydb",
    "dragonfly": "dragonfly",
    "memcached": "memcached",
    "pg": "postgres",
}
DRIVER_SERVICES = {"ycsb", "memtier"}

# memtier has no PostgreSQL profile (no RESP / memcache protocol).
YCSB_STORES = list(STORE_SERVICE)
MEMTIER_STORES = [s for s in STORE_SERVICE if s != "pg"]

# Fairness knobs to compare across stores. For YCSB they are keys in the
# .properties file; for memtier, variables in the .env file. Connection details
# (host/port/protocol/url) are deliberately excluded — they must differ.
YCSB_KNOBS = ["recordcount", "operationcount", "fieldcount", "fieldlength", "threadcount"]
MEMTIER_KNOBS = [
    "MEMTIER_CLIENTS", "MEMTIER_THREADS", "MEMTIER_TEST_TIME",
    "MEMTIER_RATIO", "MEMTIER_DATA_SIZE", "MEMTIER_KEY_MAX",
]

errors: list[str] = []


def err(msg: str) -> None:
    errors.append(msg)


def parse_kv(path: Path) -> dict[str, str]:
    """Parse a simple key=value file (.properties / .env), ignoring comments."""
    out: dict[str, str] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def check_compose_copies() -> None:
    root = REPO / "compose.yml"
    root_bytes = root.read_bytes()
    copies = sorted((REPO / "benchmarks").glob("*/compose.yml"))
    if not copies:
        err("no per-benchmark compose.yml copies found under benchmarks/")
    for copy in copies:
        if copy.read_bytes() != root_bytes:
            err(f"{copy.relative_to(REPO)} differs from root compose.yml "
                f"(re-run ./gen_scenarios.py)")


def check_resource_budget() -> None:
    compose = yaml.safe_load((REPO / "compose.yml").read_text())
    services = compose.get("services", {})
    budgets: dict[str, tuple] = {}
    for name in STORE_SERVICE.values():
        svc = services.get(name)
        if svc is None:
            err(f"compose.yml is missing store service '{name}'")
            continue
        budgets[name] = (svc.get("cpus"), svc.get("mem_limit"))
        if svc.get("cpus") is None or svc.get("mem_limit") is None:
            err(f"service '{name}' must set both cpus and mem_limit")
    distinct = set(budgets.values())
    if len(distinct) > 1:
        err(f"store services have unequal resource budgets: {budgets}")


def check_driver_knobs(stores: list[str], subdir: str, ext: str, knobs: list[str]) -> None:
    """Every store's config file must agree on the fairness knobs."""
    seen: dict[str, dict[str, str]] = {}
    for store in stores:
        path = REPO / "db" / store / subdir / f"{store}_{subdir}{ext}"
        if not path.exists():
            err(f"missing config: {path.relative_to(REPO)}")
            continue
        cfg = parse_kv(path)
        missing = [k for k in knobs if k not in cfg]
        if missing:
            err(f"{path.relative_to(REPO)} is missing knobs: {', '.join(missing)}")
        seen[store] = {k: cfg.get(k) for k in knobs}
    for knob in knobs:
        values = {store: cfg.get(knob) for store, cfg in seen.items()}
        if len(set(values.values())) > 1:
            err(f"[{subdir}] knob '{knob}' differs across stores: {values}")


def check_generated_fresh() -> None:
    res = subprocess.run(
        [sys.executable, str(REPO / "gen_scenarios.py"), "--check"],
        capture_output=True, text=True,
    )
    if res.returncode != 0:
        err("generated scenarios are stale — run ./gen_scenarios.py\n"
            + res.stdout + res.stderr)


def main() -> int:
    check_compose_copies()
    check_resource_budget()
    check_driver_knobs(YCSB_STORES, "ycsb", ".properties", YCSB_KNOBS)
    check_driver_knobs(MEMTIER_STORES, "memtier", ".env", MEMTIER_KNOBS)
    check_generated_fresh()

    if errors:
        print("check_repo: FAIL", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print("check_repo: OK — compose copies, resource budgets and fairness knobs are consistent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
