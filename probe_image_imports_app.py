#!/usr/bin/env python3
"""Does the app IMPORT inside its own image? The cheapest true test there is.

Round 55 launched five arms that all died at container start on a decorator
whose package was not in the image. Every local check passed because modal is
a stub on the laptop. This runs `import agentic_editor_app` IN THE IMAGE and
returns what happened — ~$0.01, before a round spends five jobs finding out.
"""
import modal

from agentic_editor_app import IMG as _IMG                        # noqa: E402

image = _IMG.add_local_file("agentic_editor_app.py",
                            "/root/agentic_editor_app.py", copy=True)
app = modal.App("promptly-image-import-probe")


@app.function(image=image, cpu=2, memory=4096, timeout=600)
def try_import() -> dict:
    import importlib
    import time
    import traceback
    t0 = time.time()
    try:
        m = importlib.import_module("agentic_editor_app")
        names = [n for n in ("edit", "render_remotion_batch", "extract_beat_frames",
                             "delivery_fps", "cutaway_plan") if hasattr(m, n)]
        return {"state": "IMPORTED", "wall_s": round(time.time() - t0, 1),
                "names": names}
    except Exception:                                             # noqa: BLE001
        return {"state": "FAILED", "wall_s": round(time.time() - t0, 1),
                "trace": traceback.format_exc()[-800:]}


@app.local_entrypoint()
def main():
    print("PRICE STATED: one cpu=2 container for the import, plus the image "
          "layer build for the new pip_install. ~$0.01-0.05.")
    r = try_import.remote()
    print(f"  {r['state']}  wall={r['wall_s']}s  {r.get('names') or ''}")
    if r["state"] != "IMPORTED":
        print(r.get("trace"))
