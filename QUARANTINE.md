# QUARANTINE — named hazards, owned elsewhere, not being worked

A red that will not be fixed today must be **fixed, quarantined with an owner
and a date, or deleted**. This is the register for the middle case. A hazard in
here is NOT being investigated by this lane; it is written down so it cannot
become furniture, and so the next person who trips on it finds the diagnosis
instead of re-deriving it.

Every entry names: the OWNER lane, the DATE, the SIGNATURE to search for, and
what is and is not known. An entry with no signature is a rumour, not a hazard.

---

## Q1 · handler.py clamps an unmeasurable loudness into a plausible number

    OWNER      worker lane (TRUTH). NOT this lane, NOT Builder 1's.
    RAISED     2026-09-21, by Builder 1 reading measure_source_loudness while
               checking whether his lane restated ChatCut's -70.0 anywhere.
    STATUS     NAMED HAZARD. No rate. Not a defect until someone has one.

**What it does.** `measure_source_loudness` parses ffmpeg `astats`. Where ffmpeg
emits `-inf` for a digitally silent channel it CLAMPS: peak to **-60.0**, noise
floor to **-70.0**. The comment beside it describes the clamp approvingly.

**Why it is the same class as the ChatCut -70.0 I published wrongly.** An
absent measurement becomes a present, well-typed number, and from then on
nothing downstream can tell it from a reading. This is the PRODUCER-SIDE
LAUNDERING case specifically: the fix can only be at the producer, because by
the time a consumer sees it there is nothing left to tell.

**Why it is not cosmetic.** Three render parameters branch on those values:

    _nr = 6 if _src_nf > -40 else (10 if _src_nf > -50 else 14)   denoise strength
    _snr = _rms - _nf                                             -> 10.0 dB for a
                                                                     clip with NO
                                                                     AUDIO AT ALL
    (compressor threshold and makeup gain read the same pair)

A clip with no audio reports 10 dB of speech above its noise floor, and the
render is tuned against that.

**THE DENOMINATOR IS NOT IN THE DATABASE. MEASURED: 0 of 567.** Builder 1
queried seven days of jobs — 567 — for `peak_db`, `noise_floor`, `snr_db` and
`input_quality` across `analysis_data`, `result` and `partial_state`. Zero carry
any of them. His first attempt scanned the whole table and timed out at 363s, so
this is a bounded window asking named columns, not a shrug.

**So the larger finding is the ABSENCE, and it is the reason this cannot be
priced.** A measurement that sets denoise strength, compressor thresholds and
makeup gain on every render is never persisted. No render can be audited against
what it was tuned on. This question is simply the first one that needed it.

**SIGNATURE — what to grep in production logs, which is the only surface
carrying it:**

    [loudness] peak=-60.0dB rms=-60.0dB noise_floor=-70.0dB     the clamp, exactly
    snr_db == 10.0                                              its downstream tell

**What would move this out of quarantine:** a production log read giving the
rate. That is TRUTH's remit and neither Builder 1 nor I will run it unasked.
Neither of us edits handler.py.
