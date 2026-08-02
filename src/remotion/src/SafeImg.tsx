import React, { useEffect, useState } from "react";
import { Img, delayRender, continueRender } from "remotion";

/**
 * SafeImg — A FAILED IMAGE DEGRADES TO NO IMAGE, NEVER TO A DEAD RENDER.
 * (Zac 2026-08-02, forged from job 1047def9.)
 *
 * THE FAILURE. One unresolved image fetch inside Chromium killed a user's whole
 * video:
 *   [micro-02] Remotion render failed (rc=1) in 72.6s: Error: Timeout (30000ms)
 *   exceeded rendering the component at frame 134. Open delayRender() handles:
 *     "1. Loading <Img> with src=blob:http://localhost:3005/c8b8d026-..."
 *     "2. Loading <Img> with src=blob:http://localhost:3005/46..."
 * Two handles, and CrossfadeZoom mounts exactly two MediaLayers. Job b8ab1276 is
 * the same shape on the overlay leg (PromptlyOverlay, 8 MGs, rc=1 at rendered=0).
 * The common factor is assets not loading inside Chromium — not the asset, not
 * the component, not the decoration (it survives decoration-stripping).
 *
 * WHY WRAPPING <Img> IS NOT ENOUGH. Remotion's <Img> opens its OWN delayRender
 * handle internally the moment it mounts. A wrapper cannot continueRender that
 * handle, so a wrapper still hangs. The only way to make the class impossible is
 * to never mount <Img> with a src we have not already proven loads:
 *
 *   1. Open ONE handle of our own, with an EXPLICIT timeout well under the
 *      render's 30s ceiling, so we always lose the race and degrade first.
 *   2. Probe the URL with a plain Image() off the Remotion tree.
 *   3. onload  -> render <Img> (the browser cache makes its internal handle
 *      resolve immediately).
 *      onerror / timeout -> render the fallback (default: nothing) and
 *      continueRender, so the frame completes WITHOUT the asset.
 *
 * The result: an unreachable image costs its own pixels and nothing else. It can
 * no longer cost the video. This holds regardless of WHY the fetch failed —
 * blob: URL, CDN 403, DNS, a slow cold cache — which is the point.
 */

/**
 * Must stay comfortably under the renderer's per-frame timeout (30000ms) so the
 * degrade always wins the race. Raising this past the render timeout re-arms the
 * exact bug this component exists to kill.
 */
export const SAFE_IMG_TIMEOUT_MS = 8000;

type SafeImgProps = Omit<React.ComponentProps<typeof Img>, "src"> & {
  src: string | undefined | null;
  /** Drawn when the image cannot be loaded. Default: nothing at all. */
  fallback?: React.ReactNode;
};

export const SafeImg: React.FC<SafeImgProps> = ({ src, fallback = null, ...rest }) => {
  const [state, setState] = useState<"probing" | "ok" | "failed">("probing");
  // One handle per mount. delayRender's own timeout is a backstop; the explicit
  // timer below is what normally fires, so we degrade rather than throw.
  const [handle] = useState(() =>
    delayRender(`SafeImg probing ${String(src).slice(0, 80)}`, {
      timeoutInMilliseconds: SAFE_IMG_TIMEOUT_MS + 4000,
    }),
  );

  useEffect(() => {
    let settled = false;
    const finish = (next: "ok" | "failed") => {
      if (settled) return;
      settled = true;
      setState(next);
      continueRender(handle);
    };

    if (!src) {
      finish("failed");
      return;
    }

    const timer = setTimeout(() => finish("failed"), SAFE_IMG_TIMEOUT_MS);
    const probe = new Image();
    probe.onload = () => {
      clearTimeout(timer);
      finish("ok");
    };
    probe.onerror = () => {
      clearTimeout(timer);
      finish("failed");
    };
    probe.src = src;

    return () => {
      clearTimeout(timer);
      // Never leave the handle open on unmount — an orphaned handle is the same
      // hang by another route.
      finish("failed");
    };
  }, [src, handle]);

  if (state === "probing") return null;
  if (state === "failed" || !src) return <>{fallback}</>;
  return <Img src={src} {...rest} />;
};
