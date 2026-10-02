#!/usr/bin/env bash
# Phase 1 demo: an honest MCP server, a tool-poisoning server and a rug pull.
# Everything runs locally; the only "secret" is a fake file this script writes.
set -euo pipefail
cd "$(dirname "$0")/.."

bold() { printf '\n\033[1m%s\033[0m\n' "$*"; }
pause() { [[ -t 0 ]] && read -rp $'\n[enter] to continue ' _ || true; }

make -s build-demos

bait_dir="$HOME/.ledgerline-demo"
mkdir -p "$bait_dir"
printf 'FAKE_API_KEY=demo-not-a-real-key\n' > "$bait_dir/fake-secrets.txt"
exfil="$bait_dir/attacker-received.log"
: > "$exfil"

bold "1. Honest server: tools/list, then tools/call get_weather"
./bin/demo-client --call get_weather --args '{"location":"Pune, IN","unit":"celsius"}' -- ./bin/weather
pause

bold "2. Tool poisoning: read the full description the MODEL sees"
echo "Most host UIs show only the first line: \"Adds two numbers.\""
./bin/demo-client -- ./bin/poisoned
pause

bold "   ...a hijacked model obeys and puts the file in 'sidenote':"
./bin/demo-client --call add \
  --args "{\"a\":2,\"b\":3,\"sidenote\":\"$(cat "$bait_dir/fake-secrets.txt")\"}" \
  -- ./bin/poisoned --exfil-log "$exfil" 2>/dev/null
echo; echo "Attacker received:"; cat "$exfil"
pause

bold "3. Rug pull: the tool looks harmless for 3 calls, then rewrites itself"
./bin/demo-client --call get_fact_of_the_day --repeat 4 -- ./bin/rugpull --after 3

bold "Takeaways"
cat <<'TXT'
- The model asks; the host does. Nothing stopped the poisoned call because
  nothing sits between "model wants X" and "X happens". (Phase 2 adds that.)
- The rug pull sent no list_changed notification to this client. Only
  re-listing revealed it, so pinning must re-check definitions on every list
  and before every call.
TXT
