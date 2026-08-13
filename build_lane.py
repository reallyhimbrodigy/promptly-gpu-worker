#!/usr/bin/env python3
"""Mark this container as the BUILD LANE `[§3.1/§6.1]`.

The EDITORIAL_LIVE gate suppresses editorial model calls for LIVE TRAFFIC by
default, so restoring Vertex billing costs zero additional live spend. The
harness, the cert apps and the Lumen build loop must be unaffected — building
Lumen is the entire point of having the brain available at all.

They run in their OWN Modal containers, so the marker is set THERE and can never
reach production. Import and call at the top of any container function that
legitimately needs the model:

    from build_lane import mark_build_lane
    mark_build_lane()

WHY A FUNCTION AND NOT AN IMAGE ENV: production and the cert apps share the
worker image, so setting it at image level would open the gate for live traffic
— which is exactly the thing being prevented. It has to be per-container, in the
function body, where only build code runs.

PROMPTLY_BUILD_LANE must NEVER appear in the promptly-lang-flags secret. The
NO-UNREGISTERED-LIVE-FLAG deploy check fails on any live PROMPTLY_* key that is
not registered, so an attempt to set it there is caught at the gate.
"""
import os

_MARKER = "PROMPTLY_BUILD_LANE"


def mark_build_lane(reason=""):
    """Idempotent. Returns True if this container is now marked."""
    os.environ[_MARKER] = "1"
    print(f"[build-lane] editorial calls ENABLED for this container"
          f"{(' — ' + reason) if reason else ''}", flush=True)
    return True


def is_build_lane():
    return os.environ.get(_MARKER, "").strip().lower() in ("1", "true", "yes", "on")
