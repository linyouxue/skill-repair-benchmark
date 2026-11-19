#!/usr/bin/env bash
set -euo pipefail

# Build Apache Druid indexing-service (and its dependencies) from source.
#
# This script intentionally:
# - builds only the needed Maven modules (`-pl indexing-service -am`)
# - skips web-console (not in the selected modules)
# - skips quality gates & tests via Druid profiles
#
# Usage:
#   druid_build_indexing_service.sh
#
# Optional safety check:
#   Set REQUIRE_PATCHES=1 to fail fast if /root/patches has no *.patch files.

DRUID_DIR="${DRUID_DIR:-/root/druid}"
PATCH_DIR="${PATCH_DIR:-/root/patches}"
REQUIRE_PATCHES="${REQUIRE_PATCHES:-0}"

if [[ ! -f "$DRUID_DIR/pom.xml" ]]; then
  echo "ERROR: $DRUID_DIR does not look like a Druid checkout (missing pom.xml)." >&2
  exit 1
fi

if [[ "$REQUIRE_PATCHES" == "1" ]]; then
  # Avoid nullglob portability issues by using compgen.
  if ! compgen -G "$PATCH_DIR"'/*.patch' >/dev/null; then
    echo "ERROR: No patch files found in $PATCH_DIR (expected at least one *.patch)." >&2
    echo "Hint: use skills/jackson-security/scripts/druid_emit_patch.sh to create one." >&2
    exit 1
  fi
fi

mvn -f "$DRUID_DIR/pom.xml" \
  -pl indexing-service -am \
  clean package \
  -Pskip-static-checks -Pskip-tests
