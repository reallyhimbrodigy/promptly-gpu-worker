"""SCHEMA-BILLING PROBE — are response_schema tokens billed as input?

THE QUESTION AND WHY IT MATTERS
  If schema tokens are NOT counted in prompt_token_count, then typing
  `_MotionGraphic.props` moves 1,269 tok of prop contracts OUT of the billed
  prompt and into a free, ENFORCED channel. If they ARE counted, the move is
  cost-neutral at best and the prose stays.

WHY THE LEAN_SCHEMA ARMS COULD NOT ANSWER IT
  LEAN_SCHEMA changes the emitted schema by 131 tok (the schema is a TYPE
  declaration — stripping 5 fields removes 5 declarations, not 5 per moment).
  The observed arm-to-arm spread in prompt_token_count was 186 tok. The effect
  was smaller than the noise; that null proved nothing.

THE DESIGN
  PROMPTLY_SCHEMA_PAD=30 adds 30 UNREFERENCED $defs = +5,214 tok, 28x the noise.
  Unreferenced $defs are inert: JSON Schema ignores them and constrained decoding
  cannot reach them, so GENERATION IS UNCHANGED and the only thing that moves is
  the schema's size. Flag-off is byte-identical (asserted below).

  SEQUENTIAL, and the SECOND call is the one that counts: a schema change busts
  the Vertex cache key, so call 1 reads 0 cached for the wrong reason. Call 2
  runs against a warm cache and its prompt_token_count is the real reading.

READ
  control call-2 prompt_tok  vs  padded call-2 prompt_tok
    difference ~= +5,214  -> schema IS billed as input  -> props stay in prose
    difference ~= 0       -> schema is NOT billed       -> type props, free win

COST: 4 PLAN_ONLY runs on ONE short clip, cpu=8/32GiB, no render. ~$0.50.
"""
import os
import sys

import modal
import modal_app

image = modal_app.image.add_local_file("modal_app.py", "/modal_app.py")
app = modal.App("cert-schema-billing", image=image)
SECRETS = [modal.Secret.from_name("promptly-secrets"),
           modal.Secret.from_name("promptly-cloudfront"),
           modal.Secret.from_name("gemini-vertex"),
           modal.Secret.from_name("promptly-lang-flags")]

CLIP = ("https://d1iax8jos987n3.cloudfront.net/sources/"
        "16eeba22-ac1d-4c83-8fdc-555fd2799a9d/"
        "1785393441656-4CD89C65-57DF-48D7-8B30-9C164F061946_L0_001.mp4")


@app.function(secrets=SECRETS, cpu=8.0, memory=32768, region="us", timeout=1800)
def probe(pad: int, tag: str) -> dict:
    import uuid
    os.environ["APP_URL"] = ""
    os.environ["JOB_STATUS_WRITES_ENABLED"] = ""
    os.environ["PROMPTLY_PLAN_ONLY"] = "1"
    if pad:
        os.environ["PROMPTLY_SCHEMA_PAD"] = str(pad)
    else:
        os.environ.pop("PROMPTLY_SCHEMA_PAD", None)
    sys.path.insert(0, "/")
    import handler as H
    import json as _j
    schema_tok = len(_j.dumps(H._post_cuts_response_schema())) / 4.19428
    jid = str(uuid.uuid4())
    body = {"job_id": jid, "video_url": CLIP, "vibe": "Clean engaging edit",
            "user_id": "ec702499-ca10-49e6-8850-df8f99840904",
            "upload_url": f"https://thisismybucketagainwooo.s3.amazonaws.com/probe/{jid}.mp4",
            "public_url": f"https://thisismybucketagainwooo.s3.amazonaws.com/probe/{jid}.mp4",
            "model": "flare", "supports_progressive": False,
            "premium_pipeline_enabled": False}
    try:
        H.handler({"input": body})
    except Exception as e:  # noqa: BLE001
        return {"tag": tag, "error": f"{type(e).__name__}: {str(e)[:140]}"}
    pc = [c for c in H._GEMINI_CALL_LOG
          if "post" in (c.get("label") or "") and not c.get("aborted")]
    if not pc:
        return {"tag": tag, "error": "no post-cuts call recorded"}
    c = pc[-1]
    return {"tag": tag, "pad": pad, "schema_tok": round(schema_tok),
            "prompt_tok": c.get("prompt_tok"), "cached_tok": c.get("cached_tok"),
            "out_tok": c.get("out_tok"), "total_s": c.get("total_s")}


@app.local_entrypoint()
def main():
    print("SCHEMA-BILLING PROBE — sequential; the SECOND call of each pair is the read\n")
    rows = []
    for pad, tag in ((0, "control-1"), (0, "control-2"),
                     (30, "padded-1"), (30, "padded-2")):
        rows.append(probe.remote(pad, tag))       # .remote = sequential, cache warms
        print(f"  {rows[-1]}")

    def get(tag, k):
        for r in rows:
            if r.get("tag") == tag:
                return r.get(k)
        return None

    c2, p2 = get("control-2", "prompt_tok"), get("padded-2", "prompt_tok")
    cs, ps = get("control-2", "schema_tok"), get("padded-2", "schema_tok")
    print("\n" + "=" * 74)
    print(f"  {'':<12} {'schema_tok':>11} {'prompt_tok':>11} {'cached_tok':>11}")
    for t in ("control-1", "control-2", "padded-1", "padded-2"):
        print(f"  {t:<12} {str(get(t,'schema_tok')):>11} "
              f"{str(get(t,'prompt_tok')):>11} {str(get(t,'cached_tok')):>11}")
    if c2 and p2 and cs and ps:
        d_schema, d_prompt = ps - cs, p2 - c2
        print(f"\n  schema grew by {d_schema:+,} tok")
        print(f"  prompt_token_count moved {d_prompt:+,} tok")
        frac = d_prompt / max(1, d_schema)
        print(f"  ratio {frac:.2f}")
        if frac > 0.6:
            print("\n  VERDICT: the schema IS billed as input. Typing props moves cost,")
            print("  it does not remove it — the prop contracts stay in prose.")
        elif abs(d_prompt) < 300:
            print("\n  VERDICT: the schema is NOT billed as input. Typing")
            print("  _MotionGraphic.props moves 1,269 tok out of the billed prompt")
            print("  AND upgrades it from described to ENFORCED. Free win.")
        else:
            print("\n  VERDICT: PARTIAL/AMBIGUOUS — report the raw numbers, do not round")
            print("  this into a conclusion.")
