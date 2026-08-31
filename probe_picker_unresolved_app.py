import os, modal
from collections import Counter
app = modal.App("probe-picker-unresolved")
img = modal.Image.debian_slim().pip_install("supabase")
S=[modal.Secret.from_name("promptly-secrets")]

@app.function(image=img, secrets=S, timeout=900)
def scan():
    from supabase import create_client
    sb=create_client(os.environ.get("SUPABASE_URL"),
        os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY"))
    out={}
    for ev in ("picker_asset_unresolved","picker_result","upload_started","render_completed"):
        rows=[]; page=0
        while page<6:
            r=(sb.table("analytics_events").select("user_id,props,created_at")
               .eq("event", ev).order("created_at",desc=True)
               .range(page*1000, page*1000+999).execute())
            d=r.data or []; rows.extend(d)
            if len(d)<1000: break
            page+=1
        out[ev]=rows
    return out

@app.local_entrypoint()
def main():
    d = scan.remote()
    un = d["picker_asset_unresolved"]
    print(f"\n=== picker_asset_unresolved — TWO MECHANISMS, ONE EVENT NAME ===")
    print(f"  {len(un)} events, {len({e.get('user_id') for e in un})} distinct users\n")
    by_noasset = [e for e in un if 'no_asset' in (e.get('props') or {})]
    by_stage   = [e for e in un if 'stage' in (e.get('props') or {})]
    other      = [e for e in un if 'no_asset' not in (e.get('props') or {})
                  and 'stage' not in (e.get('props') or {})]
    print(f"  VideoPicker (no_asset/no_identifier) : {len(by_noasset)} events, "
          f"{len({e.get('user_id') for e in by_noasset})} users")
    print(f"  EditorView  (stage=materialize_*)    : {len(by_stage)} events, "
          f"{len({e.get('user_id') for e in by_stage})} users")
    print(f"  neither shape                        : {len(other)}")
    if by_stage:
        print(f"\n  stage distribution:")
        for k,v in Counter(str((e.get('props') or {}).get('stage')) for e in by_stage).most_common():
            print(f"    {v:>5}  {k}")
    ni=sum(int((e.get('props') or {}).get('no_identifier') or 0) for e in by_noasset)
    na=sum(int((e.get('props') or {}).get('no_asset') or 0) for e in by_noasset)
    print(f"\n  within VideoPicker: no_identifier={ni}  no_asset={na}")

    # ── RECOVERY: did an affected user ever get a pick through, or upload? ──
    affected = {e.get('user_id') for e in by_noasset if e.get('user_id')}
    ok_pick = {e.get('user_id') for e in d["picker_result"]
               if (e.get('props') or {}).get('resolved',0) > 0}
    uploaded = {e.get('user_id') for e in d["upload_started"] if e.get('user_id')}
    rendered = {e.get('user_id') for e in d["render_completed"] if e.get('user_id')}
    print(f"\n  === RECOVERY (per USER, not per event) ===")
    print(f"    affected users (VideoPicker drop)     : {len(affected)}")
    if affected:
        print(f"    ...who later resolved a pick (>0)     : {len(affected & ok_pick)} "
              f"({100.0*len(affected & ok_pick)/len(affected):.0f}%)")
        print(f"    ...who ever reached upload_started    : {len(affected & uploaded)} "
              f"({100.0*len(affected & uploaded)/len(affected):.0f}%)")
        print(f"    ...who ever reached render_completed  : {len(affected & rendered)} "
              f"({100.0*len(affected & rendered)/len(affected):.0f}%)")
        lost = affected - ok_pick - uploaded
        print(f"    NEVER recovered (no pick, no upload)  : {len(lost)} "
              f"({100.0*len(lost)/len(affected):.0f}%)  <- the real loss")

