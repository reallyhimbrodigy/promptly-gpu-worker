#!/usr/bin/env python3
"""THE WATCHED ARTEFACT — select the moments, grab the frames, tile, GATE, ship.

Input : /tmp/watched/*.json           (one per video, from run_watch_moments.py)
Output: watched/SHEET.md              the glanceable lines, one per moment
        watched/tiles/SHEET_<n>.png   the frames, numbered to match the lines
        watched/moments.json          the full record, verdicts included

THE GATE IS THE POINT. A timestamp from a reader that watched a video can be
half a second out, and half a second is a different shot. So every tile is put
back in front of a reader with its own line and asked: does this frame show
what this line says? Only `yes` ships. `no`, `unsure`, a missing verdict and a
FAILED verify pass all mean NOT SHOWN — the three-state rule, applied to a
picture: MEASURED-yes ships, ABSENT and FAILED do not.

Without that, the artefact's failure mode is silent and expensive: a confident
caption under the wrong frame teaches the opposite of what it says, on every
turn, from inside the cached prefix.
"""
import argparse
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
IN = os.environ.get("WATCH_OUT", "/tmp/watched")
EX = os.path.expanduser(os.environ.get("WATCH_EX", "~/Desktop/EXAMPLES"))
OUT = os.path.join(HERE, "watched")

# Tile geometry. Anthropic bills an image at w*h/750 tokens and downscales
# anything whose long edge exceeds 1568, so a sheet that overshoots pays for
# pixels it then loses. Both numbers are printed by this script; they are not
# to be estimated.
TILE_W, TILE_H, HEAD_H = 240, 427, 22
COLS, ROWS = 6, 3
# ── STRIPS ──────────────────────────────────────────────────────────────────
# A cut is a CHANGE and a single settled frame shows its aftermath: where it
# ended up, not what it did. A sound lands BETWEEN two pictures and what matters
# is which two. So a moment carrying a span becomes a ROW of frames through the
# change, with each frame's time under it, and the row is one entry in the
# sheet the gate asks about.
#
# FIVE FRAMES, evenly across the span. Fewer than four cannot show a middle;
# more than six at this width is a row of thumbnails nobody can read.
STRIP_N = 5
STRIP_W, STRIP_H = 232, 412
STRIP_ROWS = 3                       # strips per sheet
BG = (24, 24, 27)
INK = (240, 240, 245)


def ffmpeg_frame(src, t, dst):
    """One frame at t. Returns True only if a non-empty file appeared."""
    r = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y",
                        "-ss", "%.3f" % t, "-i", src, "-frames:v", "1",
                        "-q:v", "2", dst], capture_output=True, text=True)
    ok = r.returncode == 0 and os.path.exists(dst) and os.path.getsize(dst) > 0
    if not ok:
        print("    frame FAILED %s @ %.2f: %s"
              % (os.path.basename(src), t, (r.stderr or "")[:160]))
    return ok


def strip_times(m):
    """The times a strip samples, or None. STATED, not inferred at draw time.

    The settled frame is forced into the set so the strip always contains the
    frame the line was written about — a strip whose five samples all miss the
    moment is a picture of the seconds around a decision with the decision
    missing.
    """
    a, b = m.get("t_from_s"), m.get("t_to_s")
    if a is None or b is None or b <= a:
        return None
    ts = [a + (b - a) * i / (STRIP_N - 1.0) for i in range(STRIP_N)]
    t = m.get("t_settled_s")
    if t is not None and a <= t <= b:
        # replace whichever sample is nearest, so the count stays STRIP_N
        j = min(range(STRIP_N), key=lambda k: abs(ts[k] - t))
        ts[j] = float(t)
    return [round(x, 2) for x in sorted(ts)]


def tile_strip(rows, path):
    """One sheet of strips: each row is a moment, frames left to right.

    The row header carries the moment number, the span and — when the moment
    names one — WHEN THE SOUND LANDS, as a caret under the frame it falls
    between. An editor reading this needs the hit's position in the sequence,
    not only its timestamp in a line of text.
    """
    from PIL import Image, ImageDraw, ImageFont
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", 14)
        small = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", 12)
    except Exception:                                             # noqa: BLE001
        font = small = ImageFont.load_default()
    W = STRIP_N * STRIP_W
    RH = STRIP_H + HEAD_H + 16
    sheet = Image.new("RGB", (W, RH * len(rows)), BG)
    d = ImageDraw.Draw(sheet)
    for r, (m, frames, times) in enumerate(rows):
        y = r * RH
        _snd = ("   sound lands %.2fs (%s)"
                % (m["sound_lands_s"], m.get("sync") or "sync not named")
                if m.get("sound_lands_s") is not None else "")
        d.text((5, y + 3), "%d  %.2fs -> %.2fs  %s%s"
               % (m["n"], m["t_from_s"], m["t_to_s"],
                  "+".join(m["families"]) or "-", _snd), fill=INK, font=font)
        for i, (fp, t) in enumerate(zip(frames, times)):
            cx = i * STRIP_W
            im = Image.open(fp).convert("RGB")
            im.thumbnail((STRIP_W - 4, STRIP_H - 4))
            sheet.paste(im, (cx + (STRIP_W - im.width) // 2, y + HEAD_H))
            _hit = (m.get("sound_lands_s") is not None
                    and i == min(range(len(times)),
                                 key=lambda k: abs(times[k]
                                                   - m["sound_lands_s"])))
            d.text((cx + 5, y + HEAD_H + STRIP_H + 1),
                   "%.2fs%s" % (t, "  <-- the hit" if _hit else ""),
                   fill=(255, 190, 90) if _hit else INK, font=small)
            d.rectangle([cx, y, cx + STRIP_W - 1, y + RH - 1],
                        outline=(70, 70, 78))
    sheet.save(path, "PNG", optimize=True)
    return sheet.width, sheet.height


def load():
    """(records, states). A video without a MEASURED file is NAMED, not skipped."""
    recs, states = [], {}
    if not os.path.isdir(IN):
        raise SystemExit("no %s — run run_watch_moments.py first" % IN)
    for n in sorted(os.listdir(IN)):
        if not n.endswith(".json"):
            continue
        r = json.load(open(os.path.join(IN, n)))
        states[r.get("label") or n] = r.get("state")
        if r.get("state") == "MEASURED":
            recs.append(r)
    return recs, states


def select(recs, per_video):
    """The moments that matter, by a rule that is stated and mechanical.

    Per video: the hook first, then the turn or payoff, then whichever
    remaining moment adds the most unseen (family, where) pairs. Greedy
    coverage rather than 'the best ones' — 'best' is a judgement nobody can
    re-derive, coverage is arithmetic.
    """
    seen, picked = set(), []
    for r in recs:
        ms = list((r.get("record") or {}).get("moments") or [])
        label = r["label"]
        take = []

        def pop(pred):
            for m in ms:
                if pred(m):
                    ms.remove(m)
                    return m
            return None

        # THE HOOK, THE TURN, AND AT LEAST ONE RESTRAINT MOMENT PER VIDEO.
        # Restraint is the half the greedy coverage rule would lose: a
        # restraint moment usually names no family, so it adds no (family,
        # where) pair and sorts last forever. A sheet made of placements
        # teaches "put something here", which is the fact an imitator copies;
        # the decision NOT to place is the half that generalises. So it is
        # taken by name, not left to arithmetic.
        for pred in (lambda m: m["purpose"] == "hook",
                     lambda m: m["purpose"] in ("turn", "payoff"),
                     lambda m: m.get("kind") == "restraint"):
            m = pop(pred)
            if m:
                take.append(m)
        while len(take) < per_video and ms:
            def gain(m):
                return len({(f, m["where"]) for f in (m["families"] or ["none"])}
                           - seen)
            ms.sort(key=lambda m: (-gain(m), m["t_settled_s"]))
            take.append(ms.pop(0))
        for m in take:
            seen |= {(f, m["where"]) for f in (m["families"] or ["none"])}
            m = dict(m)
            m["video"] = label
            m["whole"] = (r.get("record") or {}).get("whole_video") or {}
            picked.append(m)
    return picked


def tile(frames, lines, path):
    """A numbered contact sheet. The number in the header is the line number."""
    from PIL import Image, ImageDraw, ImageFont
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", 15)
    except Exception:                                             # noqa: BLE001
        font = ImageFont.load_default()
    n = len(frames)
    cols = min(COLS, n)
    rows = (n + cols - 1) // cols
    W, H = cols * TILE_W, rows * (TILE_H + HEAD_H)
    sheet = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(sheet)
    for i, (fp, ln) in enumerate(zip(frames, lines)):
        cx, cy = (i % cols) * TILE_W, (i // cols) * (TILE_H + HEAD_H)
        d.text((cx + 5, cy + 3), "%d  %.1fs  %s"
               % (ln["n"], ln["t"], ln["where"]), fill=INK, font=font)
        im = Image.open(fp).convert("RGB")
        im.thumbnail((TILE_W - 4, TILE_H - 4))
        sheet.paste(im, (cx + (TILE_W - im.width) // 2,
                         cy + HEAD_H + (TILE_H - im.height) // 2))
        d.rectangle([cx, cy, cx + TILE_W - 1, cy + TILE_H + HEAD_H - 1],
                    outline=(70, 70, 78))
    sheet.save(path, "PNG", optimize=True)
    return W, H


def sheet_text(picked, whole):
    """The glanceable half. One line per moment, keyed to the tile number."""
    L = ["THE TEN, AT THE MOMENTS THAT MATTER — the frames are on the sheets "
         "beside this, numbered to these lines.",
         "",
         "This is not a description of good editing. It is what an editor did "
         "at a specific moment, the frame it produced, and the condition that "
         "made it the right call. When you are at a moment of the same shape, "
         "do the same thing. Where this and any prose document disagree, the "
         "moment wins — it has a picture.",
         ""]
    # NOT TRUNCATED. These ten lines are what each video is ARGUING, and a
    # sentence cut at 110 characters mid-word is the truncated-list defect in
    # prose form: it reads like a complete thought and is missing its verb.
    for v, w in whole:
        L.append("  %-10s %s" % (v[:10], w.get("what_it_is_doing") or "(none)"))
    _nr = sum(1 for m in picked if m.get("kind") == "restraint")
    L += ["",
          "  Half of this sheet is PLACEMENT — what an editor did at that "
          "second. The rest is RESTRAINT — a moment where a competent editor "
          "would have reached for something and this one did not, and the "
          "video is better for it. %d of %d moments below are restraint. The "
          "NOT line on every moment is the obvious alternative and why it "
          "loses; that is the half you can apply somewhere else." % (_nr,
                                                                     len(picked)),
          "",
          "  A moment that is a CHANGE — a cut, a transition, a sound "
          "landing — carries a STRIP: five frames through it, on the strip "
          "sheet, with the times under them and the sound's hit marked. One "
          "settled frame of a cut shows where it ended up and hides what it "
          "did.",
          "",
          "  #   t     kind       purpose   where   families",
          "        SEEN / HEARD / SOUND / THE EDIT / WHY IT LANDS / NOT", ""]
    for m in picked:
        L.append("  %-3d %5.1f %-10s %-9s %-7s %s"
                 % (m["n"], m["t_settled_s"], (m.get("kind") or "placement"),
                    m["purpose"], m["where"], "+".join(m["families"]) or "-"))
        if m.get("t_from_s") is not None:
            L.append("        strip: %.2fs -> %.2fs, five frames through the "
                     "change (see the STRIP sheet)"
                     % (m["t_from_s"], m["t_to_s"]))
        L.append("        %s" % m["on_screen"])
        L.append("        heard: %s" % m["heard"])
        # THE AUDIO, AS AN EDIT. "there is a whoosh here" is the same useless
        # fact as "a card is here"; when it lands and what it marks is the half
        # that transfers.
        if m.get("sound_lands_s") is not None:
            L.append("        sound: lands %.2fs, %s — punctuates %s"
                     % (m["sound_lands_s"], m.get("sync") or "sync not named",
                        m.get("punctuates") or "(not named)"))
        L.append("        edit:  %s" % m["cut_does"])
        L.append("        why:   %s" % m["why_lands"])
        # THE LINE THAT GENERALISES. Kept last and kept on the sheet even
        # though it is the most expensive field: "a card is here" is a fact to
        # copy, "a card and not a cutaway, because the face carries the
        # accusation" is a decision to apply somewhere else.
        if m.get("instead_of"):
            L.append("        NOT:   %s" % m["instead_of"])
        L.append("")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-video", type=int, default=4)
    ap.add_argument("--no-gate", action="store_true",
                    help="build without the verify pass — writes NOTHING to "
                         "watched/, only a preview, so an ungated sheet can "
                         "never be the one that ships")
    a = ap.parse_args()

    recs, states = load()
    print("  videos: %s" % states)
    if not recs:
        raise SystemExit("no MEASURED videos")

    picked = select(recs, a.per_video)
    for i, m in enumerate(picked, 1):
        # `src_n` names the FRAME FILE on disk and never changes; `n` is the
        # number printed on the tile and renumbered after the gate. Keeping one
        # field for both is how a renumber silently repaints frame 14 with
        # line 9's caption — the exact failure this whole gate exists to stop.
        m["n"] = m["src_n"] = i
    print("  selected %d moments from %d videos (<=%d each)"
          % (len(picked), len(recs), a.per_video))

    work = os.path.join("/tmp", "watched_frames")
    os.makedirs(work, exist_ok=True)
    frames, kept, strips = [], [], []
    for m in picked:
        ts = strip_times(m)
        if ts:
            # A STRIP MOMENT NEEDS EVERY FRAME. A row with a hole in it is a
            # sequence missing the part that might be the change, so a single
            # failed grab drops the whole strip to the single-frame path rather
            # than drawing four frames and calling it five.
            fps = []
            for k, t in enumerate(ts):
                fp = os.path.join(work, "s%03d_%d.jpg" % (m["n"], k))
                if not ffmpeg_frame(os.path.join(EX, m["video"]), t, fp):
                    fps = []
                    break
                fps.append(fp)
            if fps:
                m["strip_times"] = ts
                strips.append((m, fps, ts))
                kept.append(m)
                continue
            m["span_state"] = (m.get("span_state") or "") + " (a frame grab "
            m["t_from_s"] = m["t_to_s"] = None
        fp = os.path.join(work, "m%03d.jpg" % m["n"])
        if ffmpeg_frame(os.path.join(EX, m["video"]), m["t_settled_s"], fp):
            frames.append(fp)
            kept.append(m)
        else:
            m["gate"] = "FRAME FAILED"
    _singles = [m for m in kept if not m.get("strip_times")]
    print("  %d strip(s), %d single frame(s)" % (len(strips), len(frames)))
    if len(kept) != len(picked):
        print("  *** %d moments lost their frame" % (len(picked) - len(kept)))

    # ── tile, then GATE ─────────────────────────────────────────────────────
    per = COLS * ROWS
    groups = [(_singles[i:i + per], frames[i:i + per])
              for i in range(0, len(_singles), per)]
    strip_groups = [strips[i:i + STRIP_ROWS]
                    for i in range(0, len(strips), STRIP_ROWS)]
    os.makedirs(os.path.join(OUT, "tiles"), exist_ok=True)
    preview = os.path.join("/tmp", "watched_preview")
    os.makedirs(preview, exist_ok=True)
    dst_dir = preview if a.no_gate else os.path.join(OUT, "tiles")

    # THE VERDICT CACHE. Keyed on the FRAME BYTES plus the exact line text, so
    # a re-run re-verifies only what changed and a rate limit costs one sheet
    # rather than the whole gate. Keying on the moment NUMBER would be wrong —
    # the numbers are renumbered after the gate, and a cache that survives a
    # renumber is the mechanism for pinning last run's verdict to this run's
    # frame.
    cache_p = "/tmp/watched_verdict_cache.json"
    try:
        cache = json.load(open(cache_p))
    except Exception:                                             # noqa: BLE001
        cache = {}

    # THE PROMPT'S HASH IS PART OF THE KEY. Without it, changing the verify
    # prompt silently reuses the verdicts the OLD prompt gave — which is
    # exactly what would have happened here: the first restraint build lost 9
    # of 12 held moments to a verifier that read the video's own burned-in
    # caption track as contradicting "no graphic here", and the fix is a
    # prompt change. A cache that survives the fix hands back the bug.
    import hashlib as _hl
    _pver = _hl.sha256(
        open(os.path.join(HERE, "watch_verify_prompt.txt"), "rb").read()
    ).hexdigest()[:8]
    print("  verify prompt: %s" % _pver)

    def key_of(m, fp):
        h = _hl.sha256(open(fp, "rb").read()).hexdigest()[:16]
        return "%s|%s|%s" % (_pver, h, m["on_screen"].strip())

    verdicts = {}
    px_total = 0
    for gi, (ms, fs) in enumerate(groups, 1):
        lines = [{"n": m["n"], "t": m["t_settled_s"], "where": m["where"],
                  "kind": m.get("kind") or "placement",
                  "on_screen": m["on_screen"]} for m in ms]
        p = os.path.join("/tmp", "sheet_%d.png" % gi)
        W, H = tile(fs, lines, p)
        px_total += W * H
        print("  sheet %d: %d tiles  %dx%d px  %d KB  ~%d image tokens"
              % (gi, len(fs), W, H, os.path.getsize(p) // 1024, W * H // 750))
        if a.no_gate:
            continue
        cached = {m["n"]: cache[key_of(m, f)] for m, f in zip(ms, fs)
                  if key_of(m, f) in cache}
        if len(cached) == len(ms):
            print("    verify: CACHED (%d/%d frames unchanged since a verified "
                  "run)" % (len(cached), len(ms)))
            verdicts.update(cached)
            continue
        import modal
        fn = modal.Function.from_name("promptly-watch-moments", "verify")
        if gi > 1:
            # PACE THE SHEETS. Three large images inside one minute is what
            # exhausted the quota and cost a whole video its frames.
            time.sleep(20)
        r = fn.remote(open(p, "rb").read(), lines)
        print("    verify: %s  %s" % (r["state"], (r.get("detail") or "")[:90]))
        if r["state"] != "MEASURED":
            # A verify pass that could not run is not a pass. Every tile on
            # this sheet is UNCHECKED, and UNCHECKED does not ship.
            for m in ms:
                verdicts[m["n"]] = {"verdict": "unchecked",
                                    "frame_says": r.get("detail") or ""}
            continue
        for v in r["verdicts"]:
            verdicts[int(v.get("n") or 0)] = v
        for m, f in zip(ms, fs):
            if m["n"] in verdicts:
                cache[key_of(m, f)] = verdicts[m["n"]]
        json.dump(cache, open(cache_p, "w"))

    # ── THE STRIPS GO THROUGH THE SAME GATE ─────────────────────────────────
    for gi, rows in enumerate(strip_groups, 1):
        lines = [{"n": m["n"], "t": m["t_settled_s"], "where": m["where"],
                  "kind": m.get("kind") or "placement", "strip": True,
                  "span": "%.2f->%.2f" % (m["t_from_s"], m["t_to_s"]),
                  "on_screen": m["on_screen"], "cut_does": m["cut_does"]}
                 for m, _f, _t in rows]
        p = os.path.join("/tmp", "strip_%d.png" % gi)
        W, H = tile_strip(rows, p)
        px_total += W * H
        print("  strip sheet %d: %d row(s)  %dx%d px  %d KB  ~%d image tokens"
              % (gi, len(rows), W, H, os.path.getsize(p) // 1024, W * H // 750))
        if a.no_gate:
            continue
        cached = {m["n"]: cache[key_of(m, f[0])] for m, f, _t in rows
                  if key_of(m, f[0]) in cache}
        if len(cached) == len(rows):
            print("    verify: CACHED (%d/%d strips unchanged)"
                  % (len(cached), len(rows)))
            verdicts.update(cached)
            continue
        import modal
        fn = modal.Function.from_name("promptly-watch-moments", "verify")
        time.sleep(20)
        r = fn.remote(open(p, "rb").read(), lines)
        print("    verify: %s  %s" % (r["state"], (r.get("detail") or "")[:90]))
        if r["state"] != "MEASURED":
            for m, _f, _t in rows:
                verdicts[m["n"]] = {"verdict": "unchecked",
                                    "frame_says": r.get("detail") or ""}
            continue
        for v in r["verdicts"]:
            verdicts[int(v.get("n") or 0)] = v
        for m, f, _t in rows:
            if m["n"] in verdicts:
                cache[key_of(m, f[0])] = verdicts[m["n"]]
        json.dump(cache, open(cache_p, "w"))

    if a.no_gate:
        for gi in range(1, len(groups) + 1):
            os.replace("/tmp/sheet_%d.png" % gi,
                       os.path.join(preview, "SHEET_%d.png" % gi))
        open("/tmp/watched_preview/SHEET.md", "w").write(
            sheet_text(kept, [(r["label"],
                               (r.get("record") or {}).get("whole_video") or {})
                              for r in recs]))
        print("  PREVIEW ONLY (--no-gate): %s — not shipped" % preview)
        return 0

    shipped, held = [], []
    for m in kept:
        v = verdicts.get(m["n"]) or {"verdict": "missing", "frame_says": ""}
        m["gate"] = v.get("verdict")
        m["frame_says"] = v.get("frame_says") or ""
        (shipped if v.get("verdict") == "yes" else held).append(m)
    print("\n  GATE: %d shown, %d held back" % (len(shipped), len(held)))
    for m in held:
        print("    %-3d %-40s %-9s %s | line said: %s"
              % (m["n"], m["video"][:40], m["gate"],
                 (m.get("frame_says") or "")[:44], m["on_screen"][:44]))

    if not shipped:
        raise SystemExit("*** NOTHING passed the gate — the artefact is not "
                         "built. This is the correct outcome for a pass whose "
                         "timestamps did not land, not a reason to skip it.")

    # RENUMBER AND RE-TILE FROM THE SURVIVORS ONLY, so the numbers on the
    # shipped sheets are contiguous and every number on a sheet has a line.
    for i, m in enumerate(shipped, 1):
        m["n"] = i
    px_total = 0
    _ship_strips = [m for m in shipped if m.get("strip_times")]
    _ship_single = [m for m in shipped if not m.get("strip_times")]
    for gi in range(0, len(_ship_strips), STRIP_ROWS):
        ms = _ship_strips[gi:gi + STRIP_ROWS]
        rows = [(m, [os.path.join(work, "s%03d_%d.jpg" % (m["src_n"], k))
                     for k in range(len(m["strip_times"]))], m["strip_times"])
                for m in ms]
        p = os.path.join(OUT, "tiles", "STRIP_%d.png" % (gi // STRIP_ROWS + 1))
        W, H = tile_strip(rows, p)
        px_total += W * H
        print("  shipped strip sheet %d: %d row(s) %dx%d ~%d tok"
              % (gi // STRIP_ROWS + 1, len(ms), W, H, W * H // 750))
    for gi in range(0, len(_ship_single), per):
        ms = _ship_single[gi:gi + per]
        lines = [{"n": m["n"], "t": m["t_settled_s"], "where": m["where"],
                  "kind": m.get("kind") or "placement",
                  "on_screen": m["on_screen"]} for m in ms]
        ms_frames = [os.path.join(work, "m%03d.jpg" % m["src_n"]) for m in ms]
        if not ms_frames:
            continue
        p = os.path.join(OUT, "tiles", "SHEET_%d.png" % (gi // per + 1))
        W, H = tile(ms_frames, lines, p)
        px_total += W * H
        print("  shipped sheet %d: %d tiles %dx%d ~%d tok"
              % (gi // per + 1, len(ms), W, H, W * H // 750))

    txt = sheet_text(shipped, [(r["label"],
                                (r.get("record") or {}).get("whole_video") or {})
                               for r in recs])
    open(os.path.join(OUT, "SHEET.md"), "w").write(txt)
    _dens = {"placement": sum(1 for m in shipped
                              if (m.get("kind") or "placement") == "placement"),
             "restraint": sum(1 for m in shipped
                              if m.get("kind") == "restraint")}
    _dens["restraint_share"] = (round(100.0 * _dens["restraint"]
                                      / max(1, len(shipped)), 1))
    _dens["videos_with_a_restraint_moment"] = len(
        {m["video"] for m in shipped if m.get("kind") == "restraint"})
    print("  DENSITY: %d placement, %d restraint (%.1f%%), restraint present "
          "in %d of %d videos"
          % (_dens["placement"], _dens["restraint"], _dens["restraint_share"],
             _dens["videos_with_a_restraint_moment"], len(recs)))
    json.dump({"states": states, "shipped": shipped, "held": held,
               "density": _dens,
               "tile_px": px_total, "image_tokens": px_total // 750,
               "text_chars": len(txt)},
              open(os.path.join(OUT, "moments.json"), "w"), indent=1)
    print("\n  SHEET.md %d chars (~%d tok) + %d sheets (~%d image tok) = ~%d tok"
          % (len(txt), len(txt) // 4, (len(shipped) + per - 1) // per,
             px_total // 750, len(txt) // 4 + px_total // 750))
    return 0


if __name__ == "__main__":
    sys.exit(main())
