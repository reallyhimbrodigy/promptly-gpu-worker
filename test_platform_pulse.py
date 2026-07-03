"""Pre-freeze F2: platform style pulse — rolling last-50 vocab frequency →
ONE fail-open USER-content nudge line; the system prompt may not move a byte."""
import contextlib
import io
import os
from types import SimpleNamespace

import handler as H

PASS, FAIL = [], []
def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"   :: {detail}" if (detail and not cond) else ""))


VERBATIM_TAIL = "— when the footage's register allows, reach for a different garment."


class FakeQuery:
    def __init__(self, owner, rows, boom):
        self._owner, self._rows, self._boom = owner, rows, boom
    def select(self, arg):
        self._owner.calls["select"] = arg
        return self
    def eq(self, col, val):
        self._owner.calls["eq"] = (col, val)
        return self
    def in_(self, col, vals):
        self._owner.calls["in"] = (col, tuple(vals))
        return self
    def order(self, col, desc=False):
        self._owner.calls["order"] = (col, desc)
        return self
    def limit(self, n):
        self._owner.calls["limit"] = n
        return self
    def execute(self):
        if self._boom:
            raise RuntimeError("db down")
        return SimpleNamespace(data=self._rows)


class FakeSupabase:
    def __init__(self, rows, boom=False):
        self.rows, self.boom, self.calls = rows, boom, {}
    def table(self, name):
        self.calls["table"] = name
        return FakeQuery(self, self.rows, self.boom)


def run_pulse(rows, boom=False):
    fake = FakeSupabase(rows, boom)
    prior_sb = H.supabase
    prior_env = os.environ.get("PROMPTLY_JOB_TABLE")
    H.supabase = fake
    os.environ["PROMPTLY_JOB_TABLE"] = "video_jobs"
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            return H.fetch_platform_style_pulse(), fake
    finally:
        H.supabase = prior_sb
        if prior_env is None:
            os.environ.pop("PROMPTLY_JOB_TABLE", None)
        else:
            os.environ["PROMPTLY_JOB_TABLE"] = prior_env


def rows_of(*styles):
    return [{"caption_style": s} for s in styles]


print("=== P1: dominant top-1 → verbatim line ===")
line, fake = run_pulse(rows_of("Gadzhi", "Gadzhi", "Gadzhi", "Gadzhi", "Lumen", "Prime"))
check("top-1 line verbatim",
      line == "Recently frequent caption styles across the platform: Gadzhi "
              + VERBATIM_TAIL)
check("queries the job table by env", fake.calls.get("table") == "video_jobs")
check("arrow-path select on nested vocab",
      fake.calls.get("select") == "result->vocab->>caption_style")
check("delivered rows only — BOTH spellings (worker 'complete', app 'completed')",
      fake.calls.get("in") == ("status", ("complete", "completed")))
check("newest first", fake.calls.get("order") == ("created_at", True))
check("over-fetch 4x window for older no-vocab rows", fake.calls.get("limit") == 200)

print("\n=== P2: two frequent styles → 'top1, top2' ===")
line, _ = run_pulse(rows_of(*(["Gadzhi"] * 5 + ["Lumen"] * 3 + ["Prime"] * 2)))
check("top-2 line verbatim",
      line == "Recently frequent caption styles across the platform: Gadzhi, Lumen "
              + VERBATIM_TAIL)

print("\n=== P3: second style under the 20% share floor is excluded ===")
line, _ = run_pulse(rows_of(*(["Cove"] * 9 + ["Pulse"])))  # Pulse 1/10 < floor 2
check("only the dominant style named", line is not None and "Cove" in line and "Pulse" not in line)

print("\n=== P4: null/'none' filtered; window caps at newest 50 ===")
mixed = [{"caption_style": None}, {"caption_style": "none"}] + rows_of(*(["Quintessence"] * 6))
line, _ = run_pulse(mixed)
check("null and 'none' rows don't count", line is not None and "Quintessence" in line and "none" not in line.split(":")[1].split("—")[0])
line, _ = run_pulse(rows_of(*(["Cove"] * 50 + ["Prime"] * 10)))
check("only newest 50 counted (older Prime rows outside window)",
      line is not None and "Prime" not in line)

print("\n=== P5: fail-open — thin window, flat field, no client, db down ===")
line, _ = run_pulse(rows_of("Gadzhi", "Gadzhi", "Gadzhi", "Gadzhi"))
check("<5 vocab rows → None", line is None)
line, _ = run_pulse(rows_of("Cove", "Prime", "Lumen", "Pulse", "Gadzhi", "TwoTone"))
check("no style reaches the floor → None", line is None)
line, _ = run_pulse([], boom=True)
check("query raises → None (never a job's problem)", line is None)
prior = H.supabase
H.supabase = None
check("supabase client absent → None", H.fetch_platform_style_pulse() is None)
H.supabase = prior

print("\n=== P6: deterministic tie-break (count desc, then name) ===")
line, _ = run_pulse(rows_of(*(["TwoTone"] * 3 + ["Cove"] * 3 + ["Lumen"] * 3)))
check("alphabetical among equals", line is not None and "Cove, Lumen" in line)

print("\n=== W1: wire pins — the note rides the pipeline fail-open ===")
src = open("handler.py").read()
check("parallel fetch submitted next to the user profile",
      "mega_pool.submit(fetch_platform_style_pulse)" in src)
check("read is guarded with timeout (fail-open to None)",
      "future_platform_pulse.result(timeout=10)" in src)
check("call site passes the note", "platform_style_note=_platform_pulse" in src)
check("generate passes through to the prompt builder",
      "platform_style_note=platform_style_note" in src)

print("\n=== W2: prompt placement — USER content only, system untouched ===")
sys_a, user_a = H._build_post_cuts_prompt(vibe="test vibe", duration=60.0)
note = ("Recently frequent caption styles across the platform: Gadzhi "
        + VERBATIM_TAIL)
sys_b, user_b = H._build_post_cuts_prompt(vibe="test vibe", duration=60.0,
                                          platform_style_note=note)
check("system prompt byte-identical with/without note", sys_a == sys_b)
check("note absent from system prompt", "Recently frequent caption styles" not in sys_b)
check("note verbatim in user content when present", note in user_b)
check("no trace in user content when None", "Recently frequent caption styles" not in user_a)

print(f"\n{'='*60}\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", FAIL)
    raise SystemExit(1)
