# YCSB load driver for KV-Bench.
#
# Bakes the Yahoo! Cloud Serving Benchmark (Cooper et al., SoCC 2010) with the
# bindings we need — redis (Redis/Valkey/KeyDB/Dragonfly), memcached and
# postgrenosql (PostgreSQL-as-KV via JSONB). The full release tarball bundles
# every binding jar plus each binding's client driver, but the postgrenosql
# binding ships an ancient Postgres JDBC driver (postgresql-9.4.1212.jre7.jar,
# 2016) that predates SCRAM-SHA-256 support. Postgres 14+ (we run 18) hashes
# passwords with scram-sha-256 by default, so that driver fails the handshake
# with "authentication type 10 is not supported". We swap in a modern pgjdbc.
#
# The container idles via `sleep infinity`; GMT execs the measured `ycsb`
# invocations into it (same idle-driver pattern the DB containers rely on).
FROM eclipse-temurin:17-jdk-jammy

ARG YCSB_VERSION=0.17.0
# pgjdbc 42.2.0+ speaks SCRAM; pin a recent 42.7.x. Runs only in the load
# driver, not the measured Postgres SUT, so it does not affect fairness.
ARG PG_JDBC_VERSION=42.7.4

# The scenarios invoke `bin/ycsb.sh`, not the Python `bin/ycsb` launcher: the
# latter is Python 2 only (`except E, err:`) and no Python 2 ships in this base
# image. curl fetches the release tarball.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL "https://github.com/brianfrankcooper/YCSB/releases/download/${YCSB_VERSION}/ycsb-${YCSB_VERSION}.tar.gz" \
      | tar -xz -C /opt \
    && ln -s "/opt/ycsb-${YCSB_VERSION}" /opt/ycsb

# Replace the bundled 2016 JDBC driver with a SCRAM-capable one. Remove the old
# jar so it does not linger on the glob-built binding classpath. Fetched from
# Maven Central (reliable for scripted builds).
RUN rm -f /opt/ycsb/postgrenosql-binding/lib/postgresql-9.4*.jar \
    && curl -fsSL \
      "https://repo1.maven.org/maven2/org/postgresql/postgresql/${PG_JDBC_VERSION}/postgresql-${PG_JDBC_VERSION}.jar" \
      -o "/opt/ycsb/postgrenosql-binding/lib/postgresql-${PG_JDBC_VERSION}.jar"

WORKDIR /opt/ycsb
CMD ["sleep", "infinity"]
