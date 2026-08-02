"""phase3_schema_guaranteed.py — prose the SCHEMA already guarantees.

Zac's test, applied beyond the WHY class: constrained decoding means the model
CANNOT emit an invalid enum or an out-of-bounds value. Prose that merely restates
an enum or a bound is therefore a GUARANTEE — losslessly deletable.

THE DISTINCTION THAT DECIDES THE NUMBER
  Restating the VALUE SET is guaranteed:
      "anchor": "upper_third_safe" | "center" | "lower_third_safe"
  Telling the model WHICH ONE TO PICK is not — it is the directive:
      "upper_third_safe — the default: the clear gap above the head"
  Constrained decoding stops an invalid anchor. It does not choose the right one.
  So only BARE VALUE LISTINGS count, never the selection guidance around them.

AND ONE EXCLUSION THAT MATTERS
  `props` is `Dict[str, Any]` on both MG models — the schema constrains NOTHING
  inside it. Every enum union inside a `Props:` line (e.g.
  `"mode"?: "compare"|"race"`) is therefore the ONLY place that contract exists.
  Those are load-bearing, not restatement, and are excluded here.

Read-only. No Modal, no network.
"""
import json
import re
import sys
import types

from prompt_token_map import CHARS_PER_TOKEN as CPT, build_map


def load_schema():
    for m in ("modal", "boto3", "botocore", "supabase", "cv2", "deepgram"):
        sys.modules.setdefault(m, types.ModuleType(m))
    import handler as H
    return H._post_cuts_response_schema()


def walk(node, enums, bounds, path=""):
    if isinstance(node, dict):
        if "enum" in node and isinstance(node["enum"], list):
            enums.append((path, [str(v) for v in node["enum"]]))
        for k in ("minimum", "maximum", "minItems", "maxItems", "maxLength", "minLength"):
            if k in node and isinstance(node[k], (int, float)):
                bounds.append((path, k, node[k]))
        for k, v in node.items():
            walk(v, enums, bounds, f"{path}.{k}" if k not in ("properties", "$defs", "items", "anyOf") else path)
    elif isinstance(node, list):
        for v in node:
            walk(v, enums, bounds, path)


def main():
    s = load_schema()
    enums, bounds = [], []
    walk(s, enums, bounds)
    vocab = {}
    for path, vals in enums:
        if len(vals) >= 2:
            vocab[tuple(sorted(vals))] = path
    print(f"SCHEMA: {len(enums)} enum declarations ({len(vocab)} distinct value-sets), "
          f"{len(bounds)} numeric/length bounds\n")

    sections = build_map()["sections"]
    # A bare value listing: >=2 quoted members of one schema enum, joined by |,
    # with no selection verb in the fragment.
    _SELECT = re.compile(r"\b(default|prefer|use|pick|choose|when|only|last resort"
                         r"|belongs|fits|fights|reach|instead)\b", re.I)
    total = 0
    hits = []
    for sec, text in sections.items():
        for line in text.split("\n"):
            if line.strip().startswith("Props"):
                continue          # props is Dict[str,Any] — NOT schema-constrained
            for frag in re.findall(r'(?:"[a-z_0-9]+"\s*\|\s*)+"[a-z_0-9]+"', line):
                members = tuple(sorted(re.findall(r'"([a-z_0-9]+)"', frag)))
                owner = None
                for vs, path in vocab.items():
                    if set(members) <= set(vs) and len(members) >= 2:
                        owner = path
                        break
                if not owner:
                    continue
                if _SELECT.search(line):
                    continue      # the line also STEERS — not a bare listing
                t = len(frag) / CPT
                total += t
                hits.append((sec, owner, round(t), frag[:70]))

    print("BARE ENUM LISTINGS the schema already enforces (no selection guidance "
          "in the line):")
    for sec, owner, t, frag in hits:
        print(f"  {t:>3} tok  {sec[:22]:<22} {owner[-34:]:<34} {frag}")
    print(f"\n  deletable by the GUARANTEE test: {round(total)} tok "
          f"({100.0*total/40473:.2f}% of the prefix)")
    print(f"  (excluded: every enum union inside a `Props:` line — props is "
          f"Dict[str, Any], so those are the ONLY contract, not restatement)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
