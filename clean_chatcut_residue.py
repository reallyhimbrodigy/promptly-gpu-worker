#!/usr/bin/env python3
"""Delete the harness's own project residue. DRY RUN unless --apply.

236 projects in the account and 219 of them are this repo talking to itself:
every ChatCut execution run creates a fresh "Promptly plan-first", every
component probe a "render check <Component>", every bake a "bake <name>", every
refusal probe a "refusal <name>".

THE ALLOWLIST IS DERIVED FROM THIS REPO'S OWN create_project CALLS, and nothing
else is touched. The four shapes are at chatcut_job_app.py:821, :3332, :3514
and :3602 plus the retired `wiring sweep` entrypoint. A project whose name this
code cannot produce is NOT residue by definition, and is left alone and NAMED —
"Ad Read Cleanup" and "Promptly - 100 TikToks per Hour" are somebody's work.

ChatCut's delete is the dashboard's SOFT delete: `restore_project` undoes it and
`list_projects includeDeleted=true` shows what is restorable. That is the only
reason this is a script and not a conversation — it is reversible, per project,
by name.
"""
import argparse
import json
import re
import sys

import modal

app = modal.App("promptly-chatcut-clean")
image = (modal.Image.debian_slim(python_version="3.11")
         .add_local_file("chatcut_reference.py", "/root/chatcut_reference.py"))
TOK = modal.Dict.from_name("chatcut-tokens", create_if_missing=True)

# EXACTLY the shapes this repo generates. Anchored, so "Promptly plan-first
# KEEP" or "render checklist" are not swept up by a loose prefix.
RESIDUE = (re.compile(r"^Promptly plan-first$"),
           re.compile(r"^render check \S"),
           re.compile(r"^bake \S"),
           re.compile(r"^refusal \S"),
           re.compile(r"^wiring sweep$"))
# The reference library. Named by ID as well as by name, because a name is a
# thing someone can change and an id is not.
KEEP_IDS = {"74036980-7215-4852-8423-0dca60e2403c"}


def is_residue(p):
    if p.get("projectId") in KEEP_IDS:
        return False
    n = (p.get("name") or "").strip()
    return any(rx.match(n) for rx in RESIDUE)


@app.function(image=image, timeout=3600,
              secrets=[modal.Secret.from_name("chatcut-oauth")])
def sweep(apply_it: bool = False) -> dict:
    import chatcut_reference as cr
    tok = cr.access_token(TOK)
    r = cr.rpc(tok, "tools/call",
               {"name": "list_projects", "arguments": {}})
    st = cr.structured(r)
    ps = st.get("projects") or []
    if not ps:
        return {"state": "ABSENT",
                "why": "list_projects returned no projects — refusing to "
                       "conclude the account is empty from a failed read"}
    res = [p for p in ps if is_residue(p)]
    keep = [p for p in ps if not is_residue(p)]
    out = {"state": "DRY RUN" if not apply_it else "APPLIED",
           "total": len(ps), "residue": len(res), "kept": len(keep),
           "kept_names": sorted({(p.get("name") or "").strip() for p in keep}),
           "deleted": 0, "failed": []}
    if not apply_it:
        return out
    for i, p in enumerate(res):
        try:
            cr.rpc(tok, "tools/call",
                   {"name": "delete_project",
                    "arguments": {"projectId": p["projectId"]}}, mid=i + 2)
            out["deleted"] += 1
        except Exception as e:                                    # noqa: BLE001
            out["failed"].append("%s: %s" % (p.get("name"), str(e)[:80]))
        if (i + 1) % 25 == 0:
            print("  deleted %d/%d" % (out["deleted"], len(res)), flush=True)
            tok = cr.access_token(TOK)      # the grant is short-lived
    return out


@app.local_entrypoint()
def main(apply_it: bool = False):
    r = sweep.remote(apply_it)
    print(json.dumps(r, indent=1)[:2600])
