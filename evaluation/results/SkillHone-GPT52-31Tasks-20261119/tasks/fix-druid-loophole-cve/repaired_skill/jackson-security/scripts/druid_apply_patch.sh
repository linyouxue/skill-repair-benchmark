#!/usr/bin/env bash
set -euo pipefail

# Apply a patch to a Druid source checkout.
#
# Usage:
#   druid_apply_patch.sh /root/patches/<patch>.patch
#
# Notes:
# - Prefers `git apply` (even if the target isn't a git repo) because it provides
#   better diagnostics and consistent behavior.
# - If the patch is already applied, this script exits successfully.

DRUID_DIR="${DRUID_DIR:-/root/druid}"

usage() {
  echo "Usage: $0 <patch-path>" >&2
}

die() {
  echo "ERROR: $*" >&2
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Missing required command: $1"
}

if [[ $# -ne 1 ]]; then
  usage
  exit 2
fi

PATCH_PATH="$1"

[[ -f "$PATCH_PATH" ]] || die "Patch not found: $PATCH_PATH"
[[ -d "$DRUID_DIR" ]] || die "Druid source dir not found: $DRUID_DIR"

require_cmd git

# Try to apply; if it doesn't apply, check whether it's already applied.
if git -C "$DRUID_DIR" apply --check "$PATCH_PATH" >/dev/null 2>&1; then
  git -C "$DRUID_DIR" apply "$PATCH_PATH"
  echo "Applied patch: $PATCH_PATH" >&2
  exit 0
fi

# If the patch cannot be applied cleanly, but *is* already present, treat that as success.
if git -C "$DRUID_DIR" apply --reverse --check "$PATCH_PATH" >/dev/null 2>&1; then
  echo "Patch already applied: $PATCH_PATH" >&2
  exit 0
fi

# Fall back to `patch` only if git apply can't make sense of it (rare), and provide
# helpful diagnostics.
if command -v patch >/dev/null 2>&1; then
  if patch -p1 -d "$DRUID_DIR" --dry-run < "$PATCH_PATH" >/dev/null 2>&1; then
    patch -p1 -d "$DRUID_DIR" < "$PATCH_PATH"
    echo "Applied patch via 'patch': $PATCH_PATH" >&2
    exit 0
  fi
fi

die "Patch failed to apply cleanly (and does not appear to be already applied): $PATCH_PATH"
