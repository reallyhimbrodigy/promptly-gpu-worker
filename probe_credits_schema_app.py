"""Verify BOTH migrations landed, and that service_role can actually read the
RLS-protected table.

RLS is enabled on reverse_trial_grants with NO policies. That means a non-
service_role client gets ZERO ROWS rather than an error — indistinguishable from
"no grant exists", which would re-grant. So this checks two different things:

  1. the columns/table EXIST (the migration ran), and
  2. service_role can SELECT and INSERT (the endpoint's client actually works
     against the policy set, rather than silently reading empty).

A schema check that only asks "does the column exist" would pass on a table the
server cannot read.
"""
import os
import uuid

import modal

app = modal.App("probe-credits-schema")
image = modal.Image.debian_slim().pip_install("supabase")
S = [modal.Secret.from_name("promptly-secrets")]


@app.function(image=image, secrets=S, timeout=300)
def check() -> dict:
    from supabase import create_client
    key = (os.environ.get("SUPABASE_SERVICE_KEY")
           or os.environ.get("SUPABASE_SERVICE_ROLE_KEY"))
    sb = create_client(os.environ.get("SUPABASE_URL"), key)
    out = {}

    # 1. video_jobs columns — selecting them errors if they do not exist.
    try:
        sb.table("video_jobs").select(
            "id,credits_debited,credits_refunded_at").limit(1).execute()
        out["video_jobs_columns"] = "PRESENT"
    except Exception as e:
        out["video_jobs_columns"] = f"MISSING/ERROR: {str(e)[:130]}"

    # 2. reverse_trial_grants exists AND is readable by this key.
    try:
        r = sb.table("reverse_trial_grants").select("device_id").limit(1).execute()
        out["reverse_trial_read"] = f"OK (rows={len(r.data or [])})"
    except Exception as e:
        out["reverse_trial_read"] = f"ERROR: {str(e)[:130]}"

    # 3. THE ONE THAT MATTERS: can this key actually WRITE and READ BACK? A
    #    silent-zero would show up here as "wrote, then read 0 rows".
    probe_id = f"__schema_probe_{uuid.uuid4().hex[:12]}"
    try:
        sb.table("reverse_trial_grants").insert({
            "device_id": probe_id,
            "user_id": "00000000-0000-0000-0000-000000000000",
            "pro_until": "2000-01-01T00:00:00Z",
        }).execute()
        back = sb.table("reverse_trial_grants").select(
            "device_id").eq("device_id", probe_id).execute()
        n = len(back.data or [])
        out["service_role_write_readback"] = (
            "OK — wrote and read back 1 row" if n == 1
            else f"SILENT ZERO: wrote but read back {n} rows "
                 f"(this is the re-grant failure mode)")
        # PK uniqueness is the once-per-install enforcement — prove it bites.
        try:
            sb.table("reverse_trial_grants").insert({
                "device_id": probe_id,
                "user_id": "00000000-0000-0000-0000-000000000000",
                "pro_until": "2000-01-01T00:00:00Z",
            }).execute()
            out["pk_uniqueness"] = "❌ DUPLICATE ACCEPTED — once-per-install is NOT enforced"
        except Exception:
            out["pk_uniqueness"] = "OK — duplicate device_id rejected by the PK"
        sb.table("reverse_trial_grants").delete().eq("device_id", probe_id).execute()
        out["cleanup"] = "probe row deleted"
    except Exception as e:
        out["service_role_write_readback"] = f"ERROR: {str(e)[:160]}"
    return out


@app.local_entrypoint()
def main():
    d = check.remote()
    print("\n=== CREDITS / REVERSE-TRIAL SCHEMA VERIFICATION ===")
    for k, v in d.items():
        mark = "✅" if ("OK" in str(v) or "PRESENT" in str(v) or "deleted" in str(v)) else "❌"
        print(f"  {mark} {k:<28} {v}")
