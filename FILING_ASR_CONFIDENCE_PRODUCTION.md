# handler.py: confidence is kept, laundered, and never read

Filed by BUILDER-1 (lane-agentic) 2026-09-12. **Production, not a fixture.**

## Correcting my own commit first

`13067f2` says *"handler.py's ASR ingest drops the same two fields. Its 56
`confidence` hits are all FACE DETECTION."*

**That is wrong.** I grepped for `confidence`, saw face-detection hits at
`handler.py:4428`, and concluded from a partial search. `_parse_deepgram_response`
at **handler.py:5778** keeps BOTH fields, and handler already carries a
script-aware language-confusion detector (`_looks_confused`, 6859) that probes
for transliterated Arabic. It is more sophisticated than the agentic lane's.

The wrong sentence stays in that commit rather than being rewritten out — it is
the evidence that inferring an absence from a partial search is how this keeps
happening. What follows was verified line by line.

## The three real defects

**1. `or 1.0` launders the field — handler.py:5783**

```python
"confidence": float(getattr(w, "confidence", 1.0) or 1.0),
```

| raw | stored |
|---|---|
| `None` (absent) | **1.0 — certain** |
| `0.0` (certainly wrong) | **1.0 — certain** |
| 0.42 | 0.42 |

This is the documented law — *`or 0` on a value that might not exist is a
prohibition wherever a number reaches a report* — and it is worse than the `or 0`
cases already on the record, because it converts BOTH "the instrument did not
answer" AND "the instrument said certainly wrong" into "certain", on the one
field that could refuse a caption nobody said.

**2. Confidence is read ZERO times after ingest.** `grep -c 'confidence"]'`
returns 0. It is parsed, stored, carried through the pipeline and never
consulted. A producer with no consumer, in the mechanism that would have caught
this.

**3. `_looks_confused` cannot fire on this class.** Its first line is
`if (transcript.get("detected_language") or "").strip(): return False` —
Deepgram placed a language, so trust it. On round 65's car_short Deepgram placed
`pt` with total assurance over three words of engine noise. The detector is
built for TRANSLITERATION (romanized Arabic that places as nothing); it is not
built for noise that got confidently mislabelled, and correctly returns False.

## What the agentic lane shipped, for reference

Five clips re-transcribed through the same nova-3 multi call:

| clip | words | language | median confidence |
|---|---:|---|---:|
| talking_head | 85 | en | 1.000 |
| car_mid | 23 | en | 0.824 |
| **car_short** | **3** | **pt** | **0.418** ← nothing was said |

Bar at 0.60, placed inside the gap rather than fitted to a point. n=1 on the
failure side, stated.

**PER CLIP, NEVER PER WORD.** Dropping low-confidence words produces a patchy
caption, which is a defect in this product. car_mid proves it: `'inch' 0.198`
and `'null' 0.601` sit beside `'unemployed' 0.997`, so a per-word floor cuts
three words out of a real sentence and the viewer blames the speaker.

## The patch for #1, which is one line and safe on its own

```python
# was: "confidence": float(getattr(w, "confidence", 1.0) or 1.0),
_c = getattr(w, "confidence", None)
"confidence": (float(_c) if isinstance(_c, (int, float)) else None),
```

`None` means ABSENT. Every consumer must then decide rather than inherit a
fabricated 1.0 — and there are currently no consumers, so nothing breaks.

Items 2 and 3 are a caption gate, which is a real change to another lane's file
and is not mine to make unilaterally. Routed rather than taken. If nobody picks
it up I will take it on Zac's standing instruction, and say so before I do.
