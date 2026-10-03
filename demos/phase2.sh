#!/usr/bin/env bash
# Phase 2 demo: Ledgerline sits between client and server, pins tool
# definitions, and blocks a rug pull, including one the host never notices.
set -euo pipefail
cd "$(dirname "$0")/.."

bold() { printf '\n\033[1m%s\033[0m\n' "$*"; }
pause() { [[ -t 0 ]] && read -rp $'\n[enter] to continue ' _ || true; }

uv sync --quiet
bin=.venv/bin
work="$HOME/.ledgerline-demo/phase2"
mkdir -p "$work"
lock="$work/rugpull.lock"
log="$work/proxy-log.jsonl"
rm -f "$lock" "$log"

bold "1. Review and pin the server's tools (what a person approves)"
"$bin/ledgerline" pin --yes --lock "$lock" -- "$bin/demo-rugpull" --after 3
pause

bold "2. Same rug pull as Phase 1, but now through Ledgerline"
echo "   demo-client → ledgerline proxy stdio → demo-rugpull"
"$bin/demo-client" --call get_fact_of_the_day --repeat 4 -- \
  "$bin/ledgerline" proxy stdio --lock "$lock" --log "$log" -- "$bin/demo-rugpull" --after 3
pause

bold "3. A host that never re-reads the menu (the silent rug pull)"
echo "   Ledgerline asks the server for the tool's current definition before every call."
"$bin/demo-client" --no-relist --call get_fact_of_the_day --repeat 4 -- \
  "$bin/ledgerline" proxy stdio --lock "$lock" -- "$bin/demo-rugpull" --after 3 2>/dev/null
pause

bold "4. Why that check is on by default: switch it off and the rug pull gets through"
"$bin/demo-client" --no-relist --call get_fact_of_the_day --repeat 4 -- \
  "$bin/ledgerline" proxy stdio --no-verify-each-call --lock "$lock" -- "$bin/demo-rugpull" --after 3 2>/dev/null
pause

bold "5. What Ledgerline recorded (alerts from step 2)"
python3 - "$log" <<'PY'
import json, sys
for line in open(sys.argv[1]):
    record = json.loads(line)
    alert = record.get("alert")
    if alert:
        print("  %s  %-28s tool=%s" % (record["ts"], alert["event"], alert["tool"]))
PY

bold "Takeaways"
cat <<'TXT'
- Ledgerline forwards every normal message byte-for-byte; it only steps in
  when a tool no longer matches what a person approved.
- Changed tools are hidden from the menu, so the model never reads the new
  (poisoned) description, and calls to them are blocked before the server
  sees them.
- Pinning catches CHANGES. A server that is malicious from day one (like
  demo-poisoned) gets pinned as-is, which is why `ledgerline pin` shows every
  description in full for a person to read. Argument rules (Phase 5) and
  human approval (Phase 6) cover that case.
- This log is plain JSON anyone can edit. Phase 4 makes it tamper-evident.
TXT
