"""cert_prompt_content_diff.py — the "NOTHING REMOVED" proof for the prompt condensation.

Zac's ruling (2026-07-31): UNIFORM CAVEMAN. Keep every CONTENT word (noun, verb,
number, threshold, name, JUDGMENT). Delete every STRUCTURAL word (articles,
connectives, subordinate clauses, hedges, restatement, re-saying metaphor).

AUDIT IS MECHANICAL: any content word present in the ORIGINAL and absent in the
REWRITE is a violation. This script is that audit. Run it per section:
    original_text  vs  rewrite_text  ->  PASS (empty diff) or FAIL (lists losses).

It is deliberately CONSERVATIVE — it treats a word as CONTENT unless it is on the
explicit STRUCTURAL stoplist, so the burden is on the rewrite to prove nothing
of substance vanished. Numbers and Capitalized names can NEVER be stopped.

No Modal, no network, no edits to any prompt. Read-only cert harness.
"""
import re, sys, unicodedata

# Structural words — the ONLY words allowed to disappear in a caveman rewrite.
# Articles / connectives / subordinators / prepositions / copula+aux / bare
# pronouns / degree-hedges. Everything else is CONTENT and must survive.
STRUCTURAL = set("""
a an the
and or but so because when while whereas that which who whom whose as if then than though although
however therefore thus yet still also too either neither nor whether once until unless since
of to in on at for with from into onto by about over under up down off out through across between
among against toward towards within without per via
is are was were be been being am
do does did done doing
has have had having
will would can could may might shall should must ought
it its they them their theirs this these those what
you your yours we our ours us i me my mine he she his her hers
there here
just really very quite rather somewhat fairly pretty simply merely actually basically essentially
only even also more most much many few less least own same such other another each every any all both
not no
itself themselves himself herself myself yourself ourselves oneself
""".split())

# Light stemmer so caveman morphology (flash/flashes, land/lands/landing) is not
# a false violation. Conservative: only trims common inflections. NOTE: "'s" is
# checked before "s" so "cutaway's" -> "cutaway", not "cutaway'".
def _stem(w):
    for suf in ("'s", "ing", "edly", "ed", "es", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            return w[: -len(suf)]
    return w

_word_re = re.compile(r"[A-Za-z0-9À-ɏऀ-ॿ؀-ۿ][A-Za-z0-9À-ɏऀ-ॿ؀-ۿ'\-]*")

_CAMEL = re.compile(r"[a-z][A-Z]|[A-Z][a-z]+[A-Z]")  # ShutterFlash, ZoomThrough

def _is_name(tok):
    """Protected NAME = CamelCase component (ShutterFlash) or an all-caps
    emphasized keyword not itself structural (FIGHTS, USED). A plain
    sentence-initial capital (The, A) is NOT a name — it falls through to the
    lowercase structural check and is allowed to vanish."""
    if _CAMEL.search(tok):
        return True
    if tok.isupper() and len(tok) >= 2 and tok.lower() not in STRUCTURAL:
        return True
    return False

def content_multiset(text):
    """Map key -> {surface forms}. Structural words dropped; numbers, CamelCase
    names, and emphasized keywords are protected content (never stopped)."""
    out = {}
    for tok in _word_re.findall(text):
        low = tok.lower()
        if re.search(r"\d", tok):
            key = tok
        elif _is_name(tok):
            key = tok                      # preserve exact name/keyword surface
        elif low in STRUCTURAL:
            continue                       # structural word — allowed to vanish
        else:
            key = _stem(low)
        out.setdefault(key, set()).add(tok)
    return out

def audit(original, rewrite):
    o = content_multiset(original)
    r = content_multiset(rewrite)
    lost = sorted(k for k in o if k not in r)
    # numbers & names get a hard, separate check (exact surface, never stemmed)
    nums_o = set(re.findall(r"\d+(?:\.\d+)?", original))
    nums_r = set(re.findall(r"\d+(?:\.\d+)?", rewrite))
    # Names = CamelCase components + all-caps emphasized keywords only (not plain
    # sentence-initial capitals, which _is_name deliberately excludes).
    names_o = {t for t in _word_re.findall(original) if _is_name(t)}
    names_r = {t for t in _word_re.findall(rewrite) if _is_name(t)}
    return {
        "lost_content_words": lost,
        "lost_numbers": sorted(nums_o - nums_r),
        "lost_names": sorted(names_o - names_r),
        "n_content_original": len(o),
        "n_content_rewrite": len(r),
        "tok_before": round(len(original) / 4),
        "tok_after": round(len(rewrite) / 4),
    }

def report(label, original, rewrite):
    a = audit(original, rewrite)
    ratio = a["tok_before"] / max(1, a["tok_after"])
    ok = not (a["lost_content_words"] or a["lost_numbers"] or a["lost_names"])
    print(f"\n=== {label} ===")
    print(f"  tokens {a['tok_before']} -> {a['tok_after']}  (ratio {ratio:.2f}x)")
    print(f"  content words {a['n_content_original']} -> {a['n_content_rewrite']}")
    print(f"  {'PASS — nothing removed' if ok else 'FAIL — content lost:'}")
    if a["lost_content_words"]:
        print(f"    lost words:   {a['lost_content_words']}")
    if a["lost_numbers"]:
        print(f"    lost numbers: {a['lost_numbers']}")
    if a["lost_names"]:
        print(f"    lost names:   {a['lost_names']}")
    return ok


# ─────────────────────────────────────────────────────────────────────────────
# DO-NOT-COLLAPSE invariants (Zac 2026-07-31). A carve-out can be lost WITHOUT
# dropping a content word — a reword that flattens "the hook window may carry TWO
# events" into "one event per window" keeps every content word yet destroys the
# exception. Each invariant is a set of tokens that MUST co-occur (case-insensitive
# substring) in the section's rewrite; if any token is missing the exception was
# collapsed → FAIL. This is the semantic floor the content-diff can't see.
DO_NOT_COLLAPSE = [
    # id, section, all_of (every token must be present), what it protects
    ("hook-two-events", "PREAMBLE", ["hook", "two", "overlay"],
     "hook window is the ONE window allowed two events (zoom + one opening overlay)"),
    ("composed-event", "PREAMBLE", ["composed", "transition", "zoom"],
     "boundary transition + adjacent peak zoom = ONE composed event, not two"),
    ("breather-zero", "PREAMBLE", ["breather", "zero"],
     "breather windows get ZERO events by design (silence is the treatment)"),
    ("payoff-callback-gap", "YOUR CUT PASS", ["callback", "1.5"],
     "payoff zoom is last EXCEPT a deliberate callback separated by >=1.5s"),
    ("captions-step-aside", "CAPTIONS", ["step aside", "graphic"],
     "captions run continuously EXCEPT they step aside for a takeover graphic"),
    ("payoff-commit-even-viral", "EMPHASIS MOMENTS + ZOOM", ["payoff", "even", "viral", "commit", "dwell"],
     "payoff commits by DWELL on the landed peak (not slow arrival) — even a viral payoff commits"),
    ("broll-mode-gate-order", "B-ROLL", ["extend", "literal"],
     "extend-test decides WHETHER to emit; mode(1) decides HOW — sequential gates"),
    ("thumbnail-before-after", "THUMBNAIL", ["after", "before"],
     "best thumbnail frame is usually AFTER the line, sometimes BEFORE (reveals)"),
]

def check_invariants(section, rewrite):
    """Return list of collapsed invariants (violations) for a section's rewrite."""
    low = rewrite.lower()
    out = []
    for iid, sec, toks, desc in DO_NOT_COLLAPSE:
        if sec != section:
            continue
        missing = [t for t in toks if t.lower() not in low]
        if missing:
            out.append((iid, missing, desc))
    return out

def cert_section(section, original, rewrite):
    """Full per-section gate: content-word diff PASS *and* no collapsed invariant."""
    a = audit(original, rewrite)
    lost = a["lost_content_words"] or a["lost_numbers"] or a["lost_names"]
    collapsed = check_invariants(section, rewrite)
    ok = not lost and not collapsed
    return ok, a, collapsed


if __name__ == "__main__":
    # REAL passage from the main prompt (handler.py:6014, B-ROLL cutaway treatment).
    ORIGINAL = (
        "A cutaway carries its own entry and exit treatment on the clip itself. "
        "Emit entry_transition / exit_transition (LightLeak or ShutterFlash, or omit "
        "for the bare cut) — the light punctuation: the warm bloom or the flash, and "
        "the bare cut carries most of them. The beat under the edge AND the vibe select: "
        "a reveal arriving warm → LightLeak; a stat snapping in on a punchy beat → "
        "ShutterFlash (which FIGHTS the calm register — a corporate stat cutaway takes "
        "LightLeak or the bare cut, not the flash). A cutaway's treatment fits inside "
        "its stay — a short cutaway takes the quick treatment or the bare cut."
    )
    # FAITHFUL uniform-caveman — every content word + name kept, structure stripped.
    CAVEMAN_GOOD = (
        "Cutaway carries entry exit treatment on clip. Emit entry_transition / "
        "exit_transition: LightLeak or ShutterFlash, or omit for bare cut — light "
        "punctuation: warm bloom or flash; bare cut carries most. Beat under edge AND "
        "vibe select: reveal arriving warm → LightLeak; stat snapping punchy beat → "
        "ShutterFlash (FIGHTS calm register — corporate stat cutaway takes LightLeak "
        "or bare cut, not flash). Cutaway treatment fits inside stay — short cutaway "
        "takes quick treatment or bare cut."
    )
    # OVER-compressed — drops the judgment "FIGHTS calm register" + name ShutterFlash
    # once + the "corporate" carve-out. The tool must CATCH this.
    CAVEMAN_LOSSY = (
        "Cutaway carries entry exit treatment. Emit entry_transition / exit_transition: "
        "LightLeak, or omit for bare cut. Reveal warm → LightLeak; stat punchy beat → "
        "flash. Short cutaway takes quick treatment or bare cut."
    )
    ok1 = report("DEMO 1  faithful caveman (should PASS)", ORIGINAL, CAVEMAN_GOOD)
    ok2 = report("DEMO 2  over-compressed (should FAIL)", ORIGINAL, CAVEMAN_LOSSY)
    print(f"\nTOOL SELF-CHECK: demo1 PASS={ok1} (want True), demo2 PASS={ok2} (want False) "
          f"-> {'OK' if (ok1 and not ok2) else 'TOOL BROKEN'}")
