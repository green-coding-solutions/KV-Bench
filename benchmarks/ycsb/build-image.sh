#!/usr/bin/env sh
# Build and push the YCSB load-driver image (ribalba/ycsb:latest) referenced by
# the YCSB usage scenarios. One-time, like DBMS-bench's benchbase/hammerdb-db2
# images. Requires `docker login` as the account that owns the image (ribalba).
#
#   ./benchmarks/ycsb/build-image.sh                 # latest YCSB (0.17.0)
#   YCSB_VERSION=0.17.0 ./benchmarks/ycsb/build-image.sh
#
# Pin a version for a reproducible paper build.
set -eu

IMAGE="${IMAGE:-ribalba/ycsb:latest}"
YCSB_VERSION="${YCSB_VERSION:-0.17.0}"

DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

docker build \
  --build-arg "YCSB_VERSION=${YCSB_VERSION}" \
  -t "${IMAGE}" \
  "${DIR}"

docker push "${IMAGE}"
echo "pushed ${IMAGE} (YCSB ${YCSB_VERSION})"
