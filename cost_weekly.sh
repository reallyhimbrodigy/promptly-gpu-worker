#!/usr/bin/env bash
# STANDING WEEKLY COST LINE — so cost never needs a human read again [Law 1].
#
# WHY A SEPARATE CLIENT. `modal billing` does not exist on client 1.2.6, which is
# what deploy.sh uses. Upgrading the global client mid-campaign would put the
# deploy path at risk to answer a reporting question, so this pins its own
# isolated venv and leaves the deploy client alone.
#
#   ./cost_weekly.sh              # last 7 days
#   ./cost_weekly.sh 3            # last N days
#
# Emits: total, $/day, per-app and per-resource shares, and the daily series.
set -uo pipefail

DAYS="${1:-7}"
VENV="${PROMPTLY_BILLING_VENV:-/tmp/modalbill_venv}"

if [ ! -x "$VENV/bin/modal" ]; then
  echo "  [cost] building the isolated billing client (the deploy client stays untouched)…"
  python3 -m venv "$VENV" >/dev/null 2>&1 || { echo "  [cost] venv failed"; exit 2; }
  "$VENV/bin/pip" -q install --upgrade modal >/dev/null 2>&1 || { echo "  [cost] pip failed"; exit 2; }
fi

VER="$("$VENV/bin/modal" --version 2>/dev/null)"
OUT="$(mktemp -t promptly_cost.XXXXXX.json)"

# Exit code captured DIRECTLY, never through a pipe (codified pipe rule).
"$VENV/bin/modal" billing report --start "${DAYS} days ago" --show-resources --json > "$OUT" 2>/dev/null
RC=$?
if [ "$RC" -ne 0 ]; then
  echo "  [cost] FAIL — billing report exit=$RC ($VER). Cost is UNREAD; do not"
  echo "         report a number and do not infer one from a previous week."
  rm -f "$OUT"; exit "$RC"
fi

python3 - "$OUT" "$DAYS" <<'PY'
import json, sys, collections
rows = json.load(open(sys.argv[1])); days = float(sys.argv[2])
if not rows:
    print("  [cost] EMPTY report — zero rows. That is a FAILED READ, not $0."); sys.exit(1)
app = collections.defaultdict(float); res = collections.defaultdict(float); day = collections.defaultdict(float)
for r in rows:
    c = float(r.get("cost") or 0)
    app[r.get("description") or r.get("object_id")] += c
    res[r.get("resource") or "?"] += c
    day[(r.get("interval_start") or "")[:10]] += c
tot = sum(app.values())
print(f"\n  MODAL COST — last {days:.0f} days: ${tot:,.2f}  =  ${tot/days:,.2f}/day\n")
print("  by app:")
for k, v in sorted(app.items(), key=lambda x: -x[1]):
    if v > 0.005: print(f"    {str(k)[:40]:40} ${v:9.2f}  {100*v/tot:5.1f}%")
print("  by resource:")
for k, v in sorted(res.items(), key=lambda x: -x[1]):
    if v > 0.005: print(f"    {str(k)[:40]:40} ${v:9.2f}  {100*v/tot:5.1f}%")
print("  daily:")
for d in sorted(day):
    print(f"    {d}  ${day[d]:8.2f}")
# A ceiling breach must be loud, not a number a human has to notice.
mo = tot/days*30
print(f"\n  run-rate: ${mo:,.0f}/mo")
if mo > 1500:
    print(f"  [ALERT] run-rate ${mo:,.0f}/mo EXCEEDS the $1500 monthly cap — rendering goes")
    print( "          offline when the cap binds. This is the line that must never be missed.")
PY
RC=$?
rm -f "$OUT"
exit "$RC"
