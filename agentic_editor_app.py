"""AGENTIC EDITOR — one agent, prompt + video in, finished vertical video out.

No schema. No separate editorial call. No plan handed to a renderer. The agent
reads the transcript, decides the edit, WRITES THE RENDER CODE, runs it, watches
its own output, and iterates when it is wrong. The self-review loop is the
architecture, not a nicety bolted on the end.

ffmpeg, NOT Remotion. This is the variable that decides whether the idea is
worth anything: Remotion paints ~800-1000 ms/frame in headless Chromium (
measured — SmoothPush 840, StepZoom 785, LetterboxPush 1796), so an agent
driving Remotion inherits today's render time exactly and the whole exercise
buys nothing. ffmpeg composites orders of magnitude faster. Remotion stays
available as a FALLBACK for segments ffmpeg genuinely cannot express (spring
animation, complex motion graphics) — per segment, never as the default.

REUSED, NOT REBUILT: Deepgram for word timings (33ms; no model matches it and
cuts are built on it), failure-corpus/ sources for testing, frame extraction for
the agent's own review pass.

TWO INSTRUMENTS, WIRED FROM THE START BECAUSE RETROFITTING THEM IS HOW THEY
NEVER GET BUILT:

  1. FAILURE LEDGER — every failure mode, with the agent's command and the
     stderr, appended as it happens. A loop that silently retries teaches
     nothing; the point of the first runs is the failure taxonomy.

  2. SPEECH-CONTENT CHECK — the output is TRANSCRIBED and its words compared to
     the words the agent intended to keep. THE URDU INCIDENT DELETED 58 SECONDS
     AND REPORTED SUCCESS. Generated code has no schema stopping that, so the
     check cannot be a schema — it has to be a measurement on the artifact. An
     edit that loses speech FAILS here even if ffmpeg exited 0 and the file
     plays.

  ./run_modal.sh agentic_editor_app.py --source <s3-key> --brief "..."
"""
import json
import os
import re

import time

import modal

app = modal.App("agentic-editor")

# python_version PINNED: debian_slim() defaults to 3.9 and the Deepgram SDK uses
# `match` statements, so the import dies with a SyntaxError before any agent work
# happens. First entry in the failure taxonomy, and an ENVIRONMENT failure rather
# than an agent one — worth separating in the ledger.
_HERE = os.path.dirname(os.path.abspath(__file__))
_KNOWLEDGE_DIR = os.path.join(_HERE, "knowledge")
_REMOTION_SRC = os.path.abspath(os.path.join(_HERE, "..", "..", "src", "remotion"))
# INPUT 4 — the Remotion skills. 276 markdown files, ~11MB, and until now they
# lived ONLY in ~/.claude/skills on the laptop: the agent runs in a Modal
# container, so they were not "unread", they were UNREACHABLE. Mounting them is
# what makes "did the agent read them" a question that can even be asked.
#
# Served by SEARCH, not by browsing (see search_skills). A 276-file index is not
# something an agent reads; run 10 proved extra reading burden makes the edit
# WORSE, not better. Grep is the right interface for an API reference.
# INPUT 5 — THE REAL ASSET LIBRARY. The component catalogue was mounted; the
# rest of the inventory was not. The 15 SFX files live in src/assets/sounds,
# which is a SIBLING of src/remotion, so the existing mount never carried them,
# and the tables that make them usable — attack timings, transition and caption
# enums — live in handler.py and type_registries.py, which the container has
# never seen. The agent could describe a sound it had no file for.
_ASSETS_SOUNDS = os.path.abspath(
    os.path.join(_HERE, "..", "..", "src", "assets", "sounds"))
# EXTRACTED FROM SOURCE AT DEPLOY TIME, never transcribed — see
# build_asset_inventory.py. Three _MG_ATTACK_MS entries were re-measured on
# 2026-08-29; a hand-copied table would have gone stale silently.
_INVENTORY_JSON = os.path.join(_HERE, "_asset_inventory.json")


def _write_asset_inventory():
    """LOCAL ONLY. Modal re-imports this module INSIDE the container, where
    neither build_asset_inventory.py nor handler.py exists — so an unguarded
    call here is a ModuleNotFoundError at container start, before any agent
    work, which is exactly how this first shipped. The container does not need
    to build anything: it reads the JSON already mounted at
    /assets/inventory.json.

    Deliberately NOT a try/except. A failure to extract on the DEPLOY side must
    still raise loudly — that is the guard that stops an empty inventory
    shipping — so the guard is "am I local", not "did it work".
    """
    import build_asset_inventory
    import json as _json
    inv = build_asset_inventory.build()      # raises on empty/mismatched tables
    with open(_INVENTORY_JSON, "w") as fh:
        _json.dump(inv, fh, indent=1)
    return inv


_ASSET_INV = _write_asset_inventory() if modal.is_local() else None

_SKILLS_SRC = os.path.expanduser("~/.claude/skills")
_SKILLS_IGNORE = ["arcads-*", "awesome-claude-skills", "claude-video",
                  "interactivity-best-practices", "superpowers",
                  "ui-ux-pro-max-skill", "watch",
                  "**/node_modules", "**/.git", "**/*.png", "**/*.jpg",
                  "**/*.gif", "**/*.mp4", "**/*.webm"]

# Remotion needs a real project on disk plus Chrome Headless Shell. Both are
# BAKED INTO THE IMAGE, not fetched at render time — a 150MB chrome download
# inside the agent loop would land as an opaque timeout in the middle of an edit.
_PKG = (
    '{"name":"agentic-mg","version":"1.0.0","private":true,"dependencies":'
    '{"@remotion/cli":"4.0.517","remotion":"4.0.517",'
    '"react":"19.0.0","react-dom":"19.0.0"}}'
)
_ROOT_TSX = (
    'import {Composition} from "remotion";\n'
    'import {Comp} from "./Comp";\n'
    'export const RemotionRoot: React.FC = () => (\n'
    '  <Composition id="Comp" component={Comp as any} durationInFrames={90}\n'
    '    fps={30} width={1080} height={1920} />\n'
    ');\n'
)
_INDEX_TS = (
    'import {registerRoot} from "remotion";\n'
    'import {RemotionRoot} from "./Root";\n'
    'registerRoot(RemotionRoot);\n'
)
# Placeholder the agent OVERWRITES. Transparent background is the contract: the
# MG is composited over the ffmpeg cut, it does not replace it.
_COMP_TSX = (
    'export const Comp: React.FC = () => <div style={{flex:1}} />;\n'
)

IMG = (modal.Image.debian_slim(python_version="3.11")
       .apt_install(
           "ffmpeg", "curl", "ca-certificates",
           # Chrome Headless Shell runtime deps — without these the remotion
           # render dies with a bare "browser failed to launch".
           "libnss3", "libdbus-1-3", "libatk1.0-0", "libasound2", "libxrandr2",
           "libxkbcommon0", "libxfixes3", "libxcomposite1", "libxdamage1",
           "libgbm1", "libpango-1.0-0", "libcairo2", "libatk-bridge2.0-0",
           "libcups2", "libxext6", "libx11-6", "libglib2.0-0")
       .run_commands(
           "curl -fsSL https://deb.nodesource.com/setup_20.x | bash -",
           "apt-get install -y nodejs",
           "mkdir -p /remotion/src",
           f"cat > /remotion/package.json <<'EOF'\n{_PKG}\nEOF",
           f"cat > /remotion/src/Root.tsx <<'EOF'\n{_ROOT_TSX}EOF",
           f"cat > /remotion/src/index.ts <<'EOF'\n{_INDEX_TS}EOF",
           f"cat > /remotion/src/Comp.tsx <<'EOF'\n{_COMP_TSX}EOF",
           "cd /remotion && npm install --no-audit --no-fund",
           # Bake the browser so the agent loop never pays for it.
           "cd /remotion && npx remotion browser ensure",
       )
       # THE REAL COMPONENT CATALOGUE, at ITS OWN pinned runtime. Probed
       # standalone first: FrameCompProbe 290.0 ms/frame, MGCraftProbe 293.3,
       # both 1080x1920 h264, remotion 4.0.450 + react 18.3.1 as pinned.
       # Kept SEPARATE from /remotion (4.0.517/react19) — react 19 is a major
       # and mixing them makes a working component look broken.
       .add_local_dir(_REMOTION_SRC, "/promptly-remotion", copy=True,
                      ignore=["node_modules", "*-out", ".git"])
       .run_commands(
           "cd /promptly-remotion && npm install --no-audit --no-fund",
           "cd /promptly-remotion && npx remotion browser ensure")
       .pip_install(["anthropic", "deepgram-sdk==3.*", "boto3"])
       .add_local_dir(_SKILLS_SRC, "/skills", copy=True, ignore=_SKILLS_IGNORE)
       .add_local_dir(_ASSETS_SOUNDS, "/assets/sounds", copy=True)
       .add_local_file(_INVENTORY_JSON, "/assets/inventory.json", copy=True)
       .add_local_dir(_KNOWLEDGE_DIR, "/knowledge", copy=True))

SECRETS = [modal.Secret.from_name("promptly-secrets")]
BUCKET = "thisismybucketagainwooo"
MODEL = "claude-sonnet-5"

# ── THE RUBRIC — all seven families, re-extracted 2026-09-05 ─────────────────
# Source: reference_beats joined to reference_videos, 10 videos / 426s / 153
# beats, treatment is an array per beat so every family is countable.
#
# THE RATES IN USE UNTIL NOW (7.56 text / 2.57 cards / 3.32 cutaways) DO NOT
# REPRODUCE from this corpus on any cut I can find — the full set gives
# 7.28/2.35/4.22 and the in_instrument subset (2 videos, 96s) gives
# 7.83/2.61/5.74. Their denominator is undocumented. These use the FULL corpus:
# it is the larger sample and it is reproducible from a query.
#
# Four families were counted in every run and never reported against anything.
# Text at 97% means nothing while zooms sit at 0.
REFERENCE_PER_25S = {
    "text":       7.28,   # overlay_text, 124 beats
    "cut":        4.75,   # 81
    "cutaway":    4.22,   # 72
    "card":       2.35,   # 40
    "sfx":        0.82,   # 14
    "zoom":       0.35,   # punch_in, 6
    "transition": 0.00,   # ZERO in the corpus — not a gap, an absence
}
# Which beat PURPOSE each family lands on, from the same 153 beats. This is the
# rule the agent can act on, and it is what "corpus says" should mean.
REFERENCE_BEAT_FIT = {
    "sfx":     {"hook": 5, "close": 4, "claim": 2, "breath": 1, "evidence": 1, "turn": 1},
    "card":    {"evidence": 18, "close": 11, "turn": 4, "hook": 3, "claim": 2},
    "cutaway": {"evidence": 44, "turn": 8, "claim": 7, "close": 4, "payoff": 4},
    "zoom":    {"hook": 3, "evidence": 3},
}


def _supports_effort(model_id: str) -> bool:
    """Does this model accept output_config.effort?

    A 4.5-era model 400s on it, which killed the first cheaper-model arm at
    turn 1. Allowlist rather than denylist: an unknown model gets the SAFE
    shape (no effort) instead of a request that cannot be sent.
    """
    m = str(model_id or "")
    return any(k in m for k in ("sonnet-5", "opus-5", "opus-4-8", "opus-4-7",
                                "opus-4-6", "sonnet-4-6", "fable-5"))
# 5 -> 12 -> 22. Run 3 (knowledge ON) spent 4 of its 12 turns READING and died
# at "Now burn the captions" — the budget has to cover the reading AND the edit,
# or the knowledge arm is structurally unable to finish what the control finishes.
MAX_ITERS = 16
# 8000 was the ceiling the agent kept hitting MID-TOOL-CALL. stop_reason came
# back 'max_tokens' with an incomplete tool_use block, so tool_uses was empty,
# so the loop broke -- silently, for three runs and ~$0.72. The recipes made it
# worse by teaching one enormous filtergraph per command, which is precisely the
# shape that overruns a response budget.
MAX_TOKENS = 16000

SYSTEM = """You are a video editor. You are given a raw talking-head clip and a
word-level transcript with exact timings. You produce a finished vertical
(1080x1920) short-form video.

You do this by WRITING AND RUNNING SHELL COMMANDS — ffmpeg, ffprobe, python3.
There is no schema and no downstream renderer interpreting a plan. What you
write is what ships.

HOW TO WORK
1. Read the transcript. Decide which words to keep and which to cut. Silence,
   filler and false starts are the usual cuts; keep the meaning intact.
2. Build the edit with ffmpeg. Concatenate the kept spans, crop/scale to
   1080x1920, and burn captions if they improve it.
3. RUN your command with the `shell` tool. Read the stderr.
4. VERIFY with `inspect_output`: it probes the file AND transcribes it, and
   tells you which intended words are MISSING from the result.
5. If words are missing or the output is wrong, FIX IT AND RUN AGAIN. Say
   `DONE` only when inspect_output shows the speech intact.

THE REAL COMPONENT CATALOGUE IS MOUNTED AT /promptly-remotion
Do NOT reimplement graphics in ffmpeg. The production components live there and
render standalone (measured: ~290 ms/frame at 1080x1920).

  cd /promptly-remotion && npx remotion compositions        # what exists

THE REMOTION API REFERENCE IS A TOOL: `search_skills`
276 files of official Remotion docs. Use it INSTEAD OF GUESSING at a prop name,
a hook, a CLI flag, or an error string — one wrong prop costs a whole render
round-trip, and you have a turn budget. `search_skills("--props")`,
`search_skills("spring(")`. Do not browse it; ask it one question at a time.
/promptly-remotion is the truth for WHAT EXISTS; the reference is the truth for
HOW to call it.

WHICH TOOL FOR WHICH GRAPHIC — the rule, because "don't reimplement" was not one
ffmpeg drawtext/drawbox is CORRECT and cheaper for anything STATIC: a line of
overlay text that appears, holds and cuts. Use it there without apology.

MANDATORY, NOT A PREFERENCE: if you place a CARD whose hero content is a NUMBER
the speaker said, it MUST be rendered as a StatCard component. A static ffmpeg
card is NOT an acceptable substitute for a count-up — the count-up IS the
component's reason to exist, and three prior runs each had the verified command
in hand and chose static anyway. Render it per C1-C6 below, then composite it
over your cut and declare it with method="remotion". If the render genuinely
fails, ship the ffmpeg edit and SAY SO in your final message — but do not skip
the attempt.

COMPONENT RENDER CONSTRAINTS — C1 THROUGH C6, REQUIREMENTS NOT PREFERENCES
These six are MEASURED facts about this exact image, not advice. They lived as
prose in 15_ffmpeg_placement_recipes.md and were read-and-ignored three runs
running; a fourth run then spent FOURTEEN commands rediscovering C1 and C2 from
scratch, including dumping raw pixel values to identify the grey. They are
numbered here because numbered requirements got followed and prose did not.
Violating any of them produces a BROKEN video that still exits 0.

  C9. ALL COMPONENTS IN ONE PASS — author the whole list, then `render_components`.
      This is a DIFFERENT SHAPE from place-one-check-one: decide every moving
      graphic in the edit FIRST, then make a single call with all of them. It
      packs them into one reel, renders once and hands you the composite
      command with each offset already computed.
      Measured: ten components in one pass ~72s; ten separate renders ~161s,
      and rendering them spread across the full timeline is ~169s — WORSE than
      doing them separately. The reel is what makes this cheap.
      C8 below is where that decision gets made: ruling on every number beat IS
      authoring the list. Do C8, then call this once with everything that
      earned a component.

  C8. RULE ON EVERY BEAT — ONE DECISION EACH, IN ONE CALL, ENFORCED.
      Call `rule_all_beats` ONCE with the complete list — every beat in your
      brief, in a single call. Ruling them one at a time costs one TURN per
      beat (17-19 turns before any editing happens) and grows the message
      history by a verdict every turn, which is billed again on every turn
      after it. Same decisions, one turn.
      Each entry carries:
        treatment — "card" | "text" | "none"
        cut       — "keep" | "cut"
        why       — about THAT beat's content
      "none" and "keep" are legitimate answers. Not deciding is not, and DONE
      is refused while any beat is unruled.
      THIS IS ONE QUESTION, NOT THREE. It replaced separate gates for numbers,
      components and the cut. Each of those forced a family and starved the
      rest — adding the third took cards from 0.91 to 0.23 per 25s on a source
      where the two runs before it had each rendered four. Decide the BEAT and
      the families take care of themselves.
      Beats marked "(has a number)" are candidates for a card, not obligations:
      a number that is a joke, an ordinal, or an operand feeding a later total
      is usually "text" or "none".


  COST, RE-MEASURED 2026-09-04 — the old figure here was WRONG BY ~9x and it
  was arguing against components. It said "~343 ms/frame, so 2s of component =
  ~21s of paint". That was STARTUP AMORTISED OVER A SHORT RENDER, not paint.
  Separated by rendering 30/60/150 frames and taking the slope:

      STARTUP  13.8s  per `remotion render` INVOCATION
      PAINT      39ms per frame

  So 2s of component (60 frames) is 2.3s of paint behind a 13.8s startup. The
  startup dominates and it is PER INVOCATION — the cost is in the NUMBER OF
  RENDER CALLS, not the number of components. Ten components rendered one at a
  time is ~161s; the same ten in ONE pass is ~82s and does not grow with the
  eleventh. Do not skip a component because you think paint is expensive.
  Static text still stays ffmpeg — that is a taste call, not a cost one.

A COMPONENT IS REQUIRED WHEN THE GRAPHIC MOVES. ffmpeg cannot express these at
all, and approximating them with a static box is the wrong edit, not a cheaper
one:
  - a number that COUNTS UP to its value          -> StatCard
  - a bar that FILLS toward a target              -> ProgressBar
  - anything with spring/eased entrance or staged reveal
  - multi-element graphics that animate in sequence
If the beat calls for a moving graphic, render the component at
/promptly-remotion and composite it. Do NOT downgrade a moving graphic to static
text because ffmpeg is easier — that is a quality decision, and quality wins.

DECLARE EVERY PLACEMENT
After the command that renders a graphic succeeds, call `declare_placement`
once for it. Counting ffmpeg filter names cannot tell a caption burn from an
overlay text; four runs were misread that way. Your declaration is the record.

THE REAL ASSET LIBRARY IS MOUNTED AT /assets — A1 THROUGH A3
This is the inventory the production pipeline ships, not a description of one.


  S1. SOUND IS A FAMILY YOU HAVE NEVER USED. Corpus rate is 0.82 per 25s and
      every run so far has placed ZERO. /assets/inventory.json carries
      `sfx_catalogue`: 15 real files, each with a ROLE (the moment it belongs
      on), what it FITS, what it FIGHTS, its duration and its attack offset.
      Pick by ROLE, not by name.
      WHERE THEY LAND, from the 153-beat corpus: 64% of all SFX sit on a HOOK
      or a CLOSE. If your edit has a hook and a close and no sound, that is the
      gap — not a style choice.
      `voice` is a real entry with no file: the signed bare choice, for a beat
      whose delivery already lands it. Choosing it is an answer; ignoring the
      family is not.
      ATTACK IS NOT OPTIONAL: start the file `attack_ms` EARLIER than the target
      word so its PEAK lands on the word. popsfx peaks at 32ms, imposter at
      935ms — start both at the word and the second lands a second late, and
      ffmpeg exits 0.
      Mix with ffmpeg: -i /assets/sounds/<file> and an adelay on the sound leg.

EFFICIENCY — E1 THROUGH E4, REQUIREMENTS NOT PREFERENCES
Output tokens are 40-44% of this job's cost and turns are the multiplier on it.
These are not about doing less work; they are about not doing the SAME work
twice.

  E1. USE `build_cut` AND `build_overlays` — NEVER HAND-BUILD A FILTERGRAPH.
      You choose the spans; it does the segment maths, the output-time remap
      and the .srt, and returns the exact ffmpeg command. Measured: hand-
      building these took ~7 shell commands per run and got the caption remap
      wrong twice. `build_overlays` does the same for text: you give words,
      timings and position, it escapes them and burns the captions in the SAME
      pass. Run 15 hand-wrote a drawtext graph and then sed-patched it to fix
      apostrophes — that is a turn you do not have. Dead air over 0.35s is
      already listed in your brief; do not recompute it.
      YOUR TURN BUDGET IS 8. Plan the whole edit up front, then execute: read
      what you need, decide the spans, build_cut, render, build_overlays,
      composite, verify once. There is no budget for exploration.
      (E1 was "read only what the task needs" until 2026-09-03. It was dropped:
      it cut placement density 6.9 -> 3.34 text/25s while reading stayed flat
      at 4 files, so it was suppressing the edit, not the survey.)

  E2. ONE RENDER, ONE COMPOSITE, VERIFY ONCE — ENFORCED, NOT ADVISED.
      `inspect_output` is CAPPED: one call, plus one retry ONLY if that call
      failed. A third is refused by the tool. Re-render only when verification
      actually FAILED; a second render "to be safe" is ~21s of paint and a turn
      of output tokens buying nothing.
      (Enforced 2026-09-03. As advice E2 did not bind: with the prep work gone,
      the agent spent the freed budget on SIX inspect_output calls, so turns
      fell 26 -> 21 while shell calls fell 19 -> 12. Budget expands to fill.)

  E3. DO NOT RE-DERIVE WHAT THE RECIPES ALREADY STATE. The commands in
      15_ffmpeg_placement_recipes.md and C1-C6 above are VERIFIED against this
      exact image. Use them verbatim. A previous run spent FOURTEEN commands
      rediscovering C1 and C2 from scratch, including dumping raw pixel values
      to identify a grey that C2 states outright.


WORKING DISCIPLINE — K1 THROUGH K4
Behavioural, not editorial. Measured: 0 of the 999 editing terms in the
knowledge set appear in this material, and none of these four appear in the
knowledge set at all — it answers "how to work", never "how to cut".

  K1. STATE ASSUMPTIONS, DO NOT SILENTLY PICK. If a beat could be read two
      ways, say which you chose and why in your final message.

  K2. VERIFIABLE SUCCESS CRITERIA, THEN LOOP. "Make it good" is not a goal.
      Yours are already concrete: inspect_output shows the speech intact,
      the output is 1080x1920 H.264 with audio, every graphic is declared.
      Loop until those hold — do not stop at the first render that exits 0.

  K3. NEVER DECLARE COMPLETE WHAT YOU HAVE NOT VERIFIED. Exit code 0 is not
      verification. A 60fps graphic on a 30fps cut and an unkeyed grey
      rectangle BOTH exit 0. Say DONE only after inspect_output.

  K4. DO NOT INVENT AN API. If you are unsure of a prop, a flag or a
      composition name, use `search_skills` or `npx remotion compositions`.
      A guessed prop name costs a whole render round-trip.

  NOT ADOPTED — "simplicity first / nothing beyond what was asked". It is good
  advice for writing code and it is WRONG FOR THIS JOB, measured: across five
  runs this agent placed 0-1 cards against a reference rate of 2.57 per 25s.
  The failure mode here is UNDER-doing, not over-building. Placing the graphic a
  beat calls for is the task, not scope creep.

HARD RULES
- The output must be 1080x1920, H.264, with audio.
- NEVER report success on an output whose speech is missing. An edit that plays
  but has lost the words has failed.
- Cuts land on word boundaries from the transcript, not round numbers.
- Work in /work. The source is /work/source.mp4. Write /work/out.mp4.
"""

# The editorial knowledge is served as a TOOL, not pasted into the prompt. It is
# 171k characters — inlining it would cost ~43k tokens on every single turn and
# make the $0.10/job law further out of reach, which is the opposite of the point.
# The agent reads the two or three files its edit actually needs.
_KNOWLEDGE_SYSTEM = """
EDITORIAL KNOWLEDGE — READ IT BEFORE YOU CUT

You have `read_knowledge`. It serves the editorial standard this product is
built on: the component catalogue with its FITS/FIGHTS lines, arc structure,
caption rules, grounding rules, the sound-effect library with attack timings,
and where the families actually land in reference edits.

This is not background reading. It is the difference between an edit that cuts
silence and an edit that is DIRECTED. Read `_index` first, then the two or three
files your edit needs. REQUIRED READS, before you build: `15_ffmpeg_placement_recipes.md` (the exact
ffmpeg invocations for cards and positioned overlay text — COPY THEM),
`14_card_text_placement_rules.md` (where
cards and text actually go, with the evidence), `13_placement_findings.md`,
and `03_captions.md`. The rules file is the one that tells you WHICH family
belongs on WHICH beat — an edit built without it is guessing at composition.

TWO RULES FROM THAT KNOWLEDGE THAT OVERRIDE YOUR INSTINCTS:
- Overlay text is the WORKHORSE (~7.5 per 25s). Emphasis and SFX are RARE
  (~0.5 per 25s). If your edit has more zooms than text, it is inverted.
- Every component you place must be GROUNDED in something the speaker actually
  said. A card is a quoted line. If you cannot point at the words, do not place
  it.

MOTION GRAPHICS — ffmpeg FIRST, Remotion ONLY when ffmpeg cannot express it

Cuts, crops, zooms, captions, transitions and text overlays are ffmpeg work.
ffmpeg composites orders of magnitude faster than headless Chromium, and that
speed is the whole reason this architecture is worth having.

For a GENUINE motion graphic — a counting StatCard, a filling bar, a staged
reveal — mount the REAL catalogue component at /promptly-remotion. The exact
invocation, the fps, the keying and the compositing are C1 through C6 in your
system prompt. FOLLOW THOSE; they are measured against this image and they
override any command you find in a knowledge file, including this one.

`15_ffmpeg_placement_recipes.md` carries the same procedure with the discovery
history attached. Read it for the WHY. Do not re-derive the HOW — C1-C6 is the
HOW, already paid for.

Authoring your own component in /remotion/src/Comp.tsx is a LAST resort, for a
graphic the catalogue genuinely cannot express. The catalogue is 59 components;
check `npx remotion compositions` and the MG catalogue file before writing TSX.

If the Remotion render fails, SHIP THE FFMPEG EDIT. A missing motion graphic is
a weaker video; a missing video is a failure. Never let the graphic cost you the
edit.
"""

TOOLS = [
    {"name": "shell",
     "description": "Run a shell command (ffmpeg/ffprobe/python3). Returns "
                    "exit code, stdout and stderr, truncated.",
     "input_schema": {"type": "object",
                      "properties": {"cmd": {"type": "string"}},
                      "required": ["cmd"]}},
    {"name": "inspect_output",
     "description": "Probe /work/out.mp4 AND transcribe it, reporting duration, "
                    "resolution, and which intended words are missing from the "
                    "rendered audio. Call this before saying DONE.",
     "input_schema": {"type": "object", "properties": {}}}]

# TWO tools, as a LIST. This was written as `KNOWLEDGE_TOOL = {...}, {...}`,
# which is a TUPLE of two dicts -- valid Python, and the API rejected the
# whole request with `tools.2: Input should be...`. pyflakes cannot see it;
# only the wire format can. Failed in 5.4s for $0.00 with 3 ledger events.
KNOWLEDGE_TOOLS = [{
    "name": "declare_placement",
    "description": (
        "Declare a graphic you have placed. Call this ONCE per placement, right "
        "after the command that renders it succeeds. This is the record of what "
        "the edit contains — an op-count of ffmpeg filters cannot tell a caption "
        "burn from an overlay text, and guessing from filter names is how four "
        "runs were misread."),
    "input_schema": {
        "type": "object",
        "properties": {
            "type": {"type": "string",
                     "enum": ["card", "overlay_text", "cutaway", "caption_track",
                              "emphasis", "sfx"]},
            "t_start": {"type": "number", "description": "seconds in the OUTPUT"},
            "t_end": {"type": "number"},
            "content": {"type": "string", "description": "the text/number shown"},
            "method": {"type": "string", "enum": ["ffmpeg", "remotion"]},
            "why": {"type": "string",
                    "description": "the beat this serves (claim/evidence/close/...)"},
        },
        "required": ["type", "t_start", "method"]},
}, {
    "name": "read_knowledge",
    "description": "Read a file of Promptly's editorial standard. Pass '_index' "
                   "to list what is available. Extracted verbatim from the "
                   "production editorial prompt.",
    "input_schema": {"type": "object",
                     "properties": {"file": {"type": "string"}},
                     "required": ["file"]},
}, {
    "name": "build_cut",
    "description": (
        "Turn the spans you decide to KEEP into the concat filter AND an "
        "output-time subtitle file, in one call. YOU choose the spans — that is "
        "the edit. This does the arithmetic: segment maths, the output-time "
        "remap of every word, and the .srt. Measured: this replaces ~7 shell "
        "commands per run. Returns the exact ffmpeg command to run next."),
    "input_schema": {"type": "object",
                     "properties": {
                         "keep_spans": {
                             "type": "array",
                             "description": "[[start,end],...] in SOURCE seconds, "
                                            "ascending, non-overlapping",
                             "items": {"type": "array", "items": {"type": "number"}}},
                         "words_per_cue": {"type": "integer"}},
                     "required": ["keep_spans"]},
}, {
    "name": "build_overlays",
    "description": (
        "Turn the text overlays you have decided on into a SAFE ffmpeg "
        "filtergraph, with captions burned in the same pass. YOU choose the "
        "words, timings and position — that is the edit. This escapes them "
        "(apostrophes, colons, commas) and returns the exact command. Hand-"
        "escaping cost a turn and a re-encode last run."),
    "input_schema": {"type": "object",
                     "properties": {
                         "items": {"type": "array", "items": {"type": "object",
                             "properties": {
                                 "text": {"type": "string"},
                                 "t_start": {"type": "number"},
                                 "t_end": {"type": "number"},
                                 "position": {"type": "string",
                                              "enum": ["top", "bottom"]}},
                             "required": ["text", "t_start", "t_end"]}},
                         "burn_captions": {"type": "boolean"},
                         "input_file": {"type": "string"},
                         "output_file": {"type": "string"},
                         "extra_input": {"type": "string"}},
                     "required": ["items"]},
}, {
    "name": "render_components",
    "description": (
        "Render ALL your moving components in ONE pass. Author the complete "
        "list first — every card, every animated graphic — then call this once. "
        "It packs them into a contiguous reel, renders once, and returns the "
        "ffmpeg command that composites each one at its own timestamp. "
        "Measured: one render for ten components is ~72s; ten separate renders "
        "are ~161s. Do NOT call it per component, and do not shift the offsets "
        "by hand — they are computed."),
    "input_schema": {"type": "object",
                     "properties": {
                         "items": {"type": "array", "items": {"type": "object",
                             "properties": {
                                 "type": {"type": "string",
                                          "description": "MG type, e.g. StatCard"},
                                 "t_start": {"type": "number",
                                             "description": "OUTPUT seconds"},
                                 "duration_s": {"type": "number"},
                                 "props": {"type": "object"}},
                             "required": ["type", "t_start"]}}},
                     "required": ["items"]},
}, {
    "name": "rule_all_beats",
    "description": (
        "Rule on EVERY beat in ONE call. Pass the complete list — one entry per "
        "beat in your brief, each with treatment ('card'|'text'|'none'), cut "
        "('keep'|'cut') and a why about that beat. This is one turn instead of "
        "one turn per beat, and the message history stops growing by a verdict "
        "every turn. If you miss any it tells you which; call again with only "
        "those."),
    "input_schema": {"type": "object",
                     "properties": {
                         "verdicts": {"type": "array", "items": {"type": "object",
                             "properties": {
                                 "beat": {"type": "integer"},
                                 "treatment": {"type": "string",
                                               "enum": ["card", "text", "none"]},
                                 "cut": {"type": "string", "enum": ["keep", "cut"]},
                                 "why": {"type": "string"}},
                             "required": ["beat", "treatment", "cut", "why"]}}},
                     "required": ["verdicts"]},
}, {
    "name": "beat_verdict",
    "description": (
        "Rule on ONE beat — the whole decision, once. What goes here (a card, a "
        "text overlay, or nothing), whether the beat is kept or cut, and WHY. "
        "Every beat in your brief needs one before you finish. This replaced "
        "three separate gates: each of those forced a family, and forcing one "
        "family measurably starved the others. There is one question per beat "
        "so nothing can be satisfied at another family's expense."),
    "input_schema": {"type": "object",
                     "properties": {
                         "beat": {"type": "integer", "description": "the beat index"},
                         "treatment": {"type": "string",
                                       "enum": ["card", "text", "none"]},
                         "cut": {"type": "string", "enum": ["keep", "cut"]},
                         "why": {"type": "string",
                                 "description": "about THIS beat's content"}},
                     "required": ["beat", "treatment", "cut", "why"]},
}, {
    "name": "search_skills",
    "description": (
        "Search the Remotion API reference (276 files) for how to call "
        "something: a prop name, a hook, a CLI flag, an error string. Returns "
        "matching lines with context. This is the HOW; /promptly-remotion is "
        "the WHAT-EXISTS. Use it before guessing at an API — a wrong prop name "
        "costs a full render round-trip."),
    "input_schema": {"type": "object",
                     "properties": {
                         "query": {"type": "string",
                                   "description": "literal substring, e.g. "
                                                  "'spring(' or '--props' or "
                                                  "'interpolate'"},
                         "max_hits": {"type": "integer"}},
                     "required": ["query"]},
}]


# BOTH files are required for the capability arm: 14 says WHERE families go,
# 15 gives the exact ffmpeg invocation that draws them. Runs 6/8/9 placed ZERO
# cards and ZERO text with 14 read, which is the hypothesis 15 tests — knowing
# where a card belongs is not knowing the command that renders one.
REQUIRED_KNOWLEDGE = ["14_card_text_placement_rules.md",
                      "15_ffmpeg_placement_recipes.md"]


def beat_cut_status(beats, spans, kept_threshold=0.5):
    """Which beats SURVIVED the cut, from the spans actually passed to build_cut.

    The agent's own `cut` field is a self-report and run J proved it unreliable:
    every beat was reported "keep" while build_cut received 17 spans covering
    0.789 of the source. The cut happened; the verdict field did not see it. Two
    different truths, and only the spans are ground truth.

    A beat counts as kept when more than `kept_threshold` of its duration falls
    inside some keep span — a beat clipped at one edge is still kept, a beat
    mostly removed is cut.
    """
    out = []
    for b in beats or []:
        b0, b1 = float(b["t_start"]), float(b["t_end"])
        dur = max(b1 - b0, 1e-9)
        covered = 0.0
        for a, z in (spans or []):
            lo, hi = max(b0, float(a)), min(b1, float(z))
            if hi > lo:
                covered += (hi - lo)
        frac = covered / dur
        out.append({"i": b["i"], "covered": round(frac, 3),
                    "kept": frac > kept_threshold})
    return out


def segment_beats(words, gap_s=0.35, max_beat_s=6.0):
    """Cut the transcript into BEATS — the unit the agent rules on.

    ONE DECISION PER BEAT replaced three competing gates (2026-09-04). C8
    (numbers), C9 (components) and C10 (the cut) each forced a family, and each
    one measurably starved the families that were not gated: adding C10 took
    cards 0.91 -> 0.23 per 25s on an identical source where F and G had both
    rendered 4. There is no way to satisfy a cards gate at the expense of text
    when there is only one gate and it asks about the BEAT.

    Split on dead air first — a pause is a real boundary. But gaps alone are not
    enough and the finance source proves it: 110s of scripted explainer with
    ZERO gaps >= 0.35s would collapse to a single beat, which is no segmentation
    at all. So any run longer than max_beat_s is also split, on word boundaries,
    never mid-word.
    """
    if not words:
        return []
    beats, cur = [], [words[0]]
    for prev, w in zip(words, words[1:]):
        gap = w["s"] - prev["e"]
        span = w["e"] - cur[0]["s"]
        if gap >= gap_s or span > max_beat_s:
            beats.append(cur)
            cur = [w]
        else:
            cur.append(w)
    if cur:
        beats.append(cur)
    return [{"i": i,
             "t_start": round(b[0]["s"], 2),
             "t_end": round(b[-1]["e"], 2),
             "text": " ".join(str(x["w"]) for x in b)[:180]}
            for i, b in enumerate(beats)]


def pack_reel(items, fps=30):
    """Pack authored placements into a CONTIGUOUS reel + the composite offsets.

    Batching only pays in the packed form. Measured 2026-09-04 on PromptlyOverlay
    as a PNG sequence: painting the FULL 58s timeline to get 10 components is
    1,740 frames / 169.3s / 128MB — WORSE than ten separate renders (~161s).
    Packing the same ten back-to-back is 600 frames / 72.2s / 75MB. So the reel
    is not an optimisation on top of batching; it is the thing that makes
    batching worth doing at all.

    Two clocks, and confusing them is the whole risk:
      REEL time   — where a component sits in the single rendered strip.
      OUTPUT time — where it must appear in the finished edit.
    A component that lands 2s off does not look like a bug, it looks like a
    placement decision, so this is pure and unit-tested rather than inlined.

    Returns reel entries (for PromptlyRenderInput.motionGraphics) and segments
    (for the ffmpeg composite), one per item, in author order.
    """
    out_reel, out_seg, cursor = [], [], 0
    for i, it in enumerate(items):
        dur_s = float(it.get("duration_s") or 2.0)
        dur_f = max(1, int(round(dur_s * fps)))
        at_s = float(it.get("t_start") or 0.0)
        out_reel.append({
            "type": it.get("type") or "StatCard",
            # CUMULATIVE, never i * dur_f. With variable durations a fixed
            # stride silently overlaps or gaps every component after the first
            # one whose length differs — and the render still exits 0.
            "fromFrame": cursor,
            "durationInFrames": dur_f,
            "props": dict(it.get("props") or {}),
        })
        out_seg.append({
            "i": i,
            "reel_from_s": round(cursor / fps, 4),
            "reel_to_s": round((cursor + dur_f) / fps, 4),
            "out_at_s": round(at_s, 4),
            "duration_s": round(dur_f / fps, 4),
        })
        cursor += dur_f
    return {"fps": fps, "reel_frames": cursor, "reel": out_reel, "segments": out_seg}


def remap_words(spans, words):
    """Words inside `spans`, re-timed to the CONCATENATED output's clock.

    Pure and module-level so it can be tested without a container. This is the
    arithmetic the agent hand-wrote every run and got wrong twice, and its
    failure mode is silent: wrong offsets drift the captions against the speech
    and every command still exits 0.

    A word belongs to the first span that fully contains it. Its output time is
    its offset within that span, plus the total duration of all EARLIER kept
    spans — never its source time, which is the bug both hand versions had.
    """
    kept, off = [], 0.0
    for a, b in spans:
        for w in words:
            if w["s"] >= a - 1e-6 and w["e"] <= b + 1e-6:
                kept.append({"w": w["w"],
                             "s": w["s"] - a + off,
                             "e": w["e"] - a + off})
        off += (b - a)
    return kept


# ── CHECK 1 (STATIC): the constraints cannot silently decay back to prose ─────
# The fps/alpha facts were prose in a knowledge file and were ignored three runs
# running. Promoting them to numbered requirements is only durable if something
# FAILS when they are edited back out or when the refuted flags return. This
# runs at import, so a bad prompt cannot reach a container.
#
# RED-PROVEN: deleting the "C2." line raises; re-adding "--codec=prores" raises.
# A check that has never failed is not yet a check.
_REQUIRED_CONSTRAINTS = [
    # Trimmed 2026-09-04. C1-C6 (the single-component MGCraftProbe grey-key
    # path) were superseded by C9's reel; C7 mandated a search that logged
    # skills_searched_zero_hits on every run that ran it; A1-A3 described an
    # asset library that reported mounted_unread on every run; E4 was a
    # tombstone for a retired rule. ~4,200 chars describing paths the agent no
    # longer takes, billed on every turn of every render.
    "C8.", "C9.", "S1.", "E1.", "E2.", "E3.", "K1.", "K2.", "K3.", "K4."]
# Every one of these was tried against this image and FAILED. If a future edit
# reintroduces them the agent inherits 31 failed attempts again.
_REFUTED_IN_PROMPT = ["--codec=prores", "yuva444p10le"]


def _assert_constraints_intact(system_text: str) -> None:
    missing = [c for c in _REQUIRED_CONSTRAINTS if c not in system_text]
    if missing:
        raise AssertionError(
            f"SYSTEM prompt lost component-render constraints {missing}. These "
            f"are C1-C6 (fps + alpha keying); they were prose once and were "
            f"read-and-ignored three runs running. Do not ship without them.")
    # A bare substring scan is WRONG here and the RED test proved it: C3 has to
    # NAME the refuted flags in order to forbid them, so "is the string present"
    # flags the constraint that exists to prevent the thing. The real question
    # is whether each occurrence sits in a PROHIBITING context or an
    # INSTRUCTING one. Check the line, not the file.
    _PROHIBIT = ("NEVER", "never", "Do NOT", "do not", "failed", "REFUTED")
    revived = []
    for _flag in _REFUTED_IN_PROMPT:
        for _line in system_text.splitlines():
            if _flag in _line and not any(p in _line for p in _PROHIBIT):
                revived.append(f"{_flag!r} on: {_line.strip()[:60]!r}")
    if revived:
        raise AssertionError(
            f"SYSTEM prompt reintroduced REFUTED flags as INSTRUCTION {revived} "
            f"— never tested against this image, 31 consecutive attempts failed "
            f"against them. C3 exists to keep them out.")
    # C1 is the whole point: a bare MGCraftProbe render command is 60fps against
    # a 30fps edit. Two traps here, both caught by the RED probes:
    #   - 'MGCraftProbe30' contains 'MGCraftProbe', so match the TOKEN.
    #   - C1 itself says "NEVER bare MGCraftProbe", so skip prohibiting lines
    #     exactly as the refuted-flag scan does.
    import re as _re
    bare = [ln.strip()[:60] for ln in system_text.splitlines()
            if _re.search(r"MGCraftProbe(?!30)(?![A-Za-z0-9_])", ln)
            and not any(p in ln for p in _PROHIBIT)]
    if bare:
        raise AssertionError(
            f"SYSTEM prompt names bare MGCraftProbe as INSTRUCTION {bare} — it "
            f"is 60fps and the edit is 30fps. C1 requires MGCraftProbe30.")


_assert_constraints_intact(SYSTEM)


# THINKING IS ON BY DEFAULT on claude-sonnet-5 when the `thinking` param is
# omitted — which this app does. That is where the ~42% output-token share
# comes from, and `effort` is the lever on it (default 'high').
#
# NOT thinking={"type":"disabled"}: on Sonnet 5 that makes the model measurably
# LESS likely to reach for tools, and this agent IS a tool loop — shell,
# inspect_output, read_knowledge, declare_placement. Cutting cost by making the
# agent stop calling tools would buy the number and lose the product. Lowering
# effort keeps adaptive thinking (and tool-eagerness) and reduces its depth.
DEFAULT_EFFORT = "high"


@app.function(image=IMG, secrets=SECRETS, timeout=3600, cpu=8, memory=16384)
def edit(source_key: str, brief: str, max_iters: int = MAX_ITERS,
         use_knowledge: bool = True, effort: str = DEFAULT_EFFORT,
         model: str = MODEL, route_models: bool = False,
         cheap_model: str = "claude-haiku-4-5",
         exec_model: str = MODEL) -> dict:
    import subprocess
    import boto3
    from anthropic import Anthropic

    t0 = time.time()
    led = {"failures": [], "iters": 0, "tokens": {"in": 0, "out": 0,
                                                  "cache_read": 0, "cache_write": 0}}

    def fail(kind, detail, cmd=None):
        """THE FAILURE LEDGER. Appended as it happens, never reconstructed."""
        led["failures"].append({"kind": kind, "detail": str(detail)[:400],
                                "cmd": (cmd or "")[:300],
                                "t": round(time.time() - t0, 1)})

    os.makedirs("/work", exist_ok=True)
    s3 = boto3.client("s3", region_name=os.environ.get("AWS_REGION") or "us-west-1")
    b = os.environ.get("S3_BUCKET_NAME") or BUCKET
    src = "/work/source.mp4"
    s3.download_file(b, source_key, src)
    dl_s = round(time.time() - t0, 1)

    # ── TRANSCRIPT (Deepgram — reused, not reinvented) ─────────────────────
    tw0 = time.time()
    from deepgram import DeepgramClient, PrerecordedOptions
    dg = DeepgramClient(api_key=os.environ["DEEPGRAM_API_KEY"])

    def _audio_of(path):
        """Word timings need AUDIO, not pixels. Run 5 died with an uncaught
        httpx.WriteTimeout pushing the 70MB source to Deepgram — and it died
        AFTER a working edit, losing everything, because this call sat outside
        the ledger. Sending ~1MB of mono 16k instead removes the timeout class
        rather than retrying through it."""
        a = path.rsplit(".", 1)[0] + ".dg.m4a"
        p = subprocess.run(
            ["ffmpeg", "-y", "-i", path, "-vn", "-ac", "1", "-ar", "16000",
             "-b:a", "64k", a], capture_output=True, text=True, timeout=300)
        if p.returncode != 0 or not os.path.exists(a):
            fail("audio_extract_failed", p.stderr[-400:])
            return path          # fall back to the video; worse, not fatal
        return a

    try:
        with open(_audio_of(src), "rb") as fh:
            dgr = dg.listen.prerecorded.v("1").transcribe_file(
                {"buffer": fh.read()},
                PrerecordedOptions(model="nova-3", language="multi",
                                   smart_format=True, punctuate=True,
                                   utterances=True, filler_words=True))
        d = dgr.to_dict() if hasattr(dgr, "to_dict") else json.loads(dgr.to_json())
        alt = d["results"]["channels"][0]["alternatives"][0]
        words = [{"w": w["word"], "s": round(w["start"], 3), "e": round(w["end"], 3)}
                 for w in (alt.get("words") or [])]
    except Exception as e:
        # Guarded because run 5 proved it can throw. An unguarded network call
        # here crashes the container and the failure taxonomy learns nothing —
        # the exact opposite of why the ledger exists.
        fail("source_transcribe_failed", e)
        return {"ok": False, "why": f"source transcribe failed: {e}",
                "ledger": led, "wall_s": round(time.time() - t0, 1)}
    transcript_s = round(time.time() - tw0, 1)
    if not words:
        fail("no_transcript", "Deepgram returned zero words")
        return {"ok": False, "why": "no transcript", "ledger": led}

    def probe(path):
        p = subprocess.run(
            ["ffprobe", "-v", "error", "-print_format", "json", "-show_format",
             "-show_streams", path], capture_output=True, text=True, timeout=120)
        try:
            return json.loads(p.stdout)
        except Exception:
            return {}

    def transcribe_words(path):
        """Transcribe the OUTPUT. This is the Urdu-incident check: an edit that
        exits 0 and plays can still have deleted the speech."""
        try:
            with open(_audio_of(path), "rb") as fh:
                r = dg.listen.prerecorded.v("1").transcribe_file(
                    {"buffer": fh.read()},
                    PrerecordedOptions(model="nova-3", language="multi",
                                       smart_format=True))
            dd = r.to_dict() if hasattr(r, "to_dict") else json.loads(r.to_json())
            a = dd["results"]["channels"][0]["alternatives"][0]
            return [w["word"].lower().strip(".,!?") for w in (a.get("words") or [])]
        except Exception as e:
            fail("output_transcribe_failed", e)
            return None

    def norm(ws):
        return [w.lower().strip(".,!?") for w in ws]

    def run_shell(cmd):
        try:
            p = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                               timeout=900, cwd="/work")
            if p.returncode != 0:
                fail("shell_nonzero", (p.stderr or "")[-400:], cmd)
            return {"exit": p.returncode,
                    "stdout": (p.stdout or "")[-1500:],
                    "stderr": (p.stderr or "")[-2500:]}
        except subprocess.TimeoutExpired:
            fail("shell_timeout", "900s", cmd)
            return {"exit": -1, "stdout": "", "stderr": "TIMEOUT after 900s"}

    def inspect():
        out = "/work/out.mp4"
        if not os.path.exists(out):
            fail("no_output", "out.mp4 does not exist")
            return {"exists": False,
                    "error": "/work/out.mp4 does not exist — nothing was rendered"}
        info = probe(out)
        v = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), {})
        a = next((s for s in info.get("streams", []) if s.get("codec_type") == "audio"), {})
        dur = float(info.get("format", {}).get("duration") or 0)
        res = {"exists": True, "duration_s": round(dur, 2),
               "width": v.get("width"), "height": v.get("height"),
               "vcodec": v.get("codec_name"), "has_audio": bool(a),
               "size_mb": round(os.path.getsize(out) / 1e6, 1)}
        if not a:
            fail("no_audio_stream", "output has no audio stream")
        if (v.get("width"), v.get("height")) != (1080, 1920):
            fail("wrong_resolution", f"{v.get('width')}x{v.get('height')}")
        # ── THE SPEECH CHECK ───────────────────────────────────────────────
        got = transcribe_words(out)
        if got is None:
            res["speech_check"] = "UNAVAILABLE — transcription failed, treat as UNVERIFIED"
        else:
            src_words = norm([w["w"] for w in words])
            got_set = {}
            for g in got:
                got_set[g] = got_set.get(g, 0) + 1
            missing, remaining = [], dict(got_set)
            for w in src_words:
                if remaining.get(w):
                    remaining[w] -= 1
                else:
                    missing.append(w)
            kept_ratio = 1.0 - (len(missing) / max(1, len(src_words)))
            res["speech_check"] = {
                "source_words": len(src_words), "output_words": len(got),
                "source_words_absent_from_output": len(missing),
                "kept_ratio": round(kept_ratio, 3),
                "sample_missing": missing[:25],
                "note": ("Some absence is EXPECTED — you deliberately cut words. "
                         "What must not happen is losing speech you meant to KEEP. "
                         "If output_words is far below what your edit should "
                         "contain, the render dropped audio."),
            }
            # THE GAP THE FIRST RUN EXPOSED. I ledgered only the total-loss
            # case, so a run that kept 12.7% of the speech recorded ZERO
            # failures — the ledger said clean while the content said
            # destroyed, which is the Urdu shape exactly. A check that
            # MEASURES loss but does not FLAG it is not a check.
            if len(got) == 0:
                fail("output_has_no_speech", "0 words transcribed from output")
            elif kept_ratio < 0.5:
                fail("speech_loss_severe",
                     f"kept_ratio {kept_ratio:.3f}: {len(missing)} of "
                     f"{len(src_words)} source words absent from the output")
            res["speech_check"]["VERDICT"] = (
                "FAIL — most of the speech is gone" if kept_ratio < 0.5
                else "OK" if kept_ratio >= 0.8
                else "SUSPECT — verify this was a deliberate cut")
        return res

    # ── knowledge served from the image, read on demand ────────────────────
    led["knowledge_reads"] = []
    led["cmds"] = []
    led["turns"] = []
    _knowledge_result_ids = {}   # tool_use_id -> filename

    def read_knowledge(name: str) -> dict:
        d = "/knowledge"
        if not os.path.isdir(d):
            fail("knowledge_dir_missing", d)
            return {"error": "knowledge not mounted"}
        avail = sorted(f for f in os.listdir(d) if f.endswith(".md"))
        if name in ("_index", "index", ""):
            idx = []
            for f in avail:
                p = os.path.join(d, f)
                head = ""
                try:
                    with open(p) as fh:
                        for line in fh:
                            if line.strip():
                                head = line.strip()[:90]
                                break
                except Exception:
                    pass
                idx.append({"file": f, "chars": os.path.getsize(p), "starts": head})
            return {"files": idx}
        cand = name if name in avail else next(
            (f for f in avail if name.lower() in f.lower()), None)
        if not cand:
            fail("knowledge_file_missing", f"{name} not in {avail}")
            return {"error": f"no such file: {name}", "available": avail}
        body = open(os.path.join(d, cand)).read()
        led["knowledge_reads"].append(cand)
        # Truncated per read: the MG catalogue alone is 35k chars and a single
        # unbounded read would blow the turn's budget on one file.
        return {"file": cand, "chars": len(body), "content": body[:24000],
                "truncated": len(body) > 24000}

    # ── INPUT 4: the Remotion skills, served by SEARCH ─────────────────────
    # 276 files / ~11MB cannot be browsed by an agent with a 32-turn budget, and
    # run 10 measured what extra reading burden does: MORE material produced
    # ok=False and zero shell commands. So this is grep, not a file list — the
    # agent asks "how do I X" and gets the lines that answer it.
    led["skill_searches"] = []
    led["skill_hits"] = 0

    def search_skills(query: str, max_hits: int = 12) -> dict:
        d = "/skills"
        if not os.path.isdir(d):
            fail("skills_dir_missing", d)
            return {"error": "skills not mounted"}
        q = (query or "").strip()
        if not q:
            return {"error": "empty query"}
        hits, scanned = [], 0
        for root, _dirs, files in os.walk(d):
            for fn in files:
                if not fn.endswith((".md", ".mdx")):
                    continue
                p = os.path.join(root, fn)
                scanned += 1
                try:
                    with open(p, errors="ignore") as fh:
                        lines = fh.read().splitlines()
                except Exception:
                    continue
                for i, line in enumerate(lines):
                    if q.lower() in line.lower():
                        ctx = "\n".join(lines[max(0, i - 2):i + 6])
                        hits.append({"file": os.path.relpath(p, d),
                                     "line": i + 1, "context": ctx[:900]})
                        if len(hits) >= max_hits:
                            break
                if len(hits) >= max_hits:
                    break
            if len(hits) >= max_hits:
                break
        led["skill_searches"].append({"q": q, "hits": len(hits)})
        led["skill_hits"] += len(hits)
        return {"query": q, "files_scanned": scanned, "hits": hits,
                "note": "Remotion API reference. Verify against "
                        "/promptly-remotion — the catalogue is the truth for "
                        "what EXISTS; these docs are the truth for HOW to call it."}

    # ── THE HARNESS DOES THE MECHANICS ──────────────────────────────────────
    # Measured on run 13: only 5 of 19 shell calls produced an artifact. The
    # dominant class was PREP — seven commands re-deriving cut boundaries and a
    # subtitle file from a word list the agent was already handed. That is
    # arithmetic, not editing, and it was being paid for at model rates.
    #
    # THE SPLIT IS DELIBERATE: the agent still decides WHICH spans to keep, which
    # is the whole editorial judgement. The harness does the segment maths, the
    # output-time remap and the subtitle generation, which have exactly one
    # correct answer. Nothing about what the edit SAYS moves into code here.
    led["build_cut_calls"] = 0

    def _srt_ts(t):
        h = int(t // 3600); m = int(t % 3600 // 60); s = t % 60
        return f"{h:02d}:{m:02d}:{s:06.3f}".replace(".", ",")

    def build_cut(keep_spans, words_per_cue=4):
        """keep_spans -> concat filter + output-time SRT. Returns the command."""
        try:
            spans = sorted([[float(a), float(b)] for a, b in keep_spans])
        except Exception as e:
            return {"error": f"keep_spans must be [[start,end],...]: {e}"}
        if not spans:
            return {"error": "keep_spans is empty"}
        dur = float(meta.get("format", {}).get("duration") or 0)
        bad = [s for s in spans if s[1] <= s[0] or s[0] < 0 or s[1] > dur + 0.05]
        if bad:
            return {"error": f"spans outside 0..{dur:.2f}s or non-increasing: {bad[:3]}"}
        for a, b in zip(spans, spans[1:]):
            if b[0] < a[1] - 1e-6:
                return {"error": f"overlapping spans: {a} and {b}"}

        # concat filter — the shape the agent hand-wrote every run
        parts, n = [], len(spans)
        for i, (a, b) in enumerate(spans):
            parts.append(f"[0:v]trim={a:.3f}:{b:.3f},setpts=PTS-STARTPTS[v{i}]")
            parts.append(f"[0:a]atrim={a:.3f}:{b:.3f},asetpts=PTS-STARTPTS[a{i}]")
        cat = "".join(f"[v{i}][a{i}]" for i in range(n))
        parts.append(f"{cat}concat=n={n}:v=1:a=1[outv][outa]")
        filt = ";".join(parts)
        with open("/work/filter.txt", "w") as fh:
            fh.write(filt)

        # OUTPUT-TIME REMAP — module-level and unit-tested, because this is the
        # step the agent got wrong twice by hand and the failure is SILENT: the
        # captions simply drift against the speech and ffmpeg exits 0.
        kept, cues = remap_words(spans, words), []
        for i in range(0, len(kept), words_per_cue):
            grp = kept[i:i + words_per_cue]
            cues.append((grp[0]["s"], grp[-1]["e"],
                         " ".join(g["w"] for g in grp).upper()))
        with open("/work/captions.srt", "w") as fh:
            for i, (s, e, txt) in enumerate(cues, 1):
                fh.write(f"{i}\n{_srt_ts(s)} --> {_srt_ts(e)}\n{txt}\n\n")

        led["build_cut_calls"] += 1
        out_dur = sum(b - a for a, b in spans)
        # DIAGNOSTIC: was nothing cut because the agent ran out of turns, or
        # because it CHOSE to keep everything? Coverage answers it directly —
        # one span covering the source is a decision, not an omission.
        led["keep_spans"] = [[round(a, 3), round(b, 3)] for a, b in spans]
        led["cut_coverage"] = {
            "spans": len(spans),
            "kept_s": round(out_dur, 2),
            "source_s": round(dur, 2),
            "coverage": round(out_dur / dur, 3) if dur else None,
        }
        return {
            "ok": True,
            "output_duration_s": round(out_dur, 3),
            "kept_words": len(kept), "source_words": len(words),
            "cues": len(cues),
            "filter_file": "/work/filter.txt",
            "captions_srt": "/work/captions.srt",
            "run_this": ("cd /work && filt=$(cat filter.txt) && ffmpeg -y -i source.mp4 "
                         "-filter_complex \"$filt\" -map '[outv]' -map '[outa]' "
                         "-c:v libx264 -crf 18 -preset veryfast -c:a aac cut.mp4"),
            "then_captions": ("cd /work && ffmpeg -y -i cut.mp4 -vf "
                              "\"subtitles=captions.srt:force_style='Fontname=DejaVu Sans,"
                              "Bold=1,FontSize=18,PrimaryColour=&H00FFFFFF,"
                              "OutlineColour=&H00000000,Outline=2,Alignment=2,MarginV=120'\" "
                              "-c:v libx264 -crf 18 -preset veryfast -c:a copy capped.mp4"),
            "note": "Captions are already remapped to OUTPUT time. Do not shift them.",
        }

    # ── OVERLAY FILTERGRAPH, BUILT BY THE HARNESS ───────────────────────────
    # Run 15's commands 7 and 8: the agent hand-wrote a drawtext filtergraph and
    # then `sed`-patched it to fix APOSTROPHE ESCAPING ("I''M EMPLOYED"). ffmpeg
    # filter syntax escaping is a mechanical rule with exactly one right answer,
    # it is famously easy to get wrong, and getting it wrong costs a turn plus a
    # re-encode. Same argument as build_cut: the agent picks the words and the
    # timings — the editorial content — and the harness renders them safely.
    _FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

    def _esc(t):
        """Escape text for an ffmpeg drawtext value. Order matters: backslash
        first or it re-escapes everything it just inserted."""
        return (str(t).replace("\\", r"\\\\").replace(":", r"\:")
                .replace("'", r"’" if False else "’")   # curly quote
                .replace("%", r"\%").replace(",", r"\,"))

    def build_overlays(items, burn_captions=True, input_file="cut.mp4",
                       output_file="out.mp4", extra_input=None):
        if not isinstance(items, list):
            return {"error": "items must be a list of {text,t_start,t_end}"}
        chain, errs = [], []
        if burn_captions and os.path.exists("/work/captions.srt"):
            chain.append(
                "subtitles=/work/captions.srt:force_style='Fontname=DejaVu Sans"
                ",Bold=1,FontSize=18,PrimaryColour=&H00FFFFFF"
                ",OutlineColour=&H00000000,Outline=2,Alignment=2,MarginV=120'")
        for i, it in enumerate(items):
            try:
                t0 = float(it["t_start"]); t1 = float(it["t_end"])
                txt = _esc(it["text"])
            except Exception as e:
                errs.append(f"item {i}: {e}"); continue
            if t1 <= t0:
                errs.append(f"item {i}: t_end <= t_start"); continue
            y = {"top": "h*0.14", "bottom": "h*0.78"}.get(
                str(it.get("position") or "top").lower(), "h*0.14")
            chain.append(
                f"drawtext=fontfile={_FONT}:text='{txt}':fontcolor=white"
                f":fontsize=64:borderw=6:bordercolor=black@0.9"
                f":x=(w-text_w)/2:y={y}"
                f":enable='between(t,{t0:.2f},{t1:.2f})'")
        if errs:
            return {"error": "bad items", "details": errs[:5]}
        if not chain:
            return {"error": "nothing to draw and no captions.srt"}
        with open("/work/overlays.txt", "w") as fh:
            fh.write(",".join(chain))
        led["build_overlays_calls"] = led.get("build_overlays_calls", 0) + 1
        extra = f" -i {extra_input}" if extra_input else ""
        return {
            "ok": True, "overlays": len(items),
            "captions_burned": burn_captions,
            "filter_file": "/work/overlays.txt",
            "run_this": (f"cd /work && filt=$(cat overlays.txt) && ffmpeg -y "
                         f"-i {input_file}{extra} -vf \"$filt\" -c:v libx264 "
                         f"-crf 18 -preset veryfast -c:a copy {output_file}"),
            "note": "Apostrophes and colons are already escaped. Do not sed this "
                    "file — hand-patching escaping is what cost a turn last run.",
        }

    # ── BATCHED COMPONENTS: one plan, one render, one composite ─────────────
    # Measured 2026-09-04, and the measurement changed the design. As a PNG
    # sequence PromptlyOverlay carries REAL alpha (empty frame mean alpha 0.00,
    # card frame 17.73), so it composites. But painting the FULL 58s timeline to
    # get 10 components is 1,740 frames / 169.3s / 128MB — WORSE than ten
    # separate renders (~161s). Packed back-to-back the same ten are 600 frames
    # / 72.2s / 75MB. The reel is what makes batching pay; batching over the
    # timeline does not.
    led["reel_renders"] = 0

    def render_components(items):
        if not isinstance(items, list) or not items:
            return {"error": "items must be a non-empty list of placements"}
        for i, it in enumerate(items):
            if not isinstance(it, dict) or "t_start" not in it:
                return {"error": f"item {i} needs t_start (output seconds)"}
        packed = pack_reel(items, 30)
        plan = {
            "sourceUrl": "", "fps": 30, "width": 1080, "height": 1920,
            "totalDurationInFrames": max(1, packed["reel_frames"]),
            "clips": [], "transitions": [], "broll": [], "textOverlays": [],
            "caption": {"style": "CleanCut", "pages": [], "keywords": [],
                        "positionSegments": [{"fromFrame": 0,
                                              "toFrame": max(1, packed["reel_frames"]),
                                              "position": "bottom"}]},
            "motionGraphics": packed["reel"], "outro": "none",
        }
        with open("/work/reel-plan.json", "w") as fh:
            json.dump({"input": plan}, fh)
        # ONE render. --sequence to a DIRECTORY with NO extension: any extension
        # is refused ("sequence cannot have an extension"), and every VIDEO codec
        # available here flattens the alpha (prores/vp8/vp9 all yuv, and
        # --pixel-format=yuva* is rejected outright). PNG is the only path that
        # keeps it.
        subprocess.run("rm -rf /work/reel", shell=True)
        r = subprocess.run(
            "cd /promptly-remotion && npx remotion render PromptlyOverlay /work/reel "
            "--props=/work/reel-plan.json --sequence --image-format=png",
            shell=True, capture_output=True, text=True, timeout=1800)
        if r.returncode != 0:
            fail("reel_render_failed", (r.stderr or "")[-300:])
            return {"error": "reel render failed", "stderr": (r.stderr or "")[-400:]}
        pngs = sorted(f for f in os.listdir("/work/reel") if f.endswith(".png")) \
            if os.path.isdir("/work/reel") else []
        if len(pngs) < packed["reel_frames"]:
            fail("reel_short", f"{len(pngs)} frames rendered, expected "
                               f"{packed['reel_frames']}")
        led["reel_renders"] += 1
        # Reel PNGs -> one alpha-carrying mov. qtrle is fine in FFMPEG (it is
        # only the REMOTION --codec flag that rejects it).
        subprocess.run(
            "cd /work/reel && ffmpeg -y -v error -framerate 30 -pattern_type glob "
            "-i '*.png' -c:v qtrle -pix_fmt argb /work/reel.mov",
            shell=True, capture_output=True, text=True, timeout=900)

        # THE COMPOSITE. Each reel window is trimmed and shifted to the OUTPUT
        # time the agent authored — two clocks, and pack_reel is the only thing
        # that maps between them.
        parts, last = [], "0:v"
        for k, sg in enumerate(packed["segments"]):
            parts.append(
                f"[1:v]trim=start={sg['reel_from_s']}:end={sg['reel_to_s']},"
                f"setpts=PTS-STARTPTS+{sg['out_at_s']}/TB[c{k}]")
            parts.append(
                f"[{last}][c{k}]overlay=0:0:enable='between(t,{sg['out_at_s']},"
                f"{round(sg['out_at_s'] + sg['duration_s'], 4)})'[m{k}]")
            last = f"m{k}"
        with open("/work/reel-filter.txt", "w") as fh:
            fh.write(";".join(parts))
        return {
            "ok": True, "components": len(items),
            "reel_frames": packed["reel_frames"],
            "reel_seconds": round(packed["reel_frames"] / 30, 2),
            "rendered_frames": len(pngs),
            "segments": packed["segments"],
            "run_this": (f"cd /work && filt=$(cat reel-filter.txt) && ffmpeg -y -i "
                         f"cut.mp4 -i reel.mov -filter_complex \"$filt\" "
                         f"-map '[{last}]' -map 0:a -c:v libx264 -crf 18 "
                         f"-preset veryfast -c:a copy out.mp4"),
            "note": "ONE render for all components. Offsets are already computed "
                    "— do not shift anything by hand.",
        }

    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    tl = "\n".join(f"[{w['s']:.2f}-{w['e']:.2f}] {w['w']}" for w in words)
    meta = probe(src)
    vs = next((s for s in meta.get("streams", []) if s.get("codec_type") == "video"), {})
    # PRECOMPUTED DEAD AIR — mechanical, so the harness does it. Run 13 spent
    # commands 1/2/4 deriving exactly this from the word list it was given.
    # NOTE THE VARIABLE NAMES. `b` at function scope is the S3 BUCKET (line
    # ~666), and an earlier version of this loop used `for a, b in ...`, which
    # rebound it to a word dict and killed the upload 300s later with
    # "expected string or bytes-like object, got 'dict'". pyflakes cannot see
    # it — a rebind is legal — and it is the exact shadowing class this repo
    # has already paid for once.
    _gaps = []
    for _w0, _w1 in zip(words, words[1:]):
        _g = _w1["s"] - _w0["e"]
        if _g >= 0.35:
            _gaps.append((round(_w0["e"], 2), round(_w1["s"], 2), round(_g, 2)))
    # ── NUMBER BEATS — the candidates for a component, found MECHANICALLY ───
    # The standing open problem in this lane: C1-C6 fix HOW to render a card and
    # nothing makes the card EXIST. The rule is conditioned ("if you place a
    # CARD whose hero is a NUMBER...") and the agent simply never places one, so
    # the condition never fires. The harness therefore identifies the candidates
    # itself — a word that IS a number is not a judgement call — and the gate
    # below makes the agent rule on each one. It still decides; it can no longer
    # decline to consider.
    _NUMWORD = re.compile(
        r"^(?:\d[\d,.]*|one|two|three|four|five|six|seven|eight|nine|ten|"
        r"eleven|twelve|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|"
        r"hundred|thousand|million|billion|percent|half|double|triple)$", re.I)
    _number_beats = [{"t": round(w["s"], 2), "word": w["w"]}
                     for w in words if _NUMWORD.match(str(w["w"]).strip(".,!?"))]
    led["number_beats"] = _number_beats
    _beats = segment_beats(words)
    _numeric_ts = {b["t"] for b in _number_beats}
    for _b in _beats:
        _b["has_number"] = any(_b["t_start"] <= t <= _b["t_end"] for t in _numeric_ts)
    led["beats"] = _beats
    led["beat_verdicts"] = []
    led["component_verdicts"] = []   # legacy field, retained so old runs still parse

    _gap_txt = ("\n".join(f"  [{_s:.2f}-{_e:.2f}] {_g2:.2f}s"
                          for _s, _e, _g2 in _gaps)
                or "  (none over 0.35s)")
    # THE CHECK for the shadowing class above: `b` must still be the bucket
    # string by the time we reach the agent loop. Costs nothing, and turns a
    # 300s-later TypeError inside s3transfer into an immediate, named failure.
    if not isinstance(b, str):
        raise AssertionError(
            f"S3 bucket `b` was rebound to {type(b).__name__} before the agent "
            f"loop — a loop variable shadowed it. Upload would fail after the "
            f"whole edit had already been paid for.")
    _src_dur = float(meta.get('format', {}).get('duration') or 0)
    user = (f"BRIEF: {brief}\n\n"
            f"SOURCE: /work/source.mp4 — {vs.get('width')}x{vs.get('height')}, "
            f"{_src_dur:.1f}s\n\n"
            f"TRANSCRIPT ({len(words)} words):\n{tl}\n\n"
            f"DEAD AIR ALREADY DETECTED ({len(_gaps)} gaps >=0.35s) — you do not "
            f"need to compute these:\n{_gap_txt}\n\n"
            f"BEATS ({len(_beats)}) — rule on EVERY one with `beat_verdict`:\n"
            + "\n".join(f"  [{b['i']}] {b['t_start']:.2f}-{b['t_end']:.2f}"
                        + ("  (has a number)" if b["has_number"] else "")
                        + f"  {b['text'][:90]}" for b in _beats) + "\n\n"
            f"Decide the spans to KEEP, then call `build_cut` with them. It "
            f"returns the ffmpeg command and an output-time .srt — do not build "
            f"either by hand.\n\n"
            f"Produce /work/out.mp4. Verify with inspect_output before DONE.")

    # cache_control on the system block: run 2 reported cache_read 0 and cost
    # $0.5351 against a $0.10 law. The system text is identical across every turn
    # of every job, so it is the one block that can actually be reused.
    sys_text = SYSTEM + (_KNOWLEDGE_SYSTEM if use_knowledge else "")
    sys_blocks = [{"type": "text", "text": sys_text,
                   "cache_control": {"type": "ephemeral"}}]
    tools = TOOLS + (list(KNOWLEDGE_TOOLS) if use_knowledge else [])
    led["use_knowledge"] = use_knowledge
    # ARM LABEL. Run 3 was reported as a knowledge arm without having read the
    # knowledge; an effort arm that does not record its effort is the same
    # class of unfalsifiable claim.
    led["effort"] = effort
    led["model"] = model
    led["route_models"] = route_models
    led["max_iters"] = max_iters

    # List form, not a bare string: a string content block cannot carry a
    # cache_control marker, and this message holds the full transcript.
    msgs = [{"role": "user", "content": [{"type": "text", "text": user}]}]
    final_text = ""
    for it in range(max_iters):
        led["iters"] = it + 1
        # KNOWLEDGE EVICTION: TRIED AND REVERTED 2026-09-01. Modelled $0.51 ->
        # $0.28 by dropping read files from history. MEASURED $0.51 -> $0.7688,
        # WORSE. Mutating message history INVALIDATES THE CACHE PREFIX, so every
        # eviction forced the whole downstream context to be re-written:
        # cache_write 53,992 -> 89,829. Cache_read fell exactly as predicted and
        # the write cost more than swallowed it. The agent also re-read
        # 15_ffmpeg_placement_recipes.md THREE times, paying for the same file
        # repeatedly and burning turns.
        # Eviction and prefix caching are structurally in conflict: you cannot
        # rewrite history and keep a prefix. The cost lever has to be fewer or
        # shorter turns, or a smaller RESIDENT knowledge set -- not mutation.
        # ROLLING CACHE BREAKPOINT. Run 3 cached only the system block and read
        # back 21,549 of 360,147 input tokens — 6%. The bulk is the message
        # history, which is re-sent in full every turn and grows by a 24k
        # knowledge file each time one is read. Marking the tail of the history
        # makes the whole prefix cacheable. The marker MUST move each turn and
        # the previous one must be cleared: stale breakpoints burn the 4-block
        # budget and silently stop caching anything.
        for m in msgs:
            if isinstance(m.get("content"), list):
                for blk in m["content"]:
                    if isinstance(blk, dict):
                        blk.pop("cache_control", None)
        for m in reversed(msgs):
            if isinstance(m.get("content"), list) and m["content"]:
                tail = m["content"][-1]
                if isinstance(tail, dict):
                    tail["cache_control"] = {"type": "ephemeral"}
                break
        # ── MODEL ROUTING ───────────────────────────────────────────────────
        # Measured on run M: Haiku's VERDICTS are indistinguishable from
        # Sonnet's — 19/19 ruled, 19/19 distinct, and 19 of 19 cited their own
        # beat against Sonnet's 17 — but it then never executed them. It ruled
        # 2 beats "card" and rendered nothing. Judgement is cheap; execution is
        # not, and 78% of the bill sits on the side that held up.
        #
        # So the phase boundary is "are all beats ruled yet". While any beat is
        # unruled the run is still deciding -> cheap. Once every beat has a
        # verdict the run is building -> expensive. C8/C9 already push the agent
        # to rule everything before rendering, so the routing follows the
        # workflow rather than fighting it.
        #
        # NOTE: build_cut can land in EITHER phase depending on when the agent
        # calls it. The ledger records the model per turn, so the actual split
        # is reported rather than assumed.
        if route_models:
            _all_ruled = bool(_beats) and not [
                b for b in _beats
                if b["i"] not in {v.get("beat") for v in led.get("beat_verdicts") or []}]
            model = exec_model if _all_ruled else cheap_model
        led.setdefault("turn_models", []).append(model)

        # output_config.effort is a 4.6+/5 parameter. Haiku 4.5 rejects the whole
        # request with a 400, so the cheaper-model arm died at turn 1 for $0.00.
        # Worth stating plainly: "same config, cheaper model" is NOT literally
        # available — dropping effort is itself a second variable, and the arm
        # has to be read as such.
        _kw = {"output_config": {"effort": effort}} if _supports_effort(model) else {}
        led["effort_sent"] = bool(_kw)
        try:
            r = client.messages.create(
                model=model, max_tokens=MAX_TOKENS, system=sys_blocks, tools=tools,
                messages=msgs, **_kw)
        except Exception as e:
            fail("model_call_failed", e)
            break
        u = getattr(r, "usage", None)
        if u:
            led["tokens"]["in"] += getattr(u, "input_tokens", 0) or 0
            led["tokens"]["out"] += getattr(u, "output_tokens", 0) or 0
            led["tokens"]["cache_read"] += getattr(u, "cache_read_input_tokens", 0) or 0
            led["tokens"]["cache_write"] += getattr(u, "cache_creation_input_tokens", 0) or 0
            # PER-MODEL BUCKETS. A routed run mixes two rate cards, so costing
            # aggregate tokens at one rate is wrong — the same class of error as
            # billing Haiku at Sonnet rates, and it lands on the arm's headline
            # number. Attribute each turn's tokens to the model that produced
            # them.
            _pm = led.setdefault("tokens_by_model", {}).setdefault(
                model, {"in": 0, "out": 0, "cache_read": 0, "cache_write": 0})
            _pm["in"] += getattr(u, "input_tokens", 0) or 0
            _pm["out"] += getattr(u, "output_tokens", 0) or 0
            _pm["cache_read"] += getattr(u, "cache_read_input_tokens", 0) or 0
            _pm["cache_write"] += getattr(u, "cache_creation_input_tokens", 0) or 0
        msgs.append({"role": "assistant", "content": r.content})
        tool_uses = [c for c in r.content if getattr(c, "type", "") == "tool_use"]
        led["turns"].append({
            "n": it + 1,
            "tools": [getattr(c, "name", "?") for c in tool_uses],
            "out_tokens": getattr(u, "output_tokens", 0) if u else 0,
            "stop": getattr(r, "stop_reason", None),
        })
        texts = " ".join(getattr(c, "text", "") for c in r.content
                         if getattr(c, "type", "") == "text")
        final_text = texts or final_text
        if not tool_uses:
            # THE SILENT DEATH, runs 10 and 11 (~$0.46 for zero information).
            # A model turn with no tool_use is AMBIGUOUS: it is either the agent
            # finishing ("DONE") or the agent stopping dead. The old code broke
            # on both and logged NEITHER, so a run that produced no video at all
            # returned ok=False with an EMPTY ledger — the one state the ledger
            # exists to make impossible.
            #
            # Distinguish them by the ARTIFACT, not by the prose: if /work/out.mp4
            # is absent, the agent stopped without delivering, and that is a
            # failure with a stop_reason attached.
            _sr = getattr(r, "stop_reason", None)
            if _sr == "max_tokens":
                # RECOVERABLE, not fatal: the turn was cut off, not refused.
                # Breaking here threw away a working run. Tell the agent what
                # happened and let it continue with smaller commands.
                fail("response_truncated",
                     f"turn {it + 1}: stop_reason=max_tokens at {MAX_TOKENS} "
                     f"tokens — the command was cut off mid-write. Continuing "
                     f"with an instruction to split it.")
                msgs.append({"role": "user", "content": [{"type": "text", "text":
                    "Your last response was CUT OFF at the token limit before the "
                    "command completed. Do not rebuild it as one giant filtergraph. "
                    "Split the work: run several smaller ffmpeg commands in "
                    "sequence, each writing an intermediate file, and verify as "
                    "you go."}]})
                continue
            if not os.path.exists("/work/out.mp4"):
                fail("agent_stopped_without_output",
                     f"turn {it + 1}/{max_iters}: no tool_use and no /work/out.mp4. "
                     f"stop_reason={_sr!r}, text={(texts or '')[:300]!r}, "
                     f"shell_cmds_run={len(led.get('cmds') or [])}")
                break

            # ── THE ONE GATE: every beat ruled ──────────────────────────────
            # Replaced three gates (C8 numbers, C9 components, C10 the cut).
            # Each forced a FAMILY, and forcing one starved the others —
            # measured: adding the cut gate took cards 0.91 -> 0.23 per 25s on a
            # source where the two prior runs had both rendered 4. Competition
            # was the structure, not the agent.
            #
            # One question per beat — card, text or nothing, kept or cut —
            # so there is nothing to trade off against. Fires once; a gate that
            # can re-prompt forever is a spend loop.
            _ruled_beats = {v.get("beat") for v in (led.get("beat_verdicts") or [])}
            _unruled = [b for b in _beats if b["i"] not in _ruled_beats]
            if _beats and _unruled and not led.get("beat_gate_fired"):
                led["beat_gate_fired"] = True
                fail("beat_gate_blocked_done",
                     f"finished with {len(_unruled)} of {len(_beats)} beats unruled")
                _lst = "\n".join(
                    f"  [{b['i']}] {b['t_start']:.2f}-{b['t_end']:.2f}"
                    + ("  (has a number)" if b["has_number"] else "")
                    + f"  {b['text'][:80]}" for b in _unruled[:20])
                msgs.append({"role": "user", "content": [{"type": "text", "text":
                    f"NOT DONE. {len(_unruled)} of {len(_beats)} beats have no "
                    f"ruling:\n" + _lst + "\n\nFor EACH, call `beat_verdict` "
                    "with treatment ('card' | 'text' | 'none'), cut ('keep' | "
                    "'cut') and a `why` about THAT beat's content. 'none' and "
                    "'keep' are legitimate answers — not deciding is not. If any "
                    "beat earns a card, render them ALL in one `render_components` "
                    "call, then composite."}]})
                continue

            break
        if it == max_iters - 1:
            fail("iteration_budget_exhausted",
                 f"stopped after {max_iters} turns with the agent still working "
                 f"— it never reached its own self-review")
        results = []
        for tu in tool_uses:
            if tu.name == "shell":
                _c = tu.input.get("cmd", "")
                # ── THE PRECONDITION GATE ───────────────────────────────────
                # Mounting and prompting were BOTH insufficient: run 11 had
                # /skills mounted, `search_skills` in the tool list and a
                # prompt paragraph telling it to search instead of guessing,
                # and made ZERO calls. Same shape as the rules in runs 8/9 —
                # presence, then even reading, produced no behaviour change.
                # What this agent follows is REQUIREMENTS, so the reference is
                # now a precondition of the render rather than advice about it.
                #
                # Blocks the FIRST component render only, and opens on one CALL
                # rather than one HIT — a hitless query must not deadlock the
                # run. `remotion_skills` still reports searched_no_hits in that
                # case, so opening the gate can never be mistaken for value.
                if False:  # C7 search gate retired with its prompt block
                    out = {}
                else:
                    led["cmds"].append(_c[:4000])
                    out = run_shell(_c)
            elif tu.name == "inspect_output":
                # ── THE VERIFICATION CAP (E2, ENFORCED) ─────────────────────
                # Run 14 measured the problem: removing the prep work took
                # shell calls 19 -> 12 but turns only 26 -> 21, because
                # inspect_output went 1 -> 6. The agent expanded to fill the
                # budget, verifying six times against E2's "verify once". So
                # the floor is set by turns the agent CHOOSES to take, not by
                # how much mechanical work exists — and E2 as advice did not
                # bind. Same as C7: enforce it in the tool layer.
                #
                # ONE PASS, plus ONE retry ONLY if the pass actually failed.
                # A verification that came back OK has nothing to re-check;
                # a second look at a passing output is pure cost.
                _iv = led.setdefault("inspect_verdicts", [])
                _first_failed = bool(_iv) and _iv[0] != "OK"
                _allowed = 1 + (1 if _first_failed else 0)
                if len(_iv) >= _allowed:
                    led["inspect_cap_blocks"] = led.get("inspect_cap_blocks", 0) + 1
                    fail("inspect_cap_blocked",
                         f"inspect_output call {len(_iv) + 1} refused "
                         f"(allowed {_allowed}; first verdict {_iv[0]!r})")
                    out = {"blocked": True,
                           "error": f"VERIFICATION BUDGET SPENT ({_allowed} of "
                                    f"{_allowed} used).",
                           "first_verdict": _iv[0],
                           "why": "One pass, plus one retry only if the pass "
                                  "failed. Re-checking an output that already "
                                  "verified buys nothing and costs a turn.",
                           "do_now": "If the last verdict was OK, say DONE. If "
                                     "it was not, FIX the edit and finish — you "
                                     "have no further checks."}
                else:
                    out = inspect()
                    _v = ((out.get("speech_check") or {}).get("VERDICT")
                          or ("NO_OUTPUT" if out.get("exists") is False else "OK"))
                    _iv.append("OK" if str(_v).startswith("OK") else str(_v)[:40])
            elif tu.name == "declare_placement":
                _p = dict(tu.input or {})
                led.setdefault("placements", []).append(_p)
                out = {"recorded": True, "total": len(led["placements"])}
            elif tu.name == "read_knowledge":
                out = read_knowledge(tu.input.get("file", "_index"))
                _knowledge_result_ids[tu.id] = tu.input.get("file", "_index")
            elif tu.name == "build_cut":
                out = build_cut(tu.input.get("keep_spans") or [],
                                int(tu.input.get("words_per_cue") or 4))
            elif tu.name == "build_overlays":
                out = build_overlays(tu.input.get("items") or [],
                                     bool(tu.input.get("burn_captions", True)),
                                     tu.input.get("input_file") or "cut.mp4",
                                     tu.input.get("output_file") or "out.mp4",
                                     tu.input.get("extra_input"))
            elif tu.name == "component_verdict":
                _v = {"t": tu.input.get("t"),
                      "decision": tu.input.get("decision"),
                      "why": str(tu.input.get("why") or "")}
                led["component_verdicts"].append(_v)
                out = {"recorded": True,
                       "ruled": len(led["component_verdicts"]),
                       "of": len(_number_beats)}
            elif tu.name == "render_components":
                out = render_components(tu.input.get("items") or [])
            elif tu.name == "rule_all_beats":
                _incoming = tu.input.get("verdicts") or []
                _seen = {v.get("beat") for v in led["beat_verdicts"]}
                _added = 0
                for _v in _incoming:
                    if not isinstance(_v, dict) or _v.get("beat") is None:
                        continue
                    if _v.get("beat") in _seen:
                        continue        # first ruling wins; a re-call tops up
                    led["beat_verdicts"].append({
                        "beat": _v.get("beat"), "treatment": _v.get("treatment"),
                        "cut": _v.get("cut"), "why": str(_v.get("why") or "")})
                    _seen.add(_v.get("beat")); _added += 1
                _missing = [b["i"] for b in _beats if b["i"] not in _seen]
                out = {"recorded": _added, "ruled": len(_seen),
                       "of": len(_beats), "still_missing": _missing[:30]}
            elif tu.name == "beat_verdict":
                _bv = {"beat": tu.input.get("beat"),
                       "treatment": tu.input.get("treatment"),
                       "cut": tu.input.get("cut"),
                       "why": str(tu.input.get("why") or "")}
                led["beat_verdicts"].append(_bv)
                out = {"recorded": True,
                       "ruled": len({v["beat"] for v in led["beat_verdicts"]}),
                       "of": len(_beats)}
            elif tu.name == "cut_verdict":
                led["cut_verdict"] = {"decision": tu.input.get("decision"),
                                      "why": str(tu.input.get("why") or "")}
                out = {"recorded": True}
            elif tu.name == "search_skills":
                out = search_skills(tu.input.get("query", ""),
                                    int(tu.input.get("max_hits") or 12))
            else:
                out = {"error": f"unknown tool {tu.name}"}
                fail("unknown_tool", tu.name)
            # Knowledge reads get a wider cap than shell output. At 6000 the
            # 24k-char read above would arrive as a quarter of a file and the
            # agent would silently act on a fragment.
            cap = 26000 if tu.name == "read_knowledge" else 6000
            results.append({"type": "tool_result", "tool_use_id": tu.id,
                            "content": json.dumps(out)[:cap]})
        msgs.append({"role": "user", "content": results})

    final = inspect() if os.path.exists("/work/out.mp4") else {"exists": False}
    key = None
    if final.get("exists"):
        key = f"agentic-editor/{int(time.time())}-{os.path.basename(source_key)}"
        s3.upload_file("/work/out.mp4", b, key,
                       ExtraArgs={"ContentType": "video/mp4"})
    # Run 3 read back 21,549 of 360,147 input tokens (6%) while LOOKING fine —
    # nothing errors when a cache breakpoint is misplaced, the bill just stays
    # high. A ratio this low past a few turns means the rolling breakpoint is
    # broken, so it fails LOUDLY here instead of being found in a cost report.
    _tin, _cr = led["tokens"]["in"], led["tokens"]["cache_read"]
    if led["iters"] >= 4 and (_cr / max(_tin + _cr, 1)) < 0.25:
        fail("prompt_cache_ineffective",
             f"cache_read {_cr:,} vs input {_tin:,} over {led['iters']} turns "
             f"({_cr / max(_tin + _cr, 1) * 100:.1f}%) — the rolling breakpoint "
             f"is not landing; every turn is re-billed at full input price")

    # ARM-SPECIFIC. Run 8 read four knowledge files, NONE of them the arm's, and
    # this check stayed green — so the render was reported as a rules arm when the
    # rules were never opened. "Some knowledge was read" is not the claim being
    # tested; "THIS file was read" is.
    # PER-INPUT, NOT PER-FILE. The lane has four named inputs and until now only
    # ONE of them (the rules) was asserted, so a run could be reported as "all
    # four wired" while three were never touched. Each input reports one of:
    #   read           — the agent actually used it
    #   mounted_unread — present in the image, never touched  -> FAIL
    #   not_mounted    — structurally unreachable             -> FAIL, different
    # Those last two are DIFFERENT failures and must not collapse into one: for
    # ten weeks the skills were not "ignored", they were on a laptop the
    # container could not see, and calling that "unread" would have sent someone
    # to fix the prompt.
    _cmds_join = " ".join(led.get("cmds") or [])
    _inputs = {
        # 1. the rules — the two files that say WHERE families go and HOW to draw
        "rules": {
            "mounted": os.path.isdir("/knowledge"),
            "used": [f for f in REQUIRED_KNOWLEDGE
                     if f in (led.get("knowledge_reads") or [])],
            "want": REQUIRED_KNOWLEDGE,
        },
        # 2. the component catalogue — reading it means RUNNING against it
        "remotion_catalogue": {
            "mounted": os.path.isdir("/promptly-remotion"),
            # THIRD TIME THIS CLASS BIT. render_components drives the catalogue
            # via subprocess, so it never appears in the shell log — the audit
            # had the same hole, and so did the renders display. A reel render
            # IS use of /promptly-remotion.
            "used": (["/promptly-remotion"] if "/promptly-remotion" in _cmds_join
                     else (["reel render"] if led.get("reel_renders") else [])),
            "want": ["/promptly-remotion"],
        },
        # 3. the API reference — used means at least one search returned hits
        "remotion_skills": {
            "mounted": os.path.isdir("/skills"),
            "used": [s["q"] for s in (led.get("skill_searches") or []) if s["hits"]],
            "want": [">=1 search with hits"],
        },
        # 5. the real asset library — sounds on disk plus the tables that make
        # them placeable. "Used" means a command actually referenced /assets;
        # reading the inventory alone is not using the library.
        "asset_library": {
            "mounted": os.path.isdir("/assets/sounds")
                       and os.path.isfile("/assets/inventory.json"),
            "used": ["/assets"] if "/assets" in _cmds_join else [],
            "want": ["/assets"],
        },
        # 4. Karpathy behaviour — RESIDENT in the SYSTEM prompt, not a tool read.
        # It governs every turn, so a read-count is the wrong instrument; the
        # question is whether it is in the prompt the model was actually sent.
        # Verified against sys_text, NOT the module constant, so an arm that
        # ships a stripped prompt cannot pass on the constant's behalf.
        "karpathy_behaviour": {
            "mounted": all(k in sys_text for k in ("K1.", "K2.", "K3.", "K4.")),
            "used": [k for k in ("K1.", "K2.", "K3.", "K4.") if k in sys_text],
            "want": ["K1.", "K2.", "K3.", "K4."],
            "resident": True,
        },
    }
    for _name, _i in _inputs.items():
        _i["status"] = ("not_mounted" if not _i["mounted"]
                        else "read" if _i["used"] else "mounted_unread")
    # SEARCHED BUT FOUND NOTHING is its own state. The C7 gate opens on one
    # CALL (a hitless query must not deadlock a run), so without this a search
    # that returned zero hits would satisfy the gate and then report as plain
    # `mounted_unread` — indistinguishable from never having searched, which is
    # the exact collapse the three-status split exists to prevent.
    _rs = _inputs["remotion_skills"]
    if _rs["status"] == "mounted_unread" and (led.get("skill_searches") or []):
        _rs["status"] = "searched_no_hits"
        _rs["queries_tried"] = [s["q"] for s in led["skill_searches"]]
    led["skill_gate_blocks"] = led.get("skill_gate_blocks", 0)
    led["inputs"] = _inputs
    # CLIP-BRAIN IS DELIBERATELY ABSENT, recorded so its absence is a DECISION in
    # the ledger rather than an omission someone rediscovers. See CLIP_BRAIN_
    # VERDICT.md: both findings are negatives, and the surviving one describes a
    # stage this editor does not perform.
    led["inputs"]["clip_brain"] = {"mounted": False, "used": [],
                                   "status": "parked_permanently",
                                   "why": "no rule survives; see CLIP_BRAIN_VERDICT.md"}

    if use_knowledge:
        _unmounted = [k for k, v in _inputs.items() if v["status"] == "not_mounted"]
        _unread = [k for k, v in _inputs.items() if v["status"] == "mounted_unread"]
        if _unmounted:
            fail("required_input_not_mounted",
                 f"{_unmounted} are NOT IN THE IMAGE — the agent could not have "
                 f"used them at any price. This is not an unread input, it is an "
                 f"absent one, and no prompt change can fix it.")
        # Distinct from unread, because the remedies are opposite: unread means
        # push the agent at it, no-hits means the queries or the MOUNT are
        # wrong. 276 files should answer a plausible Remotion question.
        if _rs["status"] == "searched_no_hits":
            # THE MOUNT IS NOT THE SUSPECT — that was checked and cleared
            # 2026-09-03: 282 md files land at /skills, `interpolate` hits 46
            # of them. The corpus is COMPONENT-AUTHORING docs and does not
            # document the CLI (`--props`: 0 files), which is what the first
            # gated run searched for twice. So zero hits means query/corpus
            # MISFIT, and the fix is the prompt telling the agent what the
            # reference covers — not remounting anything.
            fail("skills_searched_zero_hits",
                 f"{len(led.get('skill_searches') or [])} search(es) returned "
                 f"NOTHING: {_rs.get('queries_tried')}. The mount is known good "
                 f"(282 files); this is a query/corpus misfit. CLI flags are not "
                 f"in there — they are in C4 and recipe 15.")
        if _unread:
            fail("required_input_unread",
                 f"{_unread} mounted but never touched (rules read: "
                 f"{led.get('knowledge_reads')}; skill searches: "
                 f"{len(led.get('skill_searches') or [])}; "
                 f"/promptly-remotion in cmds: "
                 f"{'/promptly-remotion' in _cmds_join}) — this run is NOT the "
                 f"arm it claims to be and must not be compared as one")

    # ── FAMILY MIX — THE MANIFEST IS THE INSTRUMENT. OP-COUNTING IS RETIRED ──
    # Op-counting was always a guess wearing a number's clothes, and this run
    # measured the gap directly: the ops said `caption_burn: 3` where the
    # manifest said ONE caption track. A filter name cannot tell a caption burn
    # from an overlay text, cannot tell WHICH beat a placement serves, and
    # cannot see a placement rendered by Remotion at all. Four runs were misread
    # that way. `declare_placement` carries type + method + why, so it answers
    # all three, and it is now what the rates are computed from.
    #
    # The op-count SURVIVES ONLY AS A CROSS-CHECK below — never as a reported
    # family rate. A manifest nobody audits is just prose with a schema.
    _c = " ".join(led.get("cmds") or [])
    _dur = float((final or {}).get("duration_s") or 0) or 1.0
    _per25 = lambda n: round(n / _dur * 25.0, 2)
    _pl = led.get("placements") or []
    _n_of = lambda t: sum(1 for p in _pl if p.get("type") == t)
    _mix = {
        "source": "manifest",           # never 'ops' again
        "declared": len(_pl),
        "text": _n_of("overlay_text"),
        "cards": _n_of("card"),
        "cutaways": _n_of("cutaway"),
        "caption_tracks": _n_of("caption_track"),
        "emphasis": _n_of("emphasis"),
        "sfx": _n_of("sfx"),
        "by_remotion": sum(1 for p in _pl if p.get("method") == "remotion"),
        "by_ffmpeg": sum(1 for p in _pl if p.get("method") == "ffmpeg"),
        # COMMAND FACTS, kept because they are about what RAN, not what was
        # placed. WHICH composition, not just whether Remotion ran — a probe
        # render is the harness, the product comp is the catalogue.
        "remotion_renders": _c.count("remotion render"),
        "product_comp": _c.count("PromptlyOverlay") + _c.count("PromptlyMicroSegments"),
        # RENDER commands only — same false-positive class as the C1 check
        # below: a `grep -i MGCraftProbe` used to discover what exists counted
        # as a probe render, so this reported 2 where 1 render ran.
        "probe_comp": sum(x.count("FrameCompProbe") + x.count("MGCraftProbe")
                          for x in (led.get("cmds") or []) if "remotion render" in x),
        "shell_cmds": len(led.get("cmds") or []),
        # Counted so the rubric has a number for them. cut_spans is the real
        # cut count — a cut is a SPAN BOUNDARY, not a placement, which is why
        # it was never in the manifest and never reported.
        "cut_spans": max(0, len(led.get("keep_spans") or []) - 1),
        "transitions": _n_of("transition"),
    }
    _mix["text_per_25s"] = _per25(_mix["text"])
    _mix["card_per_25s"] = _per25(_mix["cards"])
    _mix["cutaway_per_25s"] = _per25(_mix["cutaways"])
    led["family_mix"] = _mix

    # ── ARE THE VERDICTS SUBSTANTIVE, OR JUST CLEARING THE GATE? ─────────────
    # The gate's own failure mode, named before it ran: an agent that writes
    # "no component warranted" nine times has SATISFIED it without being
    # changed by it. A gate that cannot tell those apart is decoration, so the
    # meter ships with the gate rather than after it.
    #   distinct_ratio — unique `why` texts over total. 1.0 = every beat got its
    #                    own reasoning; 0.11 on 9 beats = one sentence copied.
    #   quotes_beat    — does the `why` name a word from THAT beat's context?
    #                    Boilerplate cannot, without being about the beat.
    _vs = led.get("beat_verdicts") or led.get("component_verdicts") or []
    # GROUND TRUTH from the spans, computed before the meter so it can compare.
    _bcs = beat_cut_status(led.get("beats") or [], led.get("keep_spans") or [])
    _kept_actual = sum(1 for x in _bcs if x["kept"])
    led["cuts_actual"] = {"keep": _kept_actual, "cut": len(_bcs) - _kept_actual}
    if _vs:
        _whys = [str(v.get("why") or "").strip().lower() for v in _vs]
        _uniq = len(set(_whys))
        # Does the rationale name a word from ITS OWN beat? Boilerplate cannot,
        # without being about the beat.
        _btxt = {b["i"]: str(b.get("text") or "").lower()
                 for b in (led.get("beats") or [])}
        def _cites(v):
            words = [w for w in _btxt.get(v.get("beat"), "").split() if len(w) > 4]
            why = str(v.get("why") or "").lower()
            return any(w.strip(".,!?'\"") in why for w in words)
        _refs = sum(1 for v in _vs if _cites(v))
        led["verdict_quality"] = {
            "n": len(_vs),
            "distinct_whys": _uniq,
            "distinct_ratio": round(_uniq / max(len(_vs), 1), 2),
            "mentions_own_beat": _refs,
            "median_why_chars": sorted(len(w) for w in _whys)[len(_whys) // 2],
            "treatments": {t: sum(1 for v in _vs if v.get("treatment") == t)
                           for t in ("card", "text", "none")},
            # SELF-REPORT, kept for comparison only.
            "cuts_reported": {c: sum(1 for v in _vs if v.get("cut") == c)
                              for c in ("keep", "cut")},
            "cuts_actual": led.get("cuts_actual"),
            "sample": [{"b": v.get("beat"), "t": v.get("treatment"),
                        "c": v.get("cut"), "why": str(v.get("why"))[:150]}
                       for v in _vs[:8]],
        }
        # PERFUNCTORY IS A LEDGER EVENT, not a footnote. If it fires the gate is
        # being satisfied rather than working, which is a different problem and
        # must not read as a pass.
        if _uniq <= max(1, len(_vs) // 3) and len(_vs) >= 3:
            fail("component_verdicts_perfunctory",
                 f"{len(_vs)} verdicts, only {_uniq} distinct rationale(s) — the "
                 f"gate was cleared, not answered")

    # RECONCILIATION — the manifest is the instrument, so it has to be audited
    # in BOTH directions or it is unfalsifiable prose.
    #   under-declaring: drawing ops ran with nothing declared (below).
    #   over-declaring: a remotion placement claimed with no render command.
    # THE AUDIT MUST SEE BOTH RENDER PATHS. `remotion_renders` counts the string
    # in led["cmds"], which is the SHELL log — but render_components runs the
    # reel via subprocess INSIDE the tool, so it never appears there. Run F
    # declared 4 remotion placements, rendered them correctly in one reel, and
    # this check called it a false over-declaration. The manifest was right and
    # the auditor was blind to the path it was auditing.
    _renders_total = _mix["remotion_renders"] + int(led.get("reel_renders") or 0)
    _mix["reel_renders"] = int(led.get("reel_renders") or 0)
    _mix["renders_total"] = _renders_total
    if _mix["by_remotion"] and _renders_total == 0:
        fail("placement_declared_without_render",
             f"{_mix['by_remotion']} placement(s) declared method='remotion' but "
             f"ZERO renders ran on EITHER path (shell `remotion render` "
             f"{_mix['remotion_renders']}, reel {_mix['reel_renders']}) — the "
             f"manifest is claiming a component that was never rendered.")
    # THE INVERSE, which nothing checked before: a reel WAS rendered and nothing
    # was declared against it. That is paint bought and thrown away — ~72s and
    # a container's disk for components the manifest does not know exist — and
    # it is exactly as silent as the over-declaring half.
    if _mix["reel_renders"] and _mix["by_remotion"] == 0:
        fail("reel_rendered_without_declaration",
             f"{_mix['reel_renders']} reel render(s) ran but ZERO placements are "
             f"declared method='remotion' — components were painted and never "
             f"claimed, so the manifest under-reports what the edit contains.")

    if not (final or {}).get("duration_s") and not led["failures"]:
        fail("no_output_no_reason",
             f"run produced no video and logged NO failure — the ledger was "
             f"blind. iters={led['iters']}, shell_cmds={len(led.get('cmds') or [])}, "
             f"knowledge_reads={led.get('knowledge_reads')}")

    # ── CHECK 2 (RUNTIME): C1/C2 violated in the commands actually RUN ───────
    # The static check proves the constraints are IN the prompt. It proves
    # nothing about whether the agent obeyed them — same distinction as
    # cert-green vs deploy-green. This one reads the command log.
    #
    # Both failures are SILENT: a 60fps graphic on a 30fps cut plays at half
    # speed and ffmpeg exits 0; an unkeyed composite pastes a grey rectangle
    # and ffmpeg exits 0. Nothing downstream raises, so the ledger has to.
    import re as _re2
    # SCOPED TO RENDER COMMANDS. Unscoped, this scanned the whole command log
    # and fired on `npx remotion compositions | grep -i MGCraftProbe` — a
    # DISCOVERY command, which is exactly what C1 wants the agent to run. The
    # first run with all four inputs wired reported c1_violation while the only
    # actual render was the correct `render MGCraftProbe30`.
    # A check that cries wolf costs the same trust as one that never fires:
    # the next real C1 violation would be read as "that check is noisy".
    _render_cmds = " ".join(x for x in (led.get("cmds") or [])
                            if "remotion render" in x)
    _bare_probe = _re2.findall(r"MGCraftProbe(?!30)(?![A-Za-z0-9_])", _render_cmds)
    if _bare_probe:
        fail("c1_violation_60fps_probe",
             f"agent rendered bare MGCraftProbe {len(_bare_probe)}x — it is "
             f"60fps against a 30fps edit, so the graphic plays at HALF SPEED. "
             f"C1 requires MGCraftProbe30. Exit code was 0; this is silent.")
    _rendered_mg = _mix.get("remotion_renders", 0) > 0
    _keyed = ("colorkey" in _c)
    _composited = ("overlay=" in _c)
    if _rendered_mg and _composited and not _keyed:
        fail("c2_violation_unkeyed_composite",
             "a Remotion component was rendered and composited with NO colorkey "
             "step — the probe paints an OPAQUE 0x808080 field, so this pastes a "
             "GREY RECTANGLE over the footage. C2 requires keying mg.mov to "
             "mg_keyed.mov first. Exit code was 0; this is silent.")
    if _rendered_mg and not _composited:
        fail("mg_rendered_never_composited",
             "a Remotion component rendered but no overlay= composite ran — the "
             "graphic was paid for and never reached the output.")

    # THE UNDER-DECLARING HALF. This one MUST read the raw ops, not family_mix —
    # family_mix is now derived FROM the manifest, so checking it against the
    # manifest would be circular and could never fire. The op-count's surviving
    # job is exactly this: catching drawing that nobody declared.
    _drew = _c.count("drawtext") + _c.count("drawbox")
    if _drew and not _pl:
        fail("placements_undeclared",
             f"{_drew} drawtext/drawbox op(s) ran but ZERO placements were "
             f"declared — the manifest is the instrument now, so an undeclared "
             f"placement is an unmeasured one.")

    if use_knowledge and not led["knowledge_reads"]:
        # The knowledge arm that never opened a file is NOT an arm. Without this
        # the A/B could report "no effect" when the real finding is "the tool was
        # never called" — the two are indistinguishable in the output alone.
        fail("knowledge_never_read",
             "use_knowledge=True but the agent called read_knowledge zero times "
             "— this arm is not a knowledge arm and must not be compared as one")
    return {"ok": bool(final.get("exists")), "wall_s": round(time.time() - t0, 1),
            "download_s": dl_s, "transcript_s": transcript_s,
            "source_words": len(words), "final": final, "ledger": led,
            "output_key": key, "agent_last_message": final_text[:1200]}


@app.local_entrypoint()
def main(source: str = "ab-sources/talking-head-v1/625dfdc5-73s.mp4",
         brief: str = "Cut this into a punchy vertical short. Remove silence and "
                      "filler. Keep the meaning intact. Burn readable captions.",
         iters: int = MAX_ITERS,
         knowledge: bool = True,
         effort: str = DEFAULT_EFFORT,
         model: str = MODEL,
         route: bool = False):
    r = edit.remote(source, brief, iters, knowledge, effort, model, route)
    print("\n" + "=" * 66)
    print(f"  AGENTIC EDITOR — knowledge={'ON' if knowledge else 'OFF'}  "
          f"effort={r['ledger'].get('effort')}  model={r['ledger'].get('model')}")
    print("=" * 66)
    print(f"  source          : {source}")
    kr = r["ledger"].get("knowledge_reads", [])
    print(f"  knowledge reads : {len(kr)}  {kr}")
    # THE FOUR INPUTS, each with its own status. Reported here because "all four
    # are wired" was previously an impression — only the rules were ever
    # asserted, so three could be absent while the run was described as complete.
    print("  ── the four inputs ──")
    for _n, _i in (r["ledger"].get("inputs") or {}).items():
        _u = _i.get("used") or []
        _shown = (", ".join(str(x) for x in _u)[:60]) if _u else "—"
        print(f"    {_n:<20} {_i.get('status','?'):<18} {_shown}")
    _ss = r["ledger"].get("skill_searches") or []
    if _ss:
        print(f"    skill searches: {len(_ss)} -> "
              + ", ".join(f"{s['q']}({s['hits']})" for s in _ss[:8]))
    # THE VERDICTS, PRINTED. The substantiveness meter existed in the ledger and
    # nowhere else, so the one question the C8 gate was built to answer — "is it
    # being answered or just cleared" — was unreadable from a run. A meter you
    # cannot see is the same as no meter.
    _vq = r["ledger"].get("verdict_quality")
    if _vq:
        _nb = len(r["ledger"].get("beats") or [])
        print(f"  BEAT VERDICTS   : {_vq['n']} ruled of {_nb} beats, "
              f"{_vq['distinct_whys']} distinct (ratio {_vq['distinct_ratio']}), "
              f"{_vq['mentions_own_beat']} cite their own beat, "
              f"median {_vq['median_why_chars']} chars")
        _ca, _cr = _vq.get('cuts_actual'), _vq.get('cuts_reported')
        print(f"     treatments {_vq.get('treatments')}")
        print(f"     cuts ACTUAL (from build_cut spans) {_ca}   self-reported {_cr}"
              + ("   <- SELF-REPORT DISAGREES" if _ca and _cr
                 and _ca.get('cut') != _cr.get('cut') else ""))
        for _v in (_vq.get("sample") or []):
            print(f"     [{_v.get('b')}] {_v.get('t')}/{_v.get('c')}  {_v['why']}")
    # THE TWO QUESTIONS RUN F RAISED, answered in the report rather than inferred:
    # was nothing cut because turns ran out (harness) or because the agent chose
    # to keep everything (prompt)? And did the components crowd out the text?
    _cc = r["ledger"].get("cut_coverage")
    if _cc:
        print(f"  CUT DECISION    : kept {_cc['kept_s']}s of {_cc['source_s']}s "
              f"({_cc['coverage']}) across {_cc['spans']} span(s)"
              + ("   <- kept EVERYTHING" if (_cc.get('coverage') or 0) >= 0.995 else ""))
    _cv = r["ledger"].get("cut_verdict")
    if _cv:
        print(f"  CUT VERDICT     : {_cv['decision']}  {_cv['why'][:180]}")
    elif _cc and (_cc.get('coverage') or 0) >= 0.995:
        print("  CUT VERDICT     : (none — gate should have blocked)")
    _fm = r["ledger"].get("family_mix") or {}
    print(f"  TURN BUDGET     : used {r['ledger']['iters']} of {r['ledger'].get('max_iters','?')}"
          f"   renders: shell {_fm.get('remotion_renders',0)} + reel {_fm.get('reel_renders',0)}"
          f" = {_fm.get('renders_total',0)}")
    _gb = r["ledger"].get("skill_gate_blocks", 0)
    print(f"    C7 gate       : {_gb} render(s) blocked before first search"
          + ("  (gate did the work)" if _gb else "  (searched unprompted)"))
    print(f"  ok              : {r['ok']}")
    print(f"  WALL            : {r['wall_s']}s  "
          f"(download {r['download_s']}s, transcript {r['transcript_s']}s)")
    print(f"  self-review     : {r['ledger']['iters']} iteration(s)")
    t = r["ledger"]["tokens"]
    print(f"  TOKENS          : in {t['in']:,}  out {t['out']:,}  "
          f"cache_read {t['cache_read']:,}  cache_write {t['cache_write']:,}")
    # PER-MODEL RATES. Hardcoding Sonnet's numbers made the cost line a lie the
    # moment a cheaper-model arm ran — and the cost line IS the comparison that
    # arm exists to make. The $2/$10 Sonnet introductory rate EXPIRED
    # 2026-08-31; a cost compared against a pre-09-01 run is comparing two price
    # regimes, not two arms.
    _RATES = {   # in, out, cache_read, cache_write   ($ per 1M tokens)
        "claude-sonnet-5":  (3.0, 15.0, 0.30, 3.75),
        "claude-opus-5":    (5.0, 25.0, 0.50, 6.25),
        "claude-haiku-4-5": (1.0,  5.0, 0.10, 1.25),
    }
    _model = r["ledger"].get("model") or "claude-sonnet-5"
    _ri, _ro, _rr, _rw = _RATES.get(_model, _RATES["claude-sonnet-5"])
    if _model not in _RATES:
        print(f"  ⚠️  no rate table for {_model} — costing it at Sonnet rates, "
              f"which is a GUESS, not a measurement")
    def _cost_of(tt, rates):
        a, b, c, d = rates
        return (tt["in"] * a + tt["out"] * b + tt["cache_read"] * c
                + tt["cache_write"] * d) / 1e6
    _tbm = r["ledger"].get("tokens_by_model") or {}
    if len(_tbm) > 1:
        cost = sum(_cost_of(tt, _RATES.get(mm, _RATES["claude-sonnet-5"]))
                   for mm, tt in _tbm.items())
        _out_cost = sum(tt["out"] * _RATES.get(mm, _RATES["claude-sonnet-5"])[1]
                        for mm, tt in _tbm.items()) / 1e6
        print("  ROUTED          : " + "  ".join(
            f"{mm.replace('claude-','')} ${_cost_of(tt, _RATES.get(mm, _RATES['claude-sonnet-5'])):.4f}"
            f" ({tt['out']:,} out)" for mm, tt in _tbm.items()))
    else:
        cost = _cost_of(t, (_ri, _ro, _rr, _rw))
        _out_cost = t["out"] * _ro / 1e6
    print(f"  COST ({_model.replace('claude-','')})   : ${cost:.4f}")
    # THE TAIL. cache_write is 12.5x the read price, so a 7.7% token share is
    # ~half the input bill. The cached PREFIX is written once; everything else
    # is the growing message tail being re-written every turn. That is the lever.
    _cwc = t["cache_write"] * _rw / 1e6
    _crc = t["cache_read"] * _rr / 1e6
    print(f"    tail          : cache_write {t['cache_write']:,} tok = ${_cwc:.4f} "
          f"({100*_cwc/max(cost,1e-9):.0f}% of cost)   "
          f"cache_read {t['cache_read']:,} = ${_crc:.4f} "
          f"({100*_crc/max(cost,1e-9):.0f}%)")
    # THE TERM THIS ARM TARGETS. Output is 5x the input rate, so an output-token
    # share is the only part of the bill `effort` can move. Report it as a share
    # of cost, not of tokens — tokens are not what is being spent.
    print(f"    output share  : ${_out_cost:.4f} = "
          f"{100 * _out_cost / max(cost, 1e-9):.1f}% of cost   "
          f"({t['out']:,} out tokens over {r['ledger']['iters']} turns)")
    f = r["final"]
    if f.get("exists"):
        print(f"  output          : {f['duration_s']}s  {f['width']}x{f['height']}  "
              f"{f['vcodec']}  audio={f['has_audio']}  {f['size_mb']}MB")
        sc = f.get("speech_check")
        if isinstance(sc, dict):
            print(f"  SPEECH CHECK    : {sc['output_words']} words in output vs "
                  f"{sc['source_words']} in source (kept_ratio {sc['kept_ratio']})")
            if sc["sample_missing"]:
                print(f"    absent sample : {' '.join(sc['sample_missing'][:14])}")
        else:
            print(f"  SPEECH CHECK    : {sc}")
    print(f"  s3 key          : {r.get('output_key')}")
    mx = r["ledger"].get("family_mix") or {}
    if mx:
        print(f"\n  FAMILY MIX — from the PLACEMENT MANIFEST ({mx.get('declared')} "
              f"declared). Op-counting retired: a filter name cannot tell a "
              f"caption burn from an overlay text.")
        _dur = float((r.get("final") or {}).get("duration_s") or 0) or 1.0
        _n = {"text": mx["text"], "cut": mx.get("cut_spans", 0),
              "cutaway": mx["cutaways"], "card": mx["cards"],
              "sfx": mx["sfx"], "zoom": mx.get("emphasis", 0),
              "transition": mx.get("transitions", 0)}
        for _f, _ref in REFERENCE_PER_25S.items():
            _rate = round(_n.get(_f, 0) / _dur * 25.0, 2)
            _pct = f"{100*_rate/_ref:3.0f}%" if _ref else "  — "
            _bar = "#" * min(20, int(round((_rate/_ref)*10))) if _ref else ""
            print(f"    {_f:<10} {_rate:>6} /25s   ref {_ref:>5}   {_pct}  n={_n.get(_f,0):<3} {_bar}")
        print(f"    caption tracks: {mx['caption_tracks']}   emphasis: {mx['emphasis']}   sfx: {mx['sfx']}")
        print(f"    method: {mx['by_ffmpeg']} ffmpeg / {mx['by_remotion']} remotion")
        # BOTH PATHS. The audit was fixed to read shell+reel and this line was
        # not, so a reader still saw "renders: 0" printed next to "4 remotion".
        # Fixing the check and leaving the display is half a fix — the display
        # is what a person actually reads.
        print(f"    [ran] renders: {mx.get('renders_total', 0)} "
              f"(shell {mx.get('remotion_renders', 0)} + reel {mx.get('reel_renders', 0)})"
              f"  (product comp {mx.get('product_comp')}, PROBE comp {mx.get('probe_comp')})"
              f"  over {mx.get('shell_cmds')} shell commands")
    tns = r["ledger"].get("turns") or []
    if tns:
        from collections import Counter as _TC
        _tc = _TC(t for x in tns for t in (x["tools"] or ["<none>"]))
        print(f"\n  TURN BREAKDOWN — {len(tns)} turns, "
              f"{sum(x['out_tokens'] for x in tns):,} output tokens")
        for _n, _c in _tc.most_common():
            print(f"    {_n:<20} {_c}")
        _prod = sum(1 for x in tns if any(
            t in ("shell", "declare_placement") for t in (x["tools"] or [])))
        _read = sum(1 for x in tns if "read_knowledge" in (x["tools"] or []))
        _insp = sum(1 for x in tns if "inspect_output" in (x["tools"] or []))
        print(f"    -> productive(shell/declare) {_prod}  reading {_read}  "
              f"verifying {_insp}  other {len(tns)-_prod-_read-_insp}")
    cmds = r["ledger"].get("cmds") or []
    if cmds:
        print(f"\n  COMMAND LOG — {len(cmds)} shell commands")
        for _i, _c in enumerate(cmds, 1):
            _one = " ".join(str(_c).split())
            print(f"    {_i:>2}. {_one[:112]}")
    pls = r["ledger"].get("placements") or []
    print(f"\n  PLACEMENT MANIFEST — {len(pls)} declared (semantic, not op-counted)")
    from collections import Counter as _C
    for _t, _n in _C(p.get("type") for p in pls).most_common():
        print(f"    {_t:<14} {_n}")
    for _p in pls[:10]:
        print(f"      {_p.get('type'):<14} t={_p.get('t_start')}s "
              f"[{_p.get('method')}] {str(_p.get('content'))[:38]!r} "
              f"why={_p.get('why')}")
    fs = r["ledger"]["failures"]
    print(f"\n  FAILURE LEDGER  : {len(fs)} event(s)")
    for x in fs:
        print(f"    [{x['t']:>6}s] {x['kind']}: {x['detail'][:110]}")
    print(f"\n  agent said      : {r['agent_last_message'][:400]}")
