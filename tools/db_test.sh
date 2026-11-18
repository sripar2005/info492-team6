#!/usr/bin/env bash
# Runs supabase/tests/visibility_test.sql against a throwaway local Postgres (port 5433, socket /tmp/pg).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; BIN=/usr/lib/postgresql/16/bin; DATA=/tmp/pg/d
if [ ! -d "$DATA" ]; then mkdir -p /tmp/pg && chown postgres /tmp/pg && sudo -u postgres $BIN/initdb -D $DATA >/dev/null; fi
sudo -u postgres $BIN/pg_ctl -D $DATA status >/dev/null 2>&1 || sudo -u postgres $BIN/pg_ctl -D $DATA -l /tmp/pg/log start -o "-k /tmp/pg -p 5433" >/dev/null
sleep 1
P="sudo -u postgres psql -h /tmp/pg -p 5433 -v ON_ERROR_STOP=1 -q -t"
$P -c "drop database if exists cs_test" -c "create database cs_test" >/dev/null
$P -d cs_test -f "$ROOT/supabase/tests/stub.sql" >/dev/null 2>&1
$P -d cs_test -f "$ROOT/supabase/migrations/0003_platform.sql" >/dev/null 2>&1
$P -d cs_test -f "$ROOT/supabase/tests/visibility_test.sql" 2>&1 | grep -oE "ok: .*|FAILED.*|ERROR.*|ALL VISIBILITY TESTS PASSED"
