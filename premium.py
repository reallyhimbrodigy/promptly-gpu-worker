"""Premium-tier scaffold — Phase 1: structural base/premium split, EMPTY.

STANDALONE, lazily imported by handler.py only when a job reaches the tier
fork (handler.py, just after the input unpack). NOT imported by modal_app.py
(it is mounted via add_local_file), so it is free of the modal-CLI Python-3.9
constraints — but it stays plain/portable anyway.

Phase 1 establishes the separation between the two models WITHOUT adding any
premium behavior:

  • Model 1 (base, route_premium=False): today's pipeline, untouched, byte-identical.
  • Model 2 (premium, route_premium=True): the SAME base pipeline as a superset.
    In Phase 1 the scaffold attaches NO stage, so Model 2 output is byte-identical
    to Model 1. Later phases fill the scaffold one stage at a time, each behind
    its own flag, at the anchors in INSERTION_POINTS below.

Routing is double-gated: route_premium = is_premium AND premium_pipeline_enabled.
Flag OFF (default) ⇒ everyone takes the base path ⇒ zero change for anyone.
"""
from __future__ import annotations

import concurrent.futures
import os
from typing import Optional


# Where later phases attach their stages (handler.py anchors from the recon).
# Phase 1 attaches NONE of these — this is the map the build follows.
INSERTION_POINTS = {
    "G_input_quality_gate": "handler.py ~18596 — await ingest futures before the recipe",
    "C_gap_analysis": "handler.py 6685 — PostCutPlan.suggested_inputs advisory field",
    "E_generated_assets": "handler.py 18723 — fork the b-roll fetch path",
    "F_qa_judge": "handler.py 18980->19267 — between validate_output and the upload executor",
    "B_multi_input_ingest": "handler.py 17130 — the single-source download assumption",
    "D_ask_back_loop": "handler.py 17402-pattern — needs_input return + resume",
}


MODEL_FLARE = "flare"   # the base/free model — today's pipeline
MODEL_LUMEN = "lumen"   # the premium model — base + premium stages (filled in Phases E/F)


def client_requested_premium(input_data) -> bool:
    """Did the CLIENT pick the premium model (Lumen)? Reads ONLY the request
    payload — the per-job `premium_pipeline_enabled` boolean OR an explicit
    `model: "lumen"`. It does NOT consult the env override or the user's tier.

    This is a REQUEST, never an AUTHORIZATION: the caller ANDs the routing with
    the server-resolved tier (is_premium), so a forged flag from a free account
    can never grant premium. Used here for telemetry — upgrade demand and
    client-gate-leak / downgrade detection."""
    try:
        d = input_data or {}
        if bool(d.get("premium_pipeline_enabled")):
            return True
        if str(d.get("model") or "").strip().lower() == MODEL_LUMEN:
            return True
    except Exception:
        pass
    return False


def premium_pipeline_enabled(input_data) -> bool:
    """Master routing REQUEST — the client's Lumen pick (per-job boolean OR
    model="lumen") OR the global env override (PREMIUM_PIPELINE_ENABLED), both
    default OFF. NOT an authorization: the caller ANDs this with the
    server-resolved tier (is_premium), so the flag alone cannot grant premium."""
    if client_requested_premium(input_data):
        return True
    return os.environ.get("PREMIUM_PIPELINE_ENABLED", "").strip().lower() in (
        "1", "true", "yes", "on",
    )


def model_label(route_premium: bool) -> str:
    """The model a job actually RAN as, given the resolved routing."""
    return MODEL_LUMEN if route_premium else MODEL_FLARE


class CostMeter:
    """Per-job usage/cost accumulator. Phase 1: track-only, NO enforcement.
    Nothing calls add() yet (no premium stage incurs cost), so it reports zero —
    it exists so later generative phases accumulate against a budget."""

    def __init__(self, job_id: str, budget_usd: Optional[float] = None):
        self.job_id = job_id
        self.budget_usd = budget_usd
        self._entries = {}  # category -> {"count", "tokens", "usd"}

    def add(self, category: str, count: int = 1, tokens: int = 0, usd: float = 0.0) -> None:
        e = self._entries.setdefault(category, {"count": 0, "tokens": 0, "usd": 0.0})
        e["count"] += count
        e["tokens"] += tokens
        e["usd"] += usd

    def total_usd(self) -> float:
        return round(sum(e["usd"] for e in self._entries.values()), 4)

    def over_budget(self) -> bool:
        # Phase 1 never enforces (budget_usd is None). Hook for later phases.
        return self.budget_usd is not None and self.total_usd() > self.budget_usd

    def log(self) -> None:
        try:
            cats = {k: v["count"] for k, v in self._entries.items()}
            print(
                f"[premium-cost] job={self.job_id} total=${self.total_usd():.4f} "
                f"categories={cats} (track-only, no enforcement)",
                flush=True,
            )
        except Exception:
            pass


class PremiumContext:
    """Carries premium routing state through a job + owns the lazily-created
    premium asset pool. Phase 1: holds state; the pool is DEFINED here but
    instantiated only by the first premium stage (Phase E), so base/empty jobs
    never create it. Constructing this context spawns NO threads."""

    def __init__(self, is_premium: bool, route_premium: bool, cost_meter: Optional[CostMeter] = None):
        self.is_premium = is_premium
        self.route_premium = route_premium
        self.cost_meter = cost_meter
        self._asset_pool = None  # lazy — see asset_pool(); never created in Phase 1

    def asset_pool(self, max_workers: int = 5):
        """The dedicated premium parallel-asset lane, kept OFF the saturated
        mega_pool (handler.py:18571). Created on first access only — Phase 1
        never calls this. Mirrors the b-roll fetch pool (handler.py:18710)."""
        if self._asset_pool is None:
            self._asset_pool = concurrent.futures.ThreadPoolExecutor(
                max_workers=max_workers, thread_name_prefix="premium-asset",
            )
            print(f"[premium] asset pool created (max_workers={max_workers})", flush=True)
        return self._asset_pool

    def shutdown(self) -> None:
        """Tear down the asset pool if a stage created it. No-op in Phase 1."""
        if self._asset_pool is not None:
            try:
                self._asset_pool.shutdown(wait=False)
            except Exception:
                pass
            self._asset_pool = None
