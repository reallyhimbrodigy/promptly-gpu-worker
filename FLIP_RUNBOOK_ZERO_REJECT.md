# THE FLIP PACKAGE — zero-rejection goes live (staged, NOT executed)

**Trigger:** Zac watches the 4 samples (nature + city minimal · car + gym hype) and replies **"FLIP MINIMAL"**. This single action ends rejections in Promptly.

**Precondition (re-verify at flip time, not assumed):**
```bash
# reaper wall >= worker wall AT THIS MOMENT (worker=3000s, reaper must be >=3300s live on prod)
git -C /Users/zaclibman/content-studio fetch origin main -q && \
git -C /Users/zaclibman/content-studio show origin/main:lib/job-reaper.js | grep -E 'processing: |EXEC_WALL_MS ='
# expect: processing: 50 * 60 * 1000  ·  EXEC_WALL_MS = 55 * 60 * 1000
```

## Step 1 — worker flag (Modal Secret + canonical gate, same change)
```bash
cd /Users/zaclibman/promptly-gpu-worker/promptly-gpu-worker   # branch zero-reject-routing
# 1a. edit validate_deploy.py CANON: "PROMPTLY_ZERO_REJECT": "0" -> "1"
# 1b. update the secret (all 8 keys, ZERO_REJECT now "1"):
#     edit scratchpad/lang_flags.json PROMPTLY_ZERO_REJECT -> "1"
modal secret create promptly-lang-flags --from-json <scratchpad>/lang_flags.json --force
modal run secret_flags_readback.py   # expect 8/8 canonical incl. ZERO_REJECT=1
# 1c. commit (gate+secret same change), gate green (244+), quiet-window deploy, verify live sha
```

## Step 2 — server env (Render, 10-second step — Zac/frontend if this session lacks Render env access)
```
content_routing_enabled=true      # /api/usage routing flags (prepped in bca54b7)
max_upload_seconds=300            # client cap 180 -> 300 (worker capacity live-dark since v354)
```

## Step 3 — post-flip watch (first hours)
- First organic minimal completion: verify route="minimal" in result, video plays, edit_rationale present, quota consumed normally, NO refund fired on the completion.
- Rejection census: intake_rejected ledger should show ONLY CLIP_TOO_SHORT (<2.0s) going forward.
- TH control: organic speech jobs unchanged (spot-check current_step flow + a completed edit_recipe).

## Rollback (one flag)
```
CANON "1" -> "0" + secret ZERO_REJECT -> "0" + redeploy   (worker routes off, rejections return)
content_routing_enabled=false                              (server side, independent)
```

**What stays dark regardless of this flip:** PROMPTLY_HYPE_MODE (music/beat clips keep routing to MINIMAL until the hype taste gate clears: Zac's sign-off + real-music threshold validation on his rights-clear clip). PROMPTLY_RENDER_FANOUT (SA-A L4, its own pixel-equivalence cert).
