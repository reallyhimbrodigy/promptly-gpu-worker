"""DOES THE MODEL ACTUALLY RECEIVE THE STILLS? — before a single cell is spent.

`exemplar_block("FRAMES_PLAN")` has always emitted "Stills from each reference
are attached" while NOTHING attached them. Running the frame-grab arm on that
would produce a number about a prompt that referenced absent images — the
fifth unreadable scenes run in a row, and the most expensive kind, because it
would look like a real result.

THIS IS A THREE-WAY DIAGNOSTIC, which is why it is worth its own call:

  the model describes GRAPHICS / TYPE   attachment works AND my selector picked
                                        real insert scenes
  the model describes A PERSON TALKING  attachment works, SELECTOR IS WRONG —
                                        the stills teach the wrong thing
  the model describes NOTHING / refuses ATTACHMENT IS BROKEN

I cannot see the images. The selector (flat ground + real type, since cv2 and
/models/face_detector are container-only) is a heuristic, and this is the only
way I have to audit it before spending on the arm.

COST: one call, a handful of images, ~$0.01-0.02.

    modal run probe_frames_received_app.py
"""
import os
import sys

sys.path.insert(0, "/")
import modal, modal_app                                            # noqa: E402

_stills = [f for f in sorted(os.listdir("reference_stills"))
           if f.endswith(".jpg")] if os.path.isdir("reference_stills") else []
image = modal_app.image.add_local_file("modal_app.py", "/modal_app.py")
for _f in _stills:
    image = image.add_local_file(f"reference_stills/{_f}", f"/stills/{_f}")

app = modal.App("cert-frames-received", image=image)
SECRETS = [modal.Secret.from_name("promptly-secrets"),
           modal.Secret.from_name("gemini-vertex")]


@app.function(secrets=SECRETS, cpu=2.0, memory=4096, timeout=600)
def probe(names: list) -> dict:
    sys.path.insert(0, "/")
    import handler as H
    from google.genai import types as genai_types

    client = H._get_genai_client()
    parts = []
    for n in names:
        with open(f"/stills/{n}", "rb") as fh:
            parts.append(genai_types.Part.from_bytes(data=fh.read(),
                                                     mime_type="image/jpeg"))
    ask = (
        "You are being shown still frames taken from two finished short-form "
        "video edits. For EACH image in order, answer in ONE line:\n"
        "  <index>: <what is on screen> | FULL_FRAME_GRAPHIC or TALKING_HEAD "
        "or OTHER\n"
        "Be literal. If an image did not arrive, say MISSING for that index."
    )
    resp = client.models.generate_content(
        model=H.GEMINI_EDITORIAL_MODEL,
        contents=[*parts, ask],
        config=genai_types.GenerateContentConfig(temperature=0.0),
    )
    txt = (getattr(resp, "text", "") or "").strip()
    return {"n_sent": len(parts), "names": names, "reply": txt}


@app.local_entrypoint()
def main():
    names = [f for f in sorted(os.listdir("reference_stills")) if f.endswith(".jpg")]
    if not names:
        print("  no stills — run build_reference_stills.py first")
        return
    r = probe.remote(names)
    print(f"\n  SENT {r['n_sent']} stills: {', '.join(r['names'])}")
    print("  ── the model's own description ──")
    for line in (r["reply"] or "").splitlines():
        print(f"    {line}")
    low = (r["reply"] or "").lower()
    n_graphic = low.count("full_frame_graphic")
    n_head = low.count("talking_head")
    n_missing = low.count("missing")
    print(f"\n  graphics={n_graphic}  talking_heads={n_head}  missing={n_missing}")
    if n_missing or not r["reply"]:
        print("  VERDICT: ATTACHMENT IS BROKEN — do not run the arm.")
    elif n_graphic == 0:
        print("  VERDICT: attachment works, but the SELECTOR IS WRONG — these "
              "stills show no insert scenes, so FRAMES_PLAN would teach the "
              "wrong thing. Fix selection before spending on the arm.")
    else:
        print(f"  VERDICT: attachment works and {n_graphic} still(s) show a "
              f"full-frame graphic — FRAMES_PLAN has a real stimulus.")
