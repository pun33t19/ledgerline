#!/usr/bin/env bash
# Phase 4 demo: every tool call lands in a hash-chained Postgres ledger before it runs,
# and `ledgerline verify` points to the exact entry someone rewrote.
set -euo pipefail
cd "$(dirname "$0")/.."

bold() { printf '\n\033[1m%s\033[0m\n' "$*"; }
pause() { [[ -t 0 ]] && read -rp $'\n[enter] to continue ' _ || true; }

compose=(docker compose -f deploy/docker-compose.yml)
owner_url="postgresql://ledgerline:owner-dev-password@127.0.0.1:55432/ledgerline"
app_url="postgresql://ledgerline_app:app-dev-password@127.0.0.1:55432/ledgerline"
psql() { "${compose[@]}" exec -T postgres psql -U ledgerline -d ledgerline -v ON_ERROR_STOP=1 "$@"; }

uv sync --quiet
bin=.venv/bin
work="$HOME/.ledgerline-demo/phase4"
mkdir -p "$work"
lock="$work/rugpull.lock"
run="demo-$(date +%H%M%S)"

bold "1. Start Postgres and create the ledger tables (as the database owner)"
"${compose[@]}" up -d --wait
LEDGERLINE_APP_PASSWORD=app-dev-password "$bin/ledgerline" ledger migrate --ledger "$owner_url" \
  --app-password-env LEDGERLINE_APP_PASSWORD
pause

bold "2. Run the silent rug pull through Ledgerline, recording to the ledger as run $run"
"$bin/ledgerline" pin --yes --lock "$lock" -- "$bin/demo-rugpull" --after 3 >/dev/null
"$bin/demo-client" --no-relist --call get_fact_of_the_day --repeat 4 -- \
  "$bin/ledgerline" proxy stdio --lock "$lock" --ledger "$app_url" --run-id "$run" \
  --digest-key "$work/digest.key" -- "$bin/demo-rugpull" --after 3 2>/dev/null
pause

bold "3. What the ledger holds: three allowed calls and their results, then the blocked call"
psql -c "SELECT seq, entry->>'kind' AS kind, entry->>'tool' AS tool,
                coalesce(entry#>>'{decision,effect}', entry#>>'{outcome,status}') AS what,
                entry#>>'{decision,control}' AS control, left(entry_hash, 12) AS hash
         FROM ledger_entries WHERE run_id = '$run' ORDER BY seq"
pause

bold "4. Verify the chain"
"$bin/ledgerline" verify --run "$run" --ledger "$app_url"
pause

bold "5. The application's own account can't rewrite history"
psql -c "SET ROLE ledgerline_app; UPDATE ledger_entries SET entry = entry WHERE run_id = '$run'" \
  || echo "  → refused, as it should be"
pause

bold "6. A superuser can: switch triggers off and turn the blocked call into an allowed one"
psql -c "SET session_replication_role = replica;
         UPDATE ledger_entries
            SET entry = jsonb_set(entry, '{decision,effect}', '\"allow\"')
          WHERE run_id = '$run' AND entry#>>'{decision,effect}' = 'deny'"
pause

bold "7. Verify again: the edit is caught at exactly that entry"
"$bin/ledgerline" verify --run "$run" --ledger "$app_url" || true

bold "Takeaways"
cat <<'TXT'
- Each call is written (and committed) before it is forwarded; if the ledger is
  unavailable, the call is refused rather than run unrecorded.
- The app account can only append. Even a superuser who edits a row can't hide
  it: the entry's hash no longer matches its contents.
- Arguments are stored as an HMAC (keyed hash), so the ledger proves what was
  sent without revealing it. Raw arguments are only kept with --keep-args, in a
  separate table that can be erased without breaking the chain.
- Try it in the browser too: ./demos/phase3.sh, run an attack, open "Ledger".
- Stop Postgres: docker compose -f deploy/docker-compose.yml down   (add -v to delete the data)
TXT
