# YCSB load driver for KV-Bench.
#
# Bakes the Yahoo! Cloud Serving Benchmark (Cooper et al., SoCC 2010) with the
# bindings we need — redis (Redis/Valkey/KeyDB/Dragonfly), memcached and
# postgrenosql (PostgreSQL-as-KV via JSONB). The full release tarball bundles
# every binding jar plus each binding's client driver (incl. the Postgres JDBC
# driver used by postgrenosql), so no extra downloads are needed.
#
# The container idles via `sleep infinity`; GMT execs the measured `ycsb`
# invocations into it (same idle-driver pattern the DB containers rely on).
FROM eclipse-temurin:17-jdk-jammy

ARG YCSB_VERSION=0.17.0

# YCSB's bin/ycsb launcher is a Python script invoked as `python`; symlink it to
# python3. curl fetches the release tarball.
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 curl ca-certificates \
    && ln -sf /usr/bin/python3 /usr/local/bin/python \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL "https://github.com/brianfrankcooper/YCSB/releases/download/${YCSB_VERSION}/ycsb-${YCSB_VERSION}.tar.gz" \
      | tar -xz -C /opt \
    && ln -s "/opt/ycsb-${YCSB_VERSION}" /opt/ycsb

WORKDIR /opt/ycsb
CMD ["sleep", "infinity"]
