#!/usr/bin/env python3
"""How many users ask for each capability BY NAME, from the real request corpus.

TWO COLUMNS MAKE THE ROADMAP. What Zac's ten examples DO (supply: what good
editing looks like) against what users ASK FOR (demand). A family in 9 of 10
examples that users also request by name is the first thing built; one in 4 of
10 that nobody asks for waits.

COUNTED ACROSS USERS, NOT OCCURRENCES — the same rule the family discovery
used. One user asking for zooms forty times is one user's habit; forty users
asking once is demand. Counting requests would rank the habit above the demand,
which is what the per-25s rates did to the reference corpus.

WORD BOUNDARIES, AND THE MATCHES ARE PRINTED. My last keyword filter reported
29 audible families in a corpus read WITHOUT AUDIO, because "Recording"
contains "ding" and \\bbeat\\b is in every editorial sentence. A demand number
nobody can audit is the same instrument failure one level up, so every family
prints its sample matches and its distinct-user count beside the request count.

MULTILINGUAL ON PURPOSE. The corpus is not English-only — "Sem zoom, mantenha a
camera parada" is a negative zoom constraint in Portuguese. A pattern that only
matches English under-counts demand and would rank a family below its real
position.
"""
import collections
import json
import re
import sys

NORM = lambda s: re.sub(r"\s+", " ", (s or "").strip().lower())

# name -> (pattern, note). Patterns are deliberately CONSERVATIVE: they match a
# user naming the thing, not merely touching its subject area.
PATTERNS = {
 "Platform outro/end card": (
   r"\b(end ?card|endcard|outro|end screen|call.?to.?action card|cta card|"
   r"follow (?:me|us)|subscribe (?:card|screen)|final card|último card|"
   r"tarjeta final|pantalla final)\b", "an explicit closing card"),
 "Cursor/UI callout highlight": (
   r"\b(callout|call.?out|highlight (?:the )?(?:cursor|button|click)|"
   r"cursor|arrow point|point(?:ing)? (?:arrow|at the)|circle (?:the|it)|"
   r"annotat\w+|resalt\w+|seta|flecha)\b", "pointing at the screen"),
 "Automated progress/loading indicator": (
   r"\b(progress ?bar|loading (?:bar|screen|indicator)|percentage bar|"
   r"barra de progresso|barra de carga)\b", "a progress/loading graphic"),
 "Escalating counter/stat ticking animation": (
   r"\b(count(?:ing)?.?up|counter|ticking|tick up|numbers? (?:count|climb|rise)|"
   r"animated (?:number|stat)|contador|contagem)\b", "a number that ticks"),
 "Split-screen comparison of two contents": (
   r"\b(split.?screen|side.?by.?side|before.?(?:and.?)?after|comparison|compare|"
   r"tela dividida|pantalla dividida|antes y despu|antes e depois)\b",
   "two things shown together"),
 "Typed search/URL graphic": (
   r"\b(search bar|type ?(?:out|in) the (?:name|handle|url)|url graphic|"
   r"barra de (?:busca|pesquisa))\b", "a typed search/URL graphic"),
 "Simple stat/emoji graphic overlay": (
   r"\b(emoji|emojis|sticker|stickers|reaction icon)\b", "emoji/sticker overlay"),
 "Step-by-step caption narration over demo": (
   r"\b(step.?by.?step|steps?\b.*\b(?:caption|text|label)|numbered steps|"
   r"passo a passo|paso a paso)\b", "stepped narration"),
 "Floating labeled UI/graphic elements": (
   r"\b(floating (?:icon|element|label|graphic)|pill|chip|badge)\b",
   "floating labelled elements"),
 "Floating people/location graphic": (
   r"\b(map pin|pin drop|location (?:pin|graphic)|profile card|avatar)\b",
   "people/location graphics"),
 "Full-screen title/thesis card": (
   r"\b(title card|full.?screen text|text card|thesis|chapter (?:card|marker)|"
   r"section (?:card|title)|cartão de título|tarjeta de título)\b",
   "a full-frame title card"),
 "Dominant kinetic title text synced to speech": (
   r"\b(kinetic (?:text|typo\w*)|big text|large text|bold text|word.?by.?word|"
   r"text that (?:pops|slams)|animated (?:text|title)|texto animado|"
   r"texto grande|typography)\b", "frame-dominant animated type"),
 "Decorative per-word caption styling": (
   r"\b(caption style|styled caption|caption font|font for the caption|"
   r"karaoke caption|estilo de legenda|subtítulos con estilo)\b",
   "styled captions"),
 "Colored keyword highlight within captions": (
   r"\b(highlight(?:ed)? (?:word|keyword|text)|colou?r(?:ed)? (?:word|keyword)|"
   r"keyword colou?r|word highlight|palabra destacada|palavra destacada)\b",
   "coloured keyword in captions"),
 "Word-by-word caption build": (
   r"\b(word.?by.?word|one word at a time|caption build|palavra por palavra|"
   r"palabra por palabra)\b", "word-by-word caption build"),
 "3D perspective UI/gallery browse graphic": (
   r"\b(3d|three.?dimensional|perspective (?:view|graphic)|parallax)\b",
   "3D/perspective graphics"),
 "3D icon animation": (r"\b(3d icon|animated icon|icon animation)\b",
   "animated 3D icons"),
 "Polaroid-style graphic reveal": (
   r"\b(polaroid|photo frame|picture frame|instant photo|moldura)\b",
   "photo-frame reveal"),
 "Logo idle branding animation": (
   r"\b(logo|branding|brand mark|watermark|marca d'água|logotipo)\b",
   "logo/branding animation"),
 "Split-screen picture-in-picture": (
   r"\b(picture.?in.?picture|\bpip\b|corner (?:cam|video)|inset video|"
   r"webcam overlay)\b", "PIP composition"),
 # ── the audio families, for completeness of the demand read ──
 "Whoosh/Pop Accent SFX": (
   r"\b(whoosh|swoosh|sound ?effects?|sfx|riser|transition sound|"
   r"efeito sonoro|efectos de sonido)\b", "accent sound effects"),
 "Click/Interaction SFX": (
   r"\b(click sound|typing sound|keyboard sound|ui sound|interaction sound)\b",
   "interaction sound effects"),
}


def main():
    rows = json.load(open(sys.argv[1] if len(sys.argv) > 1
                          else "/tmp/video_jobs_asks.json"))
    reqs = []
    for r in rows:
        v = (r.get("vibe_input") or "").strip()
        if v:
            reqs.append((NORM(v), r.get("user_id")))
    distinct = {t for t, _ in reqs}
    users = {u for _, u in reqs}
    print(f"  CORPUS  {len(reqs):,} requests · {len(distinct):,} distinct texts "
          f"· {len(users):,} distinct users")
    print(f"  (Zac cited 5,943 distinct; this reads {len(distinct):,} after "
          f"whitespace+case normalisation of vibe_input, {len({t for t,_ in reqs})} "
          f"unnormalised would be higher — the denominator used below is "
          f"DISTINCT USERS, which is the figure that ranks demand)\n")
    out = {}
    for fam, (pat, note) in PATTERNS.items():
        rx = re.compile(pat, re.I)
        hits = [(t, u) for t, u in reqs if rx.search(t)]
        hu = {u for _, u in hits}
        ht = {t for t, _ in hits}
        out[fam] = {"requests": len(hits), "distinct_texts": len(ht),
                    "users": len(hu),
                    "pct_users": round(100.0 * len(hu) / len(users), 1),
                    "note": note,
                    "samples": [t[:110] for t in sorted(ht, key=len)[:3]]}
    json.dump(out, open("demand_by_family.json", "w"), ensure_ascii=False, indent=1)
    print(f"  {'users':>6} {'%':>6} {'reqs':>6}  family")
    for fam, d in sorted(out.items(), key=lambda x: -x[1]["users"]):
        print(f"  {d['users']:>6} {d['pct_users']:>5.1f}% {d['requests']:>6}  {fam}")
    print("\n  SAMPLE MATCHES (auditable — a demand number nobody can check is "
          "the same instrument failure one level up):")
    for fam, d in sorted(out.items(), key=lambda x: -x[1]["users"])[:8]:
        print(f"\n   {fam}  [{d['users']} users]")
        for s in d["samples"]:
            print(f"      {s!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
