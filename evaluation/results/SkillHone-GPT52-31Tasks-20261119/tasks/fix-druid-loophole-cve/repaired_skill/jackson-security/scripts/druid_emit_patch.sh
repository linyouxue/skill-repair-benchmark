#!/usr/bin/env bash
set -euo pipefail

# Emit a patch for changes made under a Druid source checkout.
#
# This helper exists because SkillHone-style tasks often require:
#   1) a patch file under /root/patches/
#   2) that patch to be applicable to /root/druid/
#
# Usage:
#   druid_emit_patch.sh <patch-file-name>.patch
#   druid_emit_patch.sh --init-git
#
# Notes:
# - If /root/druid is not already a git checkout, run --init-git *before editing*
#   to create a local baseline commit. After you make your code change(s), rerun
#   this script with a patch name to emit a non-empty patch.

DRUID_DIR="${DRUID_DIR:-/root/druid}"
PATCH_DIR="${PATCH_DIR:-/root/patches}"

usage() {
  cat >&2 <<'EOF'
Usage:
  druid_emit_patch.sh <patch-file-name>.patch
  druid_emit_patch.sh --init-git

Environment:
  DRUID_DIR   (default: /root/druid)
  PATCH_DIR   (default: /root/patches)
EOF
}

die() {
  echo "ERROR: $*" >&2
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Missing required command: $1"
}

is_git_worktree() {
  git -C "$DRUID_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1
}

has_head_commit() {
  git -C "$DRUID_DIR" rev-parse --verify HEAD >/dev/null 2>&1
}

init_git_baseline() {
  require_cmd git

  [[ -d "$DRUID_DIR" ]] || die "Druid source dir not found: $DRUID_DIR"

  if ! is_git_worktree; then
    git -C "$DRUID_DIR" init
  fi

  # Only create a baseline commit when there is no existing HEAD.
  if ! has_head_commit; then
    # Ensure a local identity exists so `git commit` succeeds.
    if ! git -C "$DRUID_DIR" config --get user.email >/dev/null 2>&1; then
      git -C "$DRUID_DIR" config user.email "skillhone@example.invalid"
    fi
    if ! git -C "$DRUID_DIR" config --get user.name >/dev/null 2>&1; then
      git -C "$DRUID_DIR" config user.name "SkillHone Local"
    fi

    git -C "$DRUID_DIR" add -A
    git -C "$DRUID_DIR" commit --no-gpg-sign -m "Baseline for patch generation"
  fi

  echo "Initialized git baseline in: $DRUID_DIR" >&2
  echo "Make your code changes, then run: druid_emit_patch.sh <name>.patch" >&2
}

if [[ $# -ne 1 ]]; then
  usage
  exit 2
fi

case "$1" in
  --help|-h)
    usage
    exit 0
    ;;
  --init-git)
    init_git_baseline
    exit 0
    ;;
esac

PATCH_NAME="$1"

if [[ "$PATCH_NAME" != *.patch ]]; then
  die "Patch filename must end in .patch (got: $PATCH_NAME)"
fi

require_cmd git

[[ -d "$DRUID_DIR" ]] || die "Druid source dir not found: $DRUID_DIR"
mkdir -p "$PATCH_DIR"

# For reliable diffs, we require a usable git worktree with a baseline commit.
if ! is_git_worktree || ! has_head_commit; then
  die "$DRUID_DIR is not a usable git checkout for diff generation. Run: druid_emit_patch.sh --init-git (BEFORE editing), or use a real git checkout."
fi

OUT_PATH="$PATCH_DIR/$PATCH_NAME"

# Use `git diff HEAD` so both staged and unstaged changes are captured.
git -C "$DRUID_DIR" diff HEAD > "$OUT_PATH"

if [[ ! -s "$OUT_PATH" ]]; then
  rm -f "$OUT_PATH"
  die "Generated patch was empty. Ensure you have made code changes under $DRUID_DIR before emitting the patch."
fi

echo "Wrote patch to: $OUT_PATH" >&2
