#!/usr/bin/env python3
"""Every credit charged is correct, stated before it is spent, and unforgeable.

THE PRICE TABLE EXISTED AND NOTHING CHARGED FROM IT. dispatch_classifier quoted
a FLAT AI_VIDEO_CREDITS = 20 for any generated video. Against a 5-second clip
that is UNDER cost on 7 of the 11 model x resolution rows credit_prices.py
carries, by up to 5.8x — Seedance 2.5 at 1080p is 115 of our credits and we
quote 20. A flat number cannot be right for a price that varies 11x with
resolution alone.

NOTHING HERE WRITES TO A DATABASE. Supabase is read-only for me, so the atomic
statement is a literal and every function takes an EXECUTOR — which is also why
the whole flow is testable without a database, and why the reservation's
concurrency behaviour is exercised by a fake that actually races.
"""
import hashlib
import hmac
import json
import math
import os
import time

import credit_prices as CP

QUOTE_TTL_S = 600                     # ten minutes, ruled
BATCH_MAX = 10                        # Pro, ruled
DAILY_CAP = {"pro": 10, "max": 25}    # per-day generation caps, ruled
FREE_TIERS = ("free", "trial", "none", "")

# THE SINGLE CONSTANT ZAC DECIDES. Everything else keys off it.
#
#   model                res     our credits (5s)   costs us (5s)
#   Seedance 2.0 Fast    480p           10            $0.101
#   Seedance 2.0         480p           15            $0.172
#   Seedance 2.5         480p           20            $0.244
#   Seedance 2.0 Fast    720p           20            $0.220
#   Gemini Omni          720p           25            $0.248
#   Seedance 2.0         720p           30            $0.367
#   Kling 3.0 Standard   720p           30            $0.367
#   Kling 3.0 Pro       1080p           40            $0.490
#   Seedance 2.5         720p           45            $0.549
#   Seedance 2.0        1080p           70            $0.808
#   Seedance 2.5        1080p          115            $1.358
#
# MY RECOMMENDATION IS Seedance 2.0 at 720p, and the reason is the canvas
# rather than the price. Output is 1080x1920 VERTICAL; a generated clip is
# b-roll behind captions and graphics, not the hero. 720p upscales to a 1080
# canvas with visible softness only on fine detail, which is exactly what
# b-roll does not have. It is $0.367 against $1.358 for Seedance 2.5 at
# 1080p — 3.7x — for a difference most of this footage cannot show.
#
# I am NOT recommending the cheapest. Seedance 2.0 Fast at 480p is $0.101 and
# on a 1080-wide canvas that is a 2.25x upscale, which is soft enough to read
# as a defect rather than as footage. The floor is legibility, not price.
AI_VIDEO_DEFAULT = ("Seedance 2.0", "720p")


def _secret():
    """The signing key. NO DEFAULT — an unset secret must refuse, not sign.

    A fallback here would make every quote forgeable by anyone who read the
    source, and it would work perfectly in every test.
    """
    s = os.environ.get("PROMPTLY_QUOTE_SECRET", "")
    if not s:
        raise RuntimeError("PROMPTLY_QUOTE_SECRET is unset — refusing to sign "
                           "a quote rather than signing it with a known key")
    return s.encode("utf-8")


def price_for(feature, model, resolution, duration_s):
    """-> (credits, why) from the TABLE. Never a flat number, never a guess."""
    per_unit, why = CP.our_price(feature, model, resolution)
    if per_unit is None:
        return None, why
    if feature == "video":
        if duration_s is None or duration_s <= 0:
            return None, "duration is required to price a video"
        return int(math.ceil(per_unit * duration_s)), "%d/s x %gs — %s" % (
            per_unit, duration_s, why)
    return int(per_unit), why


def issue_quote(feature, model, resolution, duration_s, tier, now=None):
    """-> a SERVER-ISSUED, SIGNED quote. The client gets an opaque id.

    THE QUOTE CARRIES ITS OWN INPUTS so the server can RE-DERIVE the price
    from the signed fields instead of trusting a number that came back. A
    client that sends a price is sending an opinion; it is never read.
    """
    now = time.time() if now is None else now
    if str(tier or "").strip().lower() in FREE_TIERS:
        return {"state": "REFUSED_FREE_TIER", "http": 402,
                "message": "Generated video is a Pro feature.",
                "credits": 0, "quote_id": None}
    credits, why = price_for(feature, model, resolution, duration_s)
    if credits is None:
        return {"state": "UNPRICEABLE", "credits": 0, "quote_id": None, "why": why}
    body = {"feature": feature, "model": model, "resolution": resolution,
            "duration_s": duration_s, "credits": credits,
            "expires_at": now + QUOTE_TTL_S, "tier": tier}
    raw = json.dumps(body, sort_keys=True, separators=(",", ":"))
    sig = hmac.new(_secret(), raw.encode("utf-8"), hashlib.sha256).hexdigest()[:32]
    return {"state": "QUOTED", "quote_id": "%s.%s" % (
        hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16], sig),
        "_body": raw, "credits": credits, "why": why, **body}


def redeem_quote(quote_id, body_raw, now=None):
    """-> (ok, credits_or_None, reason). The server RE-DERIVES; nothing is trusted.

    THREE WAYS THIS REFUSES, and each is a separate state rather than a
    shared False: a forged signature, an expired quote, and a quote whose
    re-derived price no longer matches what was signed — which means the
    price table moved under it and the honest answer is a new quote.
    """
    now = time.time() if now is None else now
    try:
        body = json.loads(body_raw)
    except Exception:                                          # noqa: BLE001
        return False, None, "UNREADABLE_QUOTE"
    sig = hmac.new(_secret(), body_raw.encode("utf-8"), hashlib.sha256).hexdigest()[:32]
    want = "%s.%s" % (hashlib.sha256(body_raw.encode("utf-8")).hexdigest()[:16], sig)
    if not hmac.compare_digest(want, str(quote_id or "")):
        return False, None, "BAD_SIGNATURE"
    if now > body.get("expires_at", 0):
        return False, None, "EXPIRED"
    fresh, _why = price_for(body["feature"], body["model"], body["resolution"],
                            body.get("duration_s"))
    if fresh is None or fresh != body["credits"]:
        return False, None, "PRICE_MOVED"
    return True, int(body["credits"]), "OK"


# ── THE ATOMIC RESERVATION ────────────────────────────────────────────────
# ONE STATEMENT. A read-then-write cannot be made safe by ordering: two
# requests both read 30, both see 30 >= 20, both write 10, and the user has
# spent 40 from a 30 balance. The guard has to be IN the write.
#
# The idempotency key makes a double-tap a no-op rather than a second charge:
# the INSERT ... ON CONFLICT DO NOTHING either claims the key or does not, and
# only the claimant debits. A retry returns the FIRST result, not a new one.
RESERVE_SQL = """
WITH claim AS (
  INSERT INTO credit_reservations (idem_key, user_id, quote_id, credits, state)
  VALUES ($1, $2, $3, $4, 'reserved')
  ON CONFLICT (idem_key) DO NOTHING
  RETURNING id
), debit AS (
  UPDATE profiles
     SET credit_balance = credit_balance - $4
   WHERE id = $2
     AND credit_balance >= $4
     AND EXISTS (SELECT 1 FROM claim)
  RETURNING credit_balance
)
SELECT
  (SELECT count(*) FROM claim)          AS claimed,
  (SELECT credit_balance FROM debit)    AS new_balance,
  (SELECT credit_balance FROM profiles WHERE id = $2) AS current_balance;
"""


def reserve(execute, user_id, quote_id, credits, idem_key):
    """-> dict. Reserve at dispatch, atomically, idempotently.

    `execute(sql, params) -> row dict`. Injected so the whole flow is testable
    without a database — and so the concurrency test can actually race.
    """
    row = execute(RESERVE_SQL, [idem_key, user_id, quote_id, credits])
    if not row.get("claimed"):
        return {"state": "ALREADY_RESERVED", "credits": credits,
                "balance": row.get("current_balance")}
    if row.get("new_balance") is None:
        return {"state": "INSUFFICIENT", "credits": credits,
                "balance": row.get("current_balance"),
                "shortfall": max(0, credits - (row.get("current_balance") or 0))}
    return {"state": "RESERVED", "credits": credits, "balance": row["new_balance"]}


def price_batch(items, tier, balance):
    """-> dict. The WHOLE batch priced, reserved in one transaction or not at all.

    NO PARTIAL DISPATCH. If the balance covers 6 of 10 the answer is "6, and
    you are 140 short" — not six videos and a surprise. The user may then
    choose the first N, which is a NEW request with its own quote, because a
    silently shortened batch is the same defect as a truncated list printed
    as a total.
    """
    if not items:
        return {"state": "EMPTY", "covered": 0, "credits": 0}
    if len(items) > BATCH_MAX:
        return {"state": "TOO_MANY", "max": BATCH_MAX, "asked": len(items),
                "covered": 0, "credits": 0}
    priced, total = [], 0
    for it in items:
        c, why = price_for(it.get("feature", "video"), it["model"],
                           it["resolution"], it.get("duration_s"))
        if c is None:
            return {"state": "UNPRICEABLE", "item": it, "why": why,
                    "covered": 0, "credits": 0}
        priced.append(c)
        total += c
    if balance >= total:
        return {"state": "COVERED", "covered": len(items), "credits": total,
                "per_item": priced}
    covered, run = 0, 0
    for c in priced:
        if run + c > balance:
            break
        run += c
        covered += 1
    return {"state": "SHORTFALL", "covered": covered, "credits": total,
            "affordable_credits": run, "shortfall": total - balance,
            "per_item": priced}


def check_drift(quote_credits, measured_chatcut_delta):
    """-> dict. The user is NEVER charged more than the quote.

    An over-run is OUR problem and a signal: either the price table is stale
    or something generated that nobody asked for. The paid-tier brief line
    says "only generate new images, video, voiceover or music if the user
    asked for it", so unrequested generation lands here as a delta with no
    quote behind it.
    """
    if measured_chatcut_delta is None:
        return {"state": "UNMEASURED", "charge": quote_credits,
                "alarm": True, "why": "no balance delta — cannot confirm the quote"}
    ours = math.ceil(measured_chatcut_delta * CP.OUR_PER_THEIRS)
    if ours > quote_credits:
        return {"state": "OVER_QUOTE", "charge": quote_credits, "actual": ours,
                "over_by": ours - quote_credits, "alarm": True,
                "why": "charged the quote; the overage is ours"}
    return {"state": "WITHIN_QUOTE", "charge": quote_credits, "actual": ours,
            "alarm": False}


# ── THE LOOPHOLES, CLOSED ─────────────────────────────────────────────────
# Each of these is a way to get generation without paying for it correctly.
# They are functions rather than comments because a rule that is not called
# is a rule that does not run, and every one has a mutation aimed at it.

def free_tier_generation(tier):
    """402 for a free tier, by TIER, not by what the client claims to be."""
    if str(tier or "").strip().lower() in FREE_TIERS:
        return {"allowed": False, "http": 402, "kind": "generation",
                "message": "Generated video is a Pro feature."}
    return {"allowed": True}


def free_video_allowed(server_count_this_period, client_claim=None):
    """The free video count is the SERVER'S count. The client's is ignored.

    `client_claim` is accepted only so it can be DISCARDED visibly: a count
    the client supplies is a count the client chooses, and reading it at all
    is the loophole. It is never compared and never used.
    """
    del client_claim
    return {"allowed": server_count_this_period < 1, "counted": server_count_this_period,
            "source": "server"}


def reedit_source_matches(root_source_id, requested_source_id):
    """A re-edit is bound to its ROOT'S source clip.

    Without this, a new clip enters as a "re-edit" — which does not debit
    (Ruling 3) — and a fresh edit is had for nothing. The re-edit exemption
    is what makes the binding load-bearing.
    """
    ok = bool(root_source_id) and root_source_id == requested_source_id
    return {"allowed": ok, "root": root_source_id, "requested": requested_source_id,
            "why": "" if ok else "a re-edit may only re-edit its root's source clip"}


def generation_in_reedit(feature, model, resolution, duration_s, tier):
    """Generation inside a re-edit is priced like any other generation.

    The re-edit exemption covers the EDIT, never new generated media. Without
    this, every paid generation is free by asking for it inside a re-edit.
    """
    gate = free_tier_generation(tier)
    if not gate["allowed"]:
        return gate
    credits, why = price_for(feature, model, resolution, duration_s)
    return {"allowed": credits is not None, "credits": credits, "why": why,
            "exempt": False}


def never_negative(balance, credits):
    """A balance may reach zero and must never pass it."""
    return {"allowed": balance - credits >= 0, "balance": balance,
            "credits": credits, "after": balance - credits}


def daily_cap_ok(tier, used_today, batch_size):
    """Pro 10 / Max 25 a day, enforced on the BATCH, not per video.

    Per-video enforcement is the loophole: ten single requests and one batch
    of ten are the same day's generation, and only a check that counts the
    whole batch sees the second one.
    """
    cap = DAILY_CAP.get(str(tier or "").strip().lower())
    if cap is None:
        return {"allowed": False, "why": "no cap defined for this tier", "cap": None}
    return {"allowed": used_today + batch_size <= cap, "cap": cap,
            "used": used_today, "asked": batch_size,
            "remaining": max(0, cap - used_today)}


def quote_is_live(expires_at, now=None):
    """An expired quote is refused — the price behind it may have moved."""
    now = time.time() if now is None else now
    return {"allowed": now <= expires_at, "expires_at": expires_at, "now": now}
