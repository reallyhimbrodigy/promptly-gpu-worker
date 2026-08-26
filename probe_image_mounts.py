"""Rule 0, half two: are the modules PRESENT in the image the worker runs?

`modal app history` proves WHICH COMMIT deployed. It does not prove the image
carries the files that commit added — a mount line can be missing, or a module
can be committed and never mounted, and the SHA looks identical either way.
This asks the image.

EXISTENCE ONLY, deliberately. An import can fail for reasons that have nothing
to do with presence (a missing secret, an optional dep), and presence is the
question being asked. Three earlier attempts at this died on
`ModuleNotFoundError: No module named 'modal_app'` because the probe lived in a
scratch directory — the file has to sit beside the module it imports.

    modal run probe_image_mounts.py
"""
import sys

sys.path.insert(0, "/")
import modal, modal_app                                            # noqa: E402

# modal_app.py must be mounted EXPLICITLY: the worker image does not contain the
# app-definition module (Modal auto-mounts it for the deployed app, not for an
# ephemeral one built from its image). Three attempts died on
# `ModuleNotFoundError: No module named 'modal_app'` before I read the error
# instead of theorising about it; cert_e1_ab_app.py has always added this line.
image = modal_app.image.add_local_file("modal_app.py", "/modal_app.py")
app = modal.App("cert-image-mount-probe", image=image)

MODULES = ("prompt_v2_editor", "prompt_v2_schema", "prompt_v2_exemplars",
           "duration_target", "mechanical_router", "surgical_ops", "handler")


@app.function()
def probe():
    import os
    out = {}
    for m in MODULES:
        p = f"/{m}.py"
        out[m] = f"{os.path.getsize(p)}b" if os.path.exists(p) else "ABSENT"
    return out


@app.local_entrypoint()
def main():
    r = probe.remote()
    for k in MODULES:
        print(f"  {k:22} {r.get(k)}")
