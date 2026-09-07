#!/usr/bin/env bash
# DOES THE BRIEF ACTUALLY MOVE THE OUTPUT?
#
# set_spec resolves a vibe to per-family rates and the floor now binds them. That
# machinery is only worth anything if OPPOSITE briefs produce DIFFERENT videos.
# If a "punchy, fast, big bold captions" brief and a "clean, minimal, barely
# touch it" brief come back with the same family mix on the SAME fixture, the
# resolution is decorative: the agent is producing its house style and reading
# the request as flavour text.
#
# That failure is invisible to every other check in this lane. Both runs would be
# green, both would satisfy their own floor, both would balance ruled/built/
# declared — because each is internally consistent. Only comparing them exposes it.
#
# ONE VARIABLE. Same fixture, same model, same frozen mount, same everything but
# the brief.
set -uo pipefail
cd "$(dirname "$0")"
OUT=/tmp/fixtures/discrim; mkdir -p "$OUT"
KEY="ab-sources/reliability-fixtures-v1/talking_head-eeb40bc7.mp4"
SHA="$(shasum -a 256 agentic_editor_app.py | cut -c1-16)"
echo "$SHA" > "$OUT/mount_sha.txt"
echo "[mount] $SHA"

HIGH="Make it viral. Punchy and fast — hard cuts, big bold captions on every claim, hit every number with a card, sound effects where they land, push in on the turns. Maximum energy."
LOW="Clean and minimal. Let it breathe — very few cuts, keep it calm and legible. Subtle text only where it is genuinely needed, no sound effects, no zooms, no cards."

for arm in high low; do
  case "$arm" in high) BRIEF="$HIGH";; low) BRIEF="$LOW";; esac
  now="$(shasum -a 256 agentic_editor_app.py | cut -c1-16)"
  if [ "$now" != "$SHA" ]; then
    echo "[ABORT] mount drifted mid-check ($SHA -> $now); the arms would not be comparable"
    exit 2
  fi
  IFS=$'\t' read -r S O K < <(python3 presign.py "$KEY")
  echo "[launch] $arm"
  modal run --detach agentic_editor_app.py --source "$KEY" --brief "$BRIEF" \
    --model "claude-haiku-4-5" --src-url "$S" --out-url "$O" --out-key "$K" \
    > "$OUT/$arm.log" 2>&1
done

python3 - "$OUT" <<'PY'
import re, sys, os, json
out = sys.argv[1]
FAM = ("text", "cut", "card", "sfx", "zoom")

def mix(path):
    t = open(path, encoding="utf-8", errors="ignore").read()
    m = {}
    for f in FAM:
        g = re.search(rf"^    {f}\s+([\d.]+) /25s", t, re.M)
        m[f] = float(g.group(1)) if g else None
    sig = re.search(r"RUN SIGNATURE   : turns (\d+)\s+cost \$([\d.]+)\s+placements (\d+)", t)
    m["_turns"] = int(sig.group(1)) if sig else None
    m["_cost"] = float(sig.group(2)) if sig else None
    m["_placements"] = int(sig.group(3)) if sig else None
    return m

hi, lo = mix(os.path.join(out, "high.log")), mix(os.path.join(out, "low.log"))
print(f"\n{'family':10} {'VIRAL':>10} {'MINIMAL':>10}   delta")
moved = 0
for f in FAM:
    a, b = hi.get(f), lo.get(f)
    if a is None or b is None:
        print(f"  {f:8} {'?':>10} {'?':>10}   (missing)"); continue
    d = a - b
    # "moved" = the brief changed this family by more than a rounding wobble
    if abs(d) >= 0.5:
        moved += 1
    print(f"  {f:8} {a:>10.2f} {b:>10.2f}   {d:+.2f}{'  <-- moved' if abs(d)>=0.5 else ''}")
print(f"\n  placements: viral {hi['_placements']}  minimal {lo['_placements']}")
print(f"  turns     : viral {hi['_turns']}  minimal {lo['_turns']}")
print(f"  cost      : viral ${hi['_cost']}  minimal ${lo['_cost']}")
json.dump({"viral": hi, "minimal": lo, "families_moved": moved},
          open(os.path.join(out, "discrimination.json"), "w"), indent=1)

# THE CHECK. Opposite briefs must move at least three of the five families. Two
# or fewer means the request is flavour text and the agent is shipping its house
# style whatever it is asked for.
print()
if moved >= 3:
    print(f"  PASS — the brief moved {moved} of 5 families. Spec resolution is doing work.")
else:
    print(f"  FAIL — opposite briefs moved only {moved} of 5 families. The vibe is")
    print(f"         being read as flavour text; the resolved targets are not")
    print(f"         reaching what the agent actually rules.")
    sys.exit(1)
PY
