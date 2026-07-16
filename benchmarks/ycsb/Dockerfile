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
# image. curl fetches the release tarball; patch applies our postgrenosql fix.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates patch \
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

# Patch the postgrenosql binding to be thread-safe. Upstream shares one static
# JDBC Connection and one static PreparedStatement cache across every client
# thread, so our threadcount=8 fairness knob interleaves parameter writes on a
# single statement, corrupts the protocol stream and loads 0 rows — while YCSB
# still prints [OVERALL], so a total failure looks like a pass. Verified: 0/1000
# rows at threadcount=8 vs 1000/1000 at threadcount=1. The patch file carries the
# full rationale and evidence.
#
# The release tarball ships jars only, so fetch the single source file at the
# same pinned tag, patch it, and swap the recompiled class back into the binding
# jar. `patch` fails the build if upstream moves under us; the javap assertion
# fails the build if the recompile silently did not take effect.
COPY postgrenosql-threadsafe.patch /tmp/postgrenosql-threadsafe.patch

RUN set -eux; \
    ycsb_home="/opt/ycsb-${YCSB_VERSION}"; \
    jar_path="${ycsb_home}/postgrenosql-binding/lib/postgrenosql-binding-${YCSB_VERSION}.jar"; \
    src="/tmp/src/PostgreNoSQLDBClient.java"; \
    test -f "${jar_path}"; \
    mkdir -p /tmp/src /tmp/classes; \
    curl -fsSL "https://raw.githubusercontent.com/brianfrankcooper/YCSB/${YCSB_VERSION}/postgrenosql/src/main/java/site/ycsb/postgrenosql/PostgreNoSQLDBClient.java" \
      -o "${src}"; \
    patch "${src}" /tmp/postgrenosql-threadsafe.patch; \
    classpath="$(find "${ycsb_home}/lib" "${ycsb_home}/postgrenosql-binding/lib" -name '*.jar' | tr '\n' ':')"; \
    javac -nowarn -cp "${classpath}" -d /tmp/classes "${src}"; \
    (cd /tmp/classes && jar uf "${jar_path}" site/ycsb/postgrenosql); \
    javap -p -cp "${jar_path}" site.ycsb.postgrenosql.PostgreNoSQLDBClient > /tmp/javap.txt; \
    if grep -qE 'static +java\.sql\.Connection +connection' /tmp/javap.txt; then \
      echo 'PATCH VERIFY FAILED: connection is still a static (shared) field'; cat /tmp/javap.txt; exit 1; \
    fi; \
    grep -qE 'java\.sql\.Connection +connection' /tmp/javap.txt \
      || { echo 'PATCH VERIFY FAILED: connection field missing from patched class'; cat /tmp/javap.txt; exit 1; }; \
    echo 'postgrenosql thread-safety patch applied and verified'; \
    rm -rf /tmp/src /tmp/classes /tmp/javap.txt /tmp/postgrenosql-threadsafe.patch

WORKDIR /opt/ycsb
CMD ["sleep", "infinity"]
