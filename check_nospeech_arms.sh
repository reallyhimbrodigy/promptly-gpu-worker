#!/usr/bin/env bash
# THREE ARMS ON ONE NO-SPEECH FIXTURE — two questions, one frozen mount.
#
# Round 17's signature lines showed the no-speech fixtures costing 3-4x
# talking_head for a FRACTION of the placements: music $0.2152 for 2,
# pet_video $0.2477 for 4, against talking_head $0.0667 for 18. Two candidate
# explanations, and the signature cannot separate them:
#
#   * THE BRIEF. "Playful and quick" may simply call for less than "make it
#     viral" does. A restrained edit and a thin one look identical in a count.
#   * THE MODEL. Only talking_head is routed to Haiku. The no-speech fixtures
#     are Sonnet, so part of the gap is the rate card, not the route.
#
# viral/Sonnet vs minimal/Sonnet isolates the BRIEF.
# viral/Sonnet vs viral/Haiku   isolates the MODEL.
#
# No-speech is 46.5% of real traffic, so this decides where the cost work goes.
set -uo pipefail
cd "$(dirname "$0")"
OUT=/tmp/fixtures/nospeech; mkdir -p "$OUT"
KEY="$(python3 -c "import json;print(json.load(open('/tmp/fixtures/staged.json'))['pet_video']['key'])")"
SHA="$(shasum -a 256 agentic_editor_app.py | cut -c1-16)"
echo "$SHA" > "$OUT/mount_sha.txt"; echo "[mount] $SHA  fixture=$KEY"

VIRAL="Make it viral. Punchy and fast — hard cuts, big bold captions on every claim, hit every number with a card, sound effects where they land, push in on the turns. Maximum energy."
MINIMAL="Clean and minimal. Let it breathe — very few cuts, keep it calm and legible. Subtle text only where it is genuinely needed, no sound effects, no zooms, no cards."

run_arm() {  # name brief model
  now="$(shasum -a 256 agentic_editor_app.py | cut -c1-16)"
  [ "$now" != "$SHA" ] && { echo "[ABORT] mount drifted ($SHA -> $now)"; exit 2; }
  IFS=$'\t' read -r S O K < <(python3 presign.py "$KEY")
  echo "[launch] $1 ($3)"
  modal run --detach agentic_editor_app.py --source "$KEY" --brief "$2" \
    --model "$3" --src-url "$S" --out-url "$O" --out-key "$K" \
    > "$OUT/$1.log" 2>&1
}
run_arm viral_sonnet  "$VIRAL"   "claude-sonnet-5"
run_arm minimal_sonnet "$MINIMAL" "claude-sonnet-5"
run_arm viral_haiku   "$VIRAL"   "claude-haiku-4-5"

python3 - "$OUT" <<'PY'
import re, sys, os, json
out = sys.argv[1]; FAM = ("text", "cut", "card", "sfx", "zoom")
def read(p):
    t = open(p, encoding="utf-8", errors="ignore").read()
    m = {f: (float(g.group(1)) if (g := re.search(rf"^    {f}\s+([\d.]+) /25s", t, re.M)) else None)
         for f in FAM}
    s = re.search(r"RUN SIGNATURE   : turns (\d+)\s+cost \$([\d.]+)\s+placements (\d+)", t)
    m.update(turns=int(s.group(1)) if s else None, cost=float(s.group(2)) if s else None,
             placements=int(s.group(3)) if s else None)
    m["ok"] = bool(re.search(r"^  ok +: True", t, re.M))
    return m
arms = {a: read(os.path.join(out, f"{a}.log")) for a in
        ("viral_sonnet", "minimal_sonnet", "viral_haiku")}
print(f"\n{'':16}", "".join(f"{a:>16}" for a in arms))
for f in FAM:
    print(f"  {f:14}", "".join(f"{(arms[a][f] if arms[a][f] is not None else -1):>16.2f}" for a in arms))
for k in ("placements", "turns", "cost", "ok"):
    print(f"  {k:14}", "".join(f"{str(arms[a][k]):>16}" for a in arms))
vs, ms, vh = arms["viral_sonnet"], arms["minimal_sonnet"], arms["viral_haiku"]
moved = sum(1 for f in FAM if None not in (vs[f], ms[f]) and abs(vs[f]-ms[f]) >= 0.5)
print(f"\n  BRIEF effect (viral vs minimal, Sonnet): {moved} of 5 families moved")
if vs["cost"] and vh["cost"]:
    print(f"  MODEL effect (Haiku vs Sonnet, viral) : ${vh['cost']:.4f} vs ${vs['cost']:.4f} "
          f"= {100*(1-vh['cost']/vs['cost']):.0f}% cheaper, "
          f"{vh['placements']} vs {vs['placements']} placements")
json.dump(arms, open(os.path.join(out, "arms.json"), "w"), indent=1)
PY
