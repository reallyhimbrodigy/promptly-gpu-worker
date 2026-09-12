#!/usr/bin/env python3
"""A caption nobody said is worse than no caption, and it shipped.

ROUND 65, car_short: ten seconds of a car in a flooded intersection — engine
noise, a crowd, no speech. Deepgram returned three Portuguese words and the
pipeline burned one on screen as a Cyrillic caption, "ОЙ", the only text in the
whole output. The evidence to refuse it arrived in the SAME ASR response and was
thrown away one line later: the ingest kept `word`, `start` and `end` and
discarded `confidence` and `language`.

MEASURED, five round-65 clips re-transcribed through the same nova-3 multi call:

    clip              words  language   min    p10    MEDIAN
    talking_head         85  en 85     0.723  0.981   1.000    real speech
    car_mid              23  en 23     0.198  0.532   0.824    real speech, noisy
    car_short             3  pt  3     0.142  0.142   0.418    NOTHING WAS SAID
    motion                0  —          —      —       —       no words at all
    screen_recording      0  —          —      —       —       no words at all

PER CLIP, NEVER PER WORD, AND THAT IS THE DESIGN. The obvious fix — drop words
below a floor — is forbidden here: patchy captions are a DEFECT in this product
and the only permitted answers are full captions, no captions with the reason
said, or reject. car_mid proves it: its worst words are 'inch' 0.198 and 'null'
0.601 beside 'unemployed' 0.997, so a per-word floor would cut three words out
of a real sentence and the viewer would blame the speaker.

The bar sits at 0.60, inside the gap from 0.418 to 0.824 — placed between two
populations rather than fitted to a point. n=1 on the failure side, stated
rather than hidden: a no-speech clip that transcribes CONFIDENTLY would refute
it.

SIX PROPERTIES:
  1. the ingest KEEPS confidence and language — the fields cannot be discarded
     again without this failing;
  2. real speech is captioned (both real populations, at their real medians);
  3. the hallucination is REFUSED at its real median;
  4. no confidence at all is ABSENT, never a pass;
  5. no words is its own state, not a refusal;
  6. the refusal is per CLIP — no input ever yields a partial cue list.
"""
import ast
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import modal_stub  # noqa: E402
modal_stub.install()
import agentic_editor_app as A  # noqa: E402

fail = 0
src = open(os.path.join(HERE, "agentic_editor_app.py"), encoding="utf-8").read()


def words(confs, lang="en"):
    return [{"w": "x", "s": i * 0.3, "e": i * 0.3 + 0.2, "conf": c, "lang": lang}
            for i, c in enumerate(confs)]


# 1. THE INGEST KEEPS THEM. Asked of the AST: the word dict built from the ASR
#    response must read `confidence` and `language`, or the fields are gone
#    again and every property below is testing a function nothing feeds.
tree = ast.parse(src)
reads = {n.args[0].value for n in ast.walk(tree)
         if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "get"
         and n.args and isinstance(n.args[0], ast.Constant)
         and isinstance(n.args[0].value, str)}
for f in ("confidence", "language"):
    if f not in reads:
        print(f"  *** the ASR ingest never reads {f!r} — it is discarded at "
              f"the boundary again, and the caption decision has nothing to "
              f"decide on")
        fail += 1

# 2. REAL SPEECH IS CAPTIONED, at the medians actually measured.
for name, confs in (("talking_head", [1.0] * 40 + [0.723, 0.981]),
                    ("car_mid", [0.824] * 12 + [0.198, 0.532, 0.997])):
    st, why = A.caption_confidence_state(words(confs))
    if st != "MEASURED":
        print(f"  *** {name} (real speech) was {st}: {why} — refusing a real "
              f"transcript costs every caption in the run")
        fail += 1

# 3. THE HALLUCINATION IS REFUSED, at its real median and language.
st, why = A.caption_confidence_state(words([0.142, 0.418, 0.548], lang="pt"))
if st != "REFUSED":
    print(f"  *** car_short's transcript was {st}, not REFUSED: {why}")
    fail += 1
elif "0.418" not in why and "confidence" not in why:
    print(f"  *** the refusal does not say why: {why}")
    fail += 1

# 4. NO CONFIDENCE IS ABSENT, NOT A PASS.
st, _ = A.caption_confidence_state(
    [{"w": "x", "s": 0, "e": 1}, {"w": "y", "s": 1, "e": 2}])
if st != "ABSENT":
    print(f"  *** a transcript with no confidence field read as {st} — the "
          f"instrument did not answer and that must not become 'good'")
    fail += 1

# 5. NO WORDS IS ITS OWN STATE.
st, _ = A.caption_confidence_state([])
if st != "NO_SPEECH":
    print(f"  *** an empty transcript read as {st}, which conflates 'nobody "
          f"spoke' with 'what was said is untrustworthy'")
    fail += 1

# 6. ALL OR NOTHING. Sweep the floor: no input may ever produce a state that
#    would let SOME cues through — the patchy-caption defect.
seen = set()
for lo in range(0, 11):
    st, _ = A.caption_confidence_state(words([lo / 10.0] * 9))
    seen.add(st)
if not seen <= {"MEASURED", "REFUSED", "ABSENT", "NO_SPEECH"}:
    print(f"  *** unexpected state(s) {seen - {'MEASURED','REFUSED','ABSENT','NO_SPEECH'}}")
    fail += 1
if "MEASURED" not in seen or "REFUSED" not in seen:
    print(f"  *** the floor never separates across 0.0-1.0: {seen} — a bar "
          f"that admits or refuses everything is not a bar")
    fail += 1

# AND THE CALLER MUST HONOUR IT — "IS IT CALLED" IS NOT "IS IT CHOOSING".
# The first version of this leg asserted only that the function is CALLED, and
# a mutation replacing the guard with `if True:` — every clip captioned,
# whatever the state — sailed straight past it. A presence check cannot see
# control flow; this repo has written that down five times and it caught this
# smoke on its own RED proof.
calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
         and getattr(n.func, "id", "") == "caption_confidence_state"]
if not calls:
    print("  *** caption_confidence_state is never called — the decision "
          "exists and the caption path does not consult it")
    fail += 1

# The cue loop must sit inside a branch that TESTS the state against MEASURED.
_guarded = False
for _n in ast.walk(tree):
    if not isinstance(_n, ast.If):
        continue
    _names = {getattr(x, "id", "") for x in ast.walk(_n.test)
              if isinstance(x, ast.Name)}
    _consts = {x.value for x in ast.walk(_n.test)
               if isinstance(x, ast.Constant)}
    if "MEASURED" not in _consts:
        continue
    if not any(n2.endswith("cap_state") or n2.endswith("caption_state")
               for n2 in _names):
        continue
    # does this branch actually build the cues?
    _body = ast.dump(ast.Module(body=_n.body, type_ignores=[]))
    if "words_per_cue" in _body and "cues" in _body:
        _guarded = True
        break
if not _guarded:
    print("  *** the cue loop is not guarded by a test of the caption state "
          "against MEASURED — the state is computed and the captions are "
          "built regardless, which is the defect with a diagnosis attached")
    fail += 1

print(f"smoke_caption_confidence: floor={A._CAPTION_CONF_FLOOR}, "
      f"{len(calls)} call site(s), cue loop guarded={_guarded}, "
      f"{fail} wrong")
sys.exit(1 if fail else 0)
