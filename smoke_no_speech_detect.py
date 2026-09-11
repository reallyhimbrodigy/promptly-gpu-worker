#!/usr/bin/env python3
"""RED PROOF: "[visual] motion 0.72" is not speech.

The first version of the speech-vocabulary flag tested `not said`. A
visual-route beat's SAID is not empty — it is a synthetic marker — so the
check fired on NOTHING and printed a clean zero on the fixture it was built
for. A guard that only checks emptiness is blind to the case it exists to
catch, and the blindness renders identically to a pass.
"""
import sys

import read_whys as R

RED = ["", "   ", "[visual] motion 0.72", "[visual] motion 0.40 · shot change",
       "[visual]"]
GREEN = ["being a content creator is not easy", "ой",
         "[visual] he says the app works", "it took five minutes to edit"]

bad = 0
for t in RED:
    if not R.no_speech(t):
        print(f"  *** a speech-less beat READ AS SPEECH: {t!r}")
        bad += 1
for t in GREEN:
    if R.no_speech(t):
        print(f"  *** real speech READ AS SILENT: {t!r}")
        bad += 1
print(f"smoke_no_speech_detect: {len(RED)} red + {len(GREEN)} green, "
      f"{bad} wrong")
sys.exit(1 if bad else 0)
