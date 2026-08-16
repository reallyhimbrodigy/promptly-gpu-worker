#!/usr/bin/env python3
"""THE INSTALLED SET IS A REVIEWED ARTEFACT, NOT A RESOLVER'S OPINION `[Rule 1]`.

WHY THIS EXISTS, and it cost 33 users fifteen minutes each.

On 2026-08-15 a one-line change — `supabase>=2,<3` -> `supabase==2.7.4` — took
the entire editorial path down for eleven hours. Not because the pin was wrong,
but because **Modal's `.pip_install()` layers resolve INDEPENDENTLY**. There is
no co-resolution, so a later layer silently downgrades an earlier one and NOBODY
REVIEWS THE RESULT. What actually happened, proven from PyPI metadata:

    supabase==2.7.4      requires  httpx<0.28,>=0.24
    google-genai>=1.3.0  requires  httpx<1.0.0,>=0.28.1

Mutually exclusive. Every google-genai release from 1.3.0 on carries that httpx
floor, so **1.2.0 is the ONLY version compatible with the pin** — pip did not
merely permit it, the pin mathematically forced it, 73 minor versions back. And
1.2.0 predates `VideoMetadata.fps`, so `generate_edit_gemini` raised on every
job before it ever reached the editorial gate.

The diff that caused it was ONE LINE and named ONE package. The damage was in a
package nobody typed. That is the whole class: **the thing that breaks you is
never the thing you edited.**

So the installed set becomes a committed, reviewed artefact. Any package that
moves without a corresponding change to `INSTALLED_SET.txt` is drift, and drift
is reported LOUDLY within seconds of a deploy instead of being discovered eleven
hours later by reading failure rates.

WHY POST-DEPLOY AND NOT PRE. The image does not exist until Modal builds it, so
there is nothing to freeze beforehand. This runs against the RUNNING image and
is honest about that: it is a smoke alarm, not a door lock. Catching drift 30
seconds after a deploy instead of 11 hours after is the entire win.

IT NEVER FAILS SILENTLY. If it cannot reach a container it says so and exits 2 —
"I could not measure" is reported as its own state, never as "no drift"
[the PROBE COLLAPSE class].

    python3 installed_set_diff.py            # diff live image vs INSTALLED_SET.txt
    python3 installed_set_diff.py --update   # accept current as the new baseline
"""
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASELINE = os.path.join(HERE, "INSTALLED_SET.txt")
APP = "promptly-gpu-worker"


def _live_container():
    """A running container of the worker app, or None."""
    r = subprocess.run(["modal", "container", "list", "--json"],
                       capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        return None
    try:
        rows = json.loads(r.stdout or "[]")
    except Exception:
        return None
    for c in rows:
        if APP in str(c.get("App Name", "")):
            cid = c.get("Container ID")
            if cid:
                return cid
    return None


def _freeze(container_id):
    r = subprocess.run(
        ["modal", "container", "exec", container_id, "--",
         "python", "-m", "pip", "list", "--format=freeze"],
        capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        return None
    out = {}
    for line in (r.stdout or "").splitlines():
        line = line.strip()
        if "==" in line and not line.startswith(("#", "PYTHON", "Usage")):
            name, _, ver = line.partition("==")
            out[name.strip().lower().replace("_", "-")] = ver.strip()
    return out or None


def _load_baseline():
    if not os.path.exists(BASELINE):
        return None
    out = {}
    for line in open(BASELINE, encoding="utf-8"):
        line = line.strip()
        if "==" in line:
            name, _, ver = line.partition("==")
            out[name.strip().lower().replace("_", "-")] = ver.strip()
    return out


def _declared_specs():
    """Every pip spec declared in modal_app.py's image, across ALL layers.

    Bracket-matched rather than line-matched: the specs sit in several
    `.pip_install(...)` calls, and a naive regex caught only the first, which is
    exactly the blind spot that let the layers diverge unnoticed.
    """
    out = []
    src = open(os.path.join(HERE, "modal_app.py"), encoding="utf-8").read()
    for m in re.finditer(r"\.pip_install\(", src):
        i = m.end() - 1
        depth = 0
        for j in range(i, len(src)):
            if src[j] == "(":
                depth += 1
            elif src[j] == ")":
                depth -= 1
                if depth == 0:
                    break
        blk = re.sub(r"#[^\n]*", "", src[i:j + 1])
        out += [s for s in re.findall(r'"([A-Za-z0-9_.\-\[\]]+[^"]*)"', blk)
                if not s.startswith(("-", "http"))]
    return sorted(set(out))


def _vkey(v):
    """PEP440-lite sort key. Vendored deliberately: `packaging` is NOT in the
    deploy host's python, and a ceiling check that reports NOT MEASURED on every
    real deploy is a check that does not exist. These specs are all plain numeric
    ranges, so a numeric tuple is sufficient and has no install step."""
    core = re.split(r"[+-]", str(v).strip())[0]
    parts = []
    for chunk in core.split("."):
        m = re.match(r"^(\d+)", chunk)
        parts.append(int(m.group(1)) if m else 0)
    return tuple(parts + [0] * (6 - len(parts)))[:6]


def _is_prerelease(v):
    return bool(re.search(r"(a|b|rc|dev|alpha|beta)\d*$", str(v).strip(), re.I))


def _satisfies(v, rng):
    """Does version v satisfy a comma-separated spec like '>=1.0,<2'?"""
    if not rng:
        return True
    for clause in rng.split(","):
        clause = clause.strip()
        m = re.match(r"^(==|!=|>=|<=|>|<|~=)\s*(.+)$", clause)
        if not m:
            continue
        op, target = m.group(1), m.group(2).strip()
        a, b = _vkey(v), _vkey(target)
        if op == "==" and not (a == b or str(v).strip() == target):
            return False
        if op == "!=" and a == b:
            return False
        if op == ">=" and not a >= b:
            return False
        if op == "<=" and not a <= b:
            return False
        if op == ">" and not a > b:
            return False
        if op == "<" and not a < b:
            return False
        if op == "~=" and not (a >= b and a[:len(b) - 1] == b[:len(b) - 1]):
            return False
    return True


def _below_ceiling(live):
    """Packages installed BELOW what their own declared spec allows.

    THE BASELINE CANNOT BE THE ONLY TRUTH. INSTALLED_SET.txt was first captured
    DURING the incident, so it happily enshrined google-genai==1.2.0 — the very
    version that took editorial down — as "correct", and a baseline-only diff
    would report NO DRIFT forever while the wrong library ran. A frozen snapshot
    proves nothing about whether the snapshot was right.

    So this leg asks a different question: does what is INSTALLED match what we
    DECLARED we wanted? google-genai>=1.0,<2 resolving to 1.2.0 while 1.75.0
    satisfies the same spec is 73 minor versions of silent loss, and it is
    visible ONLY from the spec, never from the baseline.

    Returns (rows, measured). measured=False when PyPI is unreachable — an
    unmeasurable state is reported as itself, never as "nothing below ceiling".
    """
    from urllib.request import urlopen
    rows = []
    for spec in _declared_specs():
        m = re.match(r"^([A-Za-z0-9_.\-]+)(\[[^\]]*\])?(.*)$", spec)
        if not m:
            continue
        name = m.group(1).lower().replace("_", "-")
        rng = (m.group(3) or "").strip()
        inst = live.get(name)
        if not inst:
            continue
        try:
            with urlopen(f"https://pypi.org/pypi/{name}/json", timeout=30) as r:
                data = json.loads(r.read().decode())
            allowed = [v for v in data.get("releases", {})
                       if not _is_prerelease(v) and _satisfies(v, rng)]
            if not allowed:
                continue
            top = max(allowed, key=_vkey)
            if _vkey(inst) < _vkey(top):
                rows.append((name, inst, str(top), spec))
        except Exception:
            return rows, False
    return rows, True


def main(argv):
    cid = _live_container()
    if not cid:
        print("[installed-set] NO RUNNING CONTAINER for "
              f"{APP} — cannot read the live image.")
        print("[installed-set] THIS IS A FAILED MEASUREMENT, NOT A CLEAN DIFF. "
              "Re-run once a container is warm (any real job warms one).")
        return 2
    live = _freeze(cid)
    if not live:
        print(f"[installed-set] pip list FAILED inside {cid} — FAILED MEASUREMENT, "
              "not a clean diff.")
        return 2

    if "--update" in argv:
        with open(BASELINE, "w", encoding="utf-8") as f:
            for k in sorted(live):
                f.write(f"{k}=={live[k]}\n")
        print(f"[installed-set] baseline UPDATED from the live image: "
              f"{len(live)} packages -> {BASELINE}")
        print("[installed-set] COMMIT IT. An un-committed baseline reviews nothing.")
        return 0

    base = _load_baseline()
    if base is None:
        print(f"[installed-set] no baseline at {BASELINE} — run with --update once, "
              "then commit it.")
        return 2

    added = sorted(set(live) - set(base))
    removed = sorted(set(base) - set(live))
    moved = sorted(k for k in (set(live) & set(base)) if live[k] != base[k])

    print(f"[installed-set] live image {cid}: {len(live)} packages | "
          f"baseline: {len(base)}")

    # LEG 2 — DECLARED-SPEC COMPARISON. Runs ALWAYS, including when the baseline
    # matches, because a baseline captured during an incident enshrines the
    # incident: INSTALLED_SET.txt was first frozen while google-genai==1.2.0 was
    # live, so a baseline-only diff would say NO DRIFT forever while the very
    # library that caused the outage kept running.
    ceil_rows, measured = _below_ceiling(live)
    if not measured:
        print("[installed-set] ceiling check NOT MEASURED (PyPI unreachable or "
              "`packaging` missing) — reported as its own state, not as a pass.")
    elif ceil_rows:
        print(f"\n[installed-set] !! {len(ceil_rows)} package(s) INSTALLED BELOW "
              "THEIR OWN DECLARED SPEC — a sibling layer pushed them down:")
        for name, inst, top, spec in ceil_rows:
            print(f"   BELOW CEILING  {name:26} running {inst:14} spec '{spec}' "
                  f"allows up to {top}")
        print("   google-genay 1.2.0 vs 1.75.0 was this exact shape, and it cost "
              "11 hours across 33 users.".replace("google-genay", "google-genai"))
    else:
        print("[installed-set] ceiling check: every declared package is at the top "
              "of its own spec.")

    if not (added or removed or moved):
        print(f"[installed-set] NO BASELINE DRIFT — all {len(base)} packages match "
              "the reviewed baseline.")
        return 1 if (measured and ceil_rows) else 0

    print("\n[installed-set] !! DEPENDENCY DRIFT — packages moved that NO DIFF NAMED.")
    print("   This is the class that took editorial down for 11 hours on 2026-08-16:")
    print("   a one-line pin on `supabase` forced google-genai 73 versions back,")
    print("   because Modal's pip_install layers resolve INDEPENDENTLY.\n")
    for k in moved:
        print(f"   MOVED    {k:34} {base[k]:16} -> {live[k]}")
    for k in added:
        print(f"   ADDED    {k:34} {'-':16} -> {live[k]}")
    for k in removed:
        print(f"   REMOVED  {k:34} {base[k]:16} -> (gone)")
    print(f"\n   {len(moved)} moved, {len(added)} added, {len(removed)} removed, "
          f"{len(ceil_rows)} below their declared ceiling.")
    print("   If this is INTENDED: python3 installed_set_diff.py --update && commit.")
    print("   If it is NOT: you have just found your next incident before it "
          "found your users.")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
