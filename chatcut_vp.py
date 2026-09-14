import modal
app = modal.App("chatcut-vp")
R = modal.Dict.from_name("chatcut-results", create_if_missing=True)
@app.local_entrypoint()
def main(run_id: str = ""):
    d = R.get(run_id)
    print("VISUAL PASS:", d.get("visual_pass"))
    print("wall:", d.get("wall_s"), "rc:", d.get("rc"))
    s = d["shape"]
    sheet = [c for c in s["calls"] if "source_sheet" in (c.get("in") or "")]
    print("sheet reads:", len(sheet))
    for c in sheet: print("   t%-4d %s %s" % (c["turn"], c["tool"], c["in"][:70]))
