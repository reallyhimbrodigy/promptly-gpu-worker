#!/usr/bin/env python3
"""COUNT THE PREFIX. Anthropic's own tokeniser, not chars/4.

Every prefix claim in this lane has been made in tokens, and chars/4 is wrong
by enough to matter on a block this size — and wrong by an unknown amount on
images, where the rule is pixels/750 before an undisclosed rescale. This calls
`messages.count_tokens`, which is the number the bill is computed from.

Text and images go in the same call because that is how they are sent: the
image blocks ride the first user message, inside the cached prefix.
"""
import modal

app = modal.App("promptly-prefix-cost")
image = modal.Image.debian_slim(python_version="3.11").pip_install("anthropic")


@app.function(image=image, timeout=600,
              secrets=[modal.Secret.from_name("anthropic-api-key")])
def count(system_text: str, images: list = None,
          model: str = "claude-sonnet-4-5-20250929") -> dict:
    """{'state','input_tokens',...}. An error is a STATE, never a zero."""
    import base64
    import os
    import time
    t0 = time.time()
    try:
        import anthropic
        c = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        blocks = []
        for b in (images or []):
            blocks.append({"type": "image",
                           "source": {"type": "base64", "media_type": "image/png",
                                      "data": base64.b64encode(b).decode()}})
        blocks.append({"type": "text", "text": "x"})
        r = c.messages.count_tokens(
            model=model,
            system=[{"type": "text", "text": system_text}] if system_text else [],
            messages=[{"role": "user", "content": blocks}])
        return {"state": "MEASURED", "input_tokens": r.input_tokens,
                "n_images": len(images or []), "sys_chars": len(system_text or ""),
                "model": model, "wall_s": round(time.time() - t0, 1)}
    except Exception as e:                                        # noqa: BLE001
        return {"state": "FAILED", "detail": "%s: %s" % (type(e).__name__,
                                                         str(e)[:300]),
                "wall_s": round(time.time() - t0, 1)}
