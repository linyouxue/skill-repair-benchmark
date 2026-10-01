#!/bin/bash
set -o pipefail
date -Is > /data1/linyuanjing/skillgrad_assets/fix-build-google-auto/exact-image-recovery-20260930/build-exact.started
docker build --network=host --progress=plain -t bf__fix-build-google-auto:latest /data1/linyuanjing/root_disk_migrated_20260923/emergency/home/linyuanjing/benchmark-executor-compat-20260828-001/skillsbench-v1.1/tasks/fix-build-google-auto/environment > /data1/linyuanjing/skillgrad_assets/fix-build-google-auto/exact-image-recovery-20260930/build-exact.log 2>&1
rc=$?
echo $rc > /data1/linyuanjing/skillgrad_assets/fix-build-google-auto/exact-image-recovery-20260930/build-exact.rc
date -Is > /data1/linyuanjing/skillgrad_assets/fix-build-google-auto/exact-image-recovery-20260930/build-exact.finished
exit $rc
