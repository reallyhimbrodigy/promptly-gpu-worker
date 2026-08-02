import React, { useEffect, useState } from "react";
import { Img, delayRender, continueRender, cancelRender } from "remotion";

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
 * THE POLICY IS SPLIT BY ROLE, and this is load-bearing. "Degrade to nothing" is
 * only correct for DECORATION. CrossfadeZoom's clipA/clipB are PRIMARY MEDIA —
 * they ARE the frame — so degrading them to nothing renders an EMPTY segment,
 * i.e. a black hole, i.e. exactly what INTEGRITY_TRIP fires on. That would trade
 * a render hang for a black segment that SHIPS, which is strictly worse.
 *   role="decoration" — avatars, bubbles, MG art, generated-scene subjects.
 *                       Failure draws nothing and the video ships.
 *   role="primary"    — the frame itself. Failure cancels the render LOUDLY with
 *                       a coded error, because an honest failure beats a black
 *                       video delivered to a user.
 * `role` is REQUIRED: a new <SafeImg> site must state which it is, so this
 * decision can never be made by defaulting.
 *
 * The result: an unreachable DECORATION costs its own pixels and nothing else,
 * and an unreachable PRIMARY fails as a named error instead of as black. This
 * holds regardless of WHY the fetch failed — blob: URL, CDN 403, DNS, a slow
 * cold cache — which is the point.
 *
 * TELEMETRY. The Remotion layer emits no telemetry of its own — every divergence
 * and error code in this pipeline comes from Python — so a quiet degrade here is
 * invisible by construction. Every outcome logs a grep-stable `[SAFEIMG]` line
 * that the worker captures from the browser console, so the degrade RATE is
 * countable on real traffic instead of assumed to be zero.
 */

/**
 * Must stay comfortably under the renderer's per-frame timeout (30000ms) so the
 * degrade always wins the race. Raising this past the render timeout re-arms the
 * exact bug this component exists to kill.
 */
export const SAFE_IMG_TIMEOUT_MS = 8000;

export type SafeImgRole = "decoration" | "primary";

type SafeImgProps = Omit<React.ComponentProps<typeof Img>, "src"> & {
  src: string | undefined | null;
  /** REQUIRED. "decoration" degrades to nothing; "primary" fails loudly. */
  role: SafeImgRole;
  /** Drawn when a DECORATION cannot be loaded. Default: nothing at all. */
  fallback?: React.ReactNode;
  /** Identifies the site in the [SAFEIMG] telemetry line. */
  label?: string;
  /**
   * PRIMARY media only. Supply this when the PARENT can still render a sensible
   * frame without this asset (e.g. a crossfade holding its other layer). Given
   * one, SafeImg reports the loss and draws nothing, and the parent compensates
   * — the user gets a slightly wrong shot instead of no video. WITHOUT one,
   * primary failure cancels the render, because nothing else can cover the frame
   * and the only alternative is shipping black.
   */
  onUnavailable?: () => void;
};

export const SafeImg: React.FC<SafeImgProps> = ({
  src,
  role,
  fallback = null,
  label,
  onUnavailable,
  ...rest
}) => {
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
    const site = label || "unlabelled";
    const finish = (next: "ok" | "failed", reason: string) => {
      if (settled) return;
      settled = true;
      // Grep-stable, one line per outcome. Python counts these off the worker log.
      // eslint-disable-next-line no-console
      console.log(
        `[SAFEIMG] ${next === "ok" ? "loaded" : "degraded"} role=${role} `
        + `site=${site} reason=${reason} src=${String(src).slice(0, 120)}`,
      );
      if (next === "failed" && role === "primary") {
        if (onUnavailable) {
          // The parent can still paint this frame without us. Hand it over and
          // draw nothing — a slightly wrong shot beats no video at all.
          setState("failed");
          continueRender(handle);
          onUnavailable();
          return;
        }
        // Nothing can cover this frame. Degrading to nothing would ship BLACK,
        // so fail named instead.
        continueRender(handle);
        cancelRender(
          new Error(
            `SAFE_IMG_PRIMARY_UNLOADABLE: site=${site} reason=${reason} `
            + `src=${String(src).slice(0, 200)}`,
          ),
        );
        return;
      }
      setState(next);
      continueRender(handle);
    };

    if (!src) {
      finish("failed", "no-src");
      return;
    }

    const timer = setTimeout(() => finish("failed", "timeout"), SAFE_IMG_TIMEOUT_MS);
    const probe = new Image();
    probe.onload = () => {
      clearTimeout(timer);
      finish("ok", "ok");
    };
    probe.onerror = () => {
      clearTimeout(timer);
      finish("failed", "error");
    };
    probe.src = src;

    return () => {
      clearTimeout(timer);
      // Never leave the handle open on unmount — an orphaned handle is the same
      // hang by another route. But an ordinary unmount is NOT an asset failure:
      // routing it through finish() would cancelRender a healthy render whenever
      // a primary layer unmounted mid-probe. Release the handle and say nothing.
      if (!settled) {
        settled = true;
        continueRender(handle);
      }
    };
  }, [src, handle, role, label, onUnavailable]);

  if (state === "probing") return null;
  if (state === "failed" || !src) return <>{fallback}</>;
  return <Img src={src} {...rest} />;
};
