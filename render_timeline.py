"""RenderTimeline — the ONE output-timeline truth (unification pillar 3).

Frames-first: the output timeline is quantized to integer frames at
source_fps EXACTLY ONCE, here. Every seconds/sample view is derived from
the frame truth, never re-accumulated. One floor rule for slots: a slot
that rounds to 0 frames DOES NOT EXIST anywhere — not in the total, not in
the list, not in audio, not in the masks (kills #D3 in both directions).

Slice 1 (this file) is SHADOW ONLY: build_render_timeline is computed
alongside the five current representations and shadow_check logs every
divergence for the census. NOTHING consumes it yet — zero behavior change.
Consumer cutover + deletion of the duplicate accounting is Slice 2 (a
separate GO).

The INSERT model is the frame truth (what the render concatenates: body,
slot, body, slot …), matching ffmpeg_base concat and build_per_cut_audio.
The OVERLAP/handle seconds model (get_output_clip_ranges) is a derived
view; the shadow records where the two diverge rather than assuming parity.
"""


def build_render_timeline(render_cuts, effective_durations, trim_head_dur,
                          trim_tail_dur, trans_dur_after, clip_time_maps,
                          source_fps):
    """Construct the one truth. Returns a dict:
        {fps, total_frames, entries: [{cut_index, out_start_frame,
         body_frames, slot_frames_after, source_start, source_end,
         avg_speed, trim_head_s, trim_tail_s}]}
    All frame quantities are the AUTHORITATIVE integer-frame truth.
    """
    fps = float(source_fps)
    n = len(render_cuts)
    entries = []
    cum = 0
    for i in range(n):
        eff = float(effective_durations[i]) if i < len(effective_durations) else 0.0
        th = float(trim_head_dur[i]) if i < len(trim_head_dur) else 0.0
        tt = float(trim_tail_dur[i]) if i < len(trim_tail_dur) else 0.0
        body_s = eff - th - tt
        body_frames = max(1, int(round(body_s * fps)))
        slot_s = float(trans_dur_after[i]) if i < len(trans_dur_after) else 0.0
        # THE ONE FLOOR RULE: round once; 0 means the slot does not exist.
        slot_frames = int(round(slot_s * fps))
        if slot_frames < 0:
            slot_frames = 0
        avg_speed = 1.0
        if i < len(clip_time_maps) and clip_time_maps[i]:
            avg_speed = float(clip_time_maps[i].get("avg_speed") or 1.0)
        entries.append({
            "cut_index": i,
            "out_start_frame": cum,
            "body_frames": body_frames,
            "slot_frames_after": slot_frames,
            "source_start": float(render_cuts[i].get("source_start") or 0.0),
            "source_end": float(render_cuts[i].get("source_end") or 0.0),
            "avg_speed": avg_speed,
            "trim_head_s": th,
            "trim_tail_s": tt,
        })
        cum += body_frames + slot_frames
    return {"fps": fps, "total_frames": max(1, cum), "entries": entries}


def assert_frame_truth(tl, effective_durations, trim_head_dur, trim_tail_dur,
                       trans_dur_after, source_fps):
    """v197-lineage parity tripwire, re-anchored to the one truth (Slice 2).

    Re-derives the proven-correct per-cut frame accounting and asserts the
    timeline matches it EXACTLY on body frames and every REAL slot. The
    ONLY sanctioned difference is the #D3 phantom drop (a sub-frame slot
    that the old total counted as max(1) and the timeline correctly omits) —
    that lives in the total, never in a body or a real slot. Any body-frame
    or real-slot movement is a hard STOP: raise, failing the render loudly
    rather than shipping a shifted boundary (the census proved these were
    perfect; they must stay perfect).
    """
    fps = float(source_fps)
    for e in tl["entries"]:
        i = e["cut_index"]
        eff = float(effective_durations[i]) if i < len(effective_durations) else 0.0
        th = float(trim_head_dur[i]) if i < len(trim_head_dur) else 0.0
        tt = float(trim_tail_dur[i]) if i < len(trim_tail_dur) else 0.0
        old_body = max(1, int(round((eff - th - tt) * fps)))
        if e["body_frames"] != old_body:
            raise RuntimeError(
                f"ONE-TRUTH BODY VIOLATION cut {i}: timeline "
                f"{e['body_frames']}f != accounting {old_body}f")
        slot_s = float(trans_dur_after[i]) if i < len(trans_dur_after) else 0.0
        old_slot = int(round(slot_s * fps))
        # a REAL slot (rounds to >=1) must match to the frame; a phantom
        # (old max(1) over a sub-frame slot) is the sanctioned #D3 drop.
        if old_slot > 0 and e["slot_frames_after"] != old_slot:
            raise RuntimeError(
                f"ONE-TRUTH SLOT VIOLATION cut {i}: timeline "
                f"{e['slot_frames_after']}f != accounting {old_slot}f")


# ── Derived views (never re-accumulate; read the frame truth) ──────────────
def total_seconds(tl):
    return tl["total_frames"] / tl["fps"]


def body_frames_list(tl):
    return [e["body_frames"] for e in tl["entries"]]


def slot_frames_list(tl):
    return [e["slot_frames_after"] for e in tl["entries"]]


def shadow_check(tl, *, current_total_frames, current_per_cut_render_frames,
                 body_seconds, slot_seconds, transitions_out, clip_ranges,
                 source_fps):
    """Compare the one truth to the five current representations. Returns a
    divergence record (always) for the census; the caller logs it. Pure —
    no mutation, no raise.

    Two divergence CLASSES, adjudicated differently in the census:
      - INTEGRITY (body identity, total vs R1, slot vs transitions_out):
        a mismatch is a real defect or the known #D3 phantom.
      - ROUNDING (#D1: sum-of-rounds vs round-of-sum): expected ±1-frame
        noise, recorded per the bug-audit rider so each site is on record.
    """
    fps = float(source_fps)
    div = {"total": {}, "body": [], "slots": [], "d1": {}, "info": {}}

    # (1) total_frames: timeline (one floor) vs R1 (max(1)-per-slot sum).
    # A nonzero delta here == the #D3 phantom-frame count (slots that
    # rounded to 0 but were counted as 1 in R1). INTEGRITY class.
    div["total"] = {
        "timeline": tl["total_frames"],
        "current_R1": int(current_total_frames),
        "delta": tl["total_frames"] - int(current_total_frames),
    }

    # (2) body frames identity — MUST match _per_cut_render_dur_frames.
    # Any delta is a genuine defect (same formula both sides). INTEGRITY.
    tl_body = body_frames_list(tl)
    for i, bf in enumerate(tl_body):
        cur = (int(current_per_cut_render_frames[i])
               if i < len(current_per_cut_render_frames) else None)
        if cur is not None and cur != bf:
            div["body"].append({"cut": i, "timeline": bf, "current": cur,
                                "delta": bf - cur})

    # (3) slot frames vs transitions_out.durationInFrames. The #D3 domain:
    # a slot the timeline drops (0) but transitions_out kept, or vice
    # versa, or a frame mismatch. INTEGRITY.
    trans_by_ai = {int(t.get("afterClipIndex", -1)): t for t in transitions_out}
    for e in tl["entries"]:
        i = e["cut_index"]
        tl_slot = e["slot_frames_after"]
        t = trans_by_ai.get(i)
        cur_slot = int(t.get("durationInFrames") or 0) if t else 0
        if tl_slot != cur_slot:
            div["slots"].append({
                "cut": i, "timeline_frames": tl_slot,
                "transitions_out_frames": cur_slot,
                "in_transitions_out": t is not None,
                "delta": tl_slot - cur_slot,
            })

    # (4) #D1 — sum-of-rounds vs round-of-sum, apples-to-apples on the SAME
    # insert quantities. This isolates the pure rounding effect the design
    # named (per-segment rounding then summed, vs the float total rounded
    # once). ROUNDING class — recorded for the census, not an integrity bug.
    if body_seconds is not None and slot_seconds is not None:
        sum_s = sum(body_seconds) + sum(slot_seconds)
        round_of_sum = max(1, int(round(sum_s * fps)))
        div["d1"] = {
            "sum_of_rounds": tl["total_frames"],
            "round_of_sum": round_of_sum,
            "delta": tl["total_frames"] - round_of_sum,
        }

    # informational: the overlap seconds model's implied total (different
    # reference points from the insert model by construction — recorded, not
    # flagged), so the census can see the R1↔R2 relationship.
    if clip_ranges:
        div["info"]["clip_ranges_total_frames"] = int(round(
            float(clip_ranges[-1].get("end") or 0.0) * fps))

    div["integrity_divergence"] = bool(
        div["total"]["delta"] or div["body"] or div["slots"])
    div["rounding_divergence"] = bool(div["d1"].get("delta"))
    div["has_divergence"] = div["integrity_divergence"] or div["rounding_divergence"]
    return div
