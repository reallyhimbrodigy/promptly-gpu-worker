"""Read a spawned job's result out of the durable Dict.

Separate from the launcher ON PURPOSE: the whole point is that the answer does
not depend on the process that started the work still being alive.
"""
import json
import modal

app = modal.App("chatcut-read-result")
RESULTS = modal.Dict.from_name("chatcut-results", create_if_missing=True)


@app.local_entrypoint()
def main(run_id: str = "", list_all: bool = False, out: str = ""):
    if list_all or not run_id:
        print("keys:", list(RESULTS.keys()))
        return
    v = RESULTS.get(run_id)
    if v is None:
        print(f"{run_id}: ABSENT — not finished, or never started. Not 'empty'.")
        return
    # NEVER A PREFIX. This printed `[:12000]` and cut the record mid-string, so
    # every reader downstream died on a JSONDecodeError that looks like a
    # corrupt result rather than a truncated print. Second time this exact
    # reader has done it. A truncated artifact and a broken one are
    # indistinguishable once the bytes are gone, so the whole record goes to a
    # FILE and the terminal gets a summary that says what it is a summary OF.
    if out:
        with open(out, "w", encoding="utf-8") as fh:
            json.dump(v, fh, indent=1)
        print(f"WROTE {out}  ({len(json.dumps(v))} chars, complete)")
    sh = (v or {}).get("shape") or {}
    print("  wall_s          : %s" % v.get("wall_s"))
    print("  agent_s         : %s" % ((v.get("marks") or {}).get("agent")))
    print("  assistant_turns : %s" % sh.get("assistant_turns"))
    print("  turns_with_no_tool: %s" % sh.get("turns_with_no_tool"))
    print("  tool_calls      : %s  errors %s  identical_repeats %s"
          % (sh.get("tool_calls"), sh.get("tool_errors"),
             sh.get("identical_repeats")))
    print("  visual_pass     : %s" % json.dumps(v.get("visual_pass")))
    if not out:
        print("  (pass --out PATH for the complete record; this is a SUMMARY "
              "of %d chars, not the record)" % len(json.dumps(v)))
