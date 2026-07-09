## Scope

This repository contains usage scenarios to be run with the Green Metrics Tool.

The purpose is to evaluate key-value-store energy usage on reference benchmarks — primarily
YCSB (the peer-reviewed Yahoo! Cloud Serving Benchmark) plus memtier_benchmark for the
RESP/Memcached family. PostgreSQL is included, benchmarked *as a key-value store* via YCSB's
`postgrenosql` binding.

## Golden rules

- The comparison must stay **fair**: every store runs the same benchmark flow with the same
  resource budget (`cpus`/`mem_limit`) and the same workload knobs. Only connection details and
  (in the T1 tier) the store's own configuration may differ.
- The scenario `benchmarks/*/*.yml` files are **generated** — never hand-edit them. Edit
  `gen_scenarios.py` (flow/structure) or the `db/<store>/…` config files (knobs), then run
  `./gen_scenarios.py` and commit the result.
- `compose.yml` is the single source of truth; the per-benchmark copies are written by the
  generator. Run `python3 check_repo.py` before committing — it must exit 0.

## Syntax Validation

Look at these for reference:
  - Simple: https://raw.githubusercontent.com/green-coding-solutions/green-metrics-tool/refs/heads/main/tests/data/usage_scenarios/internal_network.yml
  - Including SCI: https://raw.githubusercontent.com/green-coding-solutions/green-metrics-tool/refs/heads/main/tests/data/usage_scenarios/stress_custom_metrics.yml
  - Complex with Dockerfile build and Volume Mounts: https://raw.githubusercontent.com/green-coding-solutions/green-metrics-tool/refs/heads/main/tests/data/usage_scenarios/subdir_volume_loading/subdir/usage_scenario_subdir.yml
