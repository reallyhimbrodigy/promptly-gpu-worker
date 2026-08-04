"""prompt_token_map.py — per-section token map of the Call-2 CACHED PREFIX.

Read-only. No Modal, no network, no edits. The Phase-3 measuring stick.

WHAT IT MEASURES
  The cached `system_instruction` Gemini actually receives on Call 2:
    core        = handler.py f-string  (opens `system_instruction = f` + triple-quote
                  + `=== YOUR JOB ===`)
    static tail = the unconditional `system_instruction +=` appends (LEVER3, WHY-DIET,
                  BURNED-TEXT) — part of EVERY job's cached prefix (ledger §8E).
  Per-job forks (premium, EDITOR'S CONSTRAINTS, AUTHOR-IN-SOURCE-LANGUAGE) are
  listed separately: they fragment the cache by (premium x policy x language) and
  are NOT part of the shared baseline.

CALIBRATION — the honest bit
  Authoritative baseline = Vertex's own `cached_content_token_count` = 40,473 on a
  real Call 2 (2026-07-31). We cannot re-run Vertex countTokens locally (no ADC),
  so absolute per-section tokens are chars / CHARS_PER_TOKEN where the factor is
  BACK-SOLVED from that one authoritative total. Consequences, stated plainly:
    - per-section RATIOS (before/after) are EXACT — they are char ratios, and the
      factor cancels. Ratios are what Phase 3 is judged on.
    - per-section ABSOLUTE tokens carry the factor's error (~2-4%, ledger §8E).
    - the real number returns for free: the first Call 2 after deploy logs
      `cached=` (handler.py `cached_content_token_count`). That is the Rule-2
      real-traffic observation, and it costs nothing to collect.

USAGE
    python3 prompt_token_map.py                  # full map
    python3 prompt_token_map.py --json           # machine-readable
    python3 prompt_token_map.py --section "B-ROLL"   # dump one section's text
"""
import json
import re
import sys

HANDLER = "handler.py"

# Vertex `cached_content_token_count` from a real Call 2, 2026-07-31 (ledger §0).
VERTEX_BASELINE_TOKENS = 40473
# Chars in that same prefix, measured at the Phase-3 start commit. The ratio is
# FROZEN on purpose: re-solving it every run would re-normalise the total to
# 40,473 after every cut and report a delta of zero. Only re-pin these two
# numbers together, against a fresh Vertex `cached=` reading from real traffic.
BASELINE_CHARS = 169755
CHARS_PER_TOKEN = BASELINE_CHARS / VERTEX_BASELINE_TOKENS  # 4.19428

_OPEN = 'system_instruction = f"""=== YOUR JOB ==='
_HEADER = re.compile(r"^\s*=== (.+?) ===\s*$")


def _read_lines():
    with open(HANDLER, encoding="utf-8") as fh:
        return fh.read().split("\n")


def _unescape(s):
    """The f-string doubles literal braces; Gemini receives them singled."""
    return s.replace("{{", "{").replace("}}", "}")


def extract_core(lines):
    """Return (start_line, end_line, text) of the cached f-string body, 1-indexed."""
    start = None
    for i, ln in enumerate(lines):
        if _OPEN in ln:
            start = i
            break
    if start is None:
        raise SystemExit("FATAL: could not find the system_instruction f-string open")
    # The body starts at the `=== YOUR JOB ===` on the opening line itself.
    body_first = lines[start].split('f"""', 1)[1]
    out = [body_first]
    end = None
    for i in range(start + 1, len(lines)):
        ln = lines[i]
        if ln.rstrip().endswith('"""'):
            out.append(ln.rstrip()[:-3])
            end = i
            break
        out.append(ln)
    if end is None:
        raise SystemExit("FATAL: could not find the f-string close")
    return start + 1, end + 1, _unescape("\n".join(out))


def split_sections(text, first_label="PREAMBLE (=== YOUR JOB ===)"):
    """Split on `=== HEADER ===` lines. Returns [(label, text), ...] in order."""
    sections, label, buf = [], first_label, []
    for ln in text.split("\n"):
        m = _HEADER.match(ln)
        if m and not ln.strip().startswith("=== YOUR JOB"):
            sections.append((label, "\n".join(buf)))
            label, buf = m.group(1).strip(), [ln]
        else:
            buf.append(ln)
    sections.append((label, "\n".join(buf)))
    return sections


def extract_appends(lines, core_end):
    """The `system_instruction +=` blocks after the f-string close.

    Classified STATIC (in every cached prefix) vs PER-JOB (forks the cache) by
    ledger §8E. Detection is by the nearest enclosing `if` above each append.
    """
    blocks = []
    i = core_end  # 0-indexed position just past the close
    while i < len(lines):
        ln = lines[i]
        if "system_instruction +=" in ln:
            # Collect the string literal that follows, to its close.
            buf, j, opened = [], i, False
            while j < len(lines) and j < i + 200:
                cur = lines[j]
                quotes = cur.count('"""')
                if not opened and quotes:
                    opened = True
                    seg = cur.split('"""', 1)[1]
                    if seg.rstrip().endswith('"""'):
                        buf.append(seg.rstrip()[:-3])
                        break
                    buf.append(seg)
                elif opened:
                    if cur.rstrip().endswith('"""'):
                        buf.append(cur.rstrip()[:-3])
                        break
                    buf.append(cur)
                elif not opened and j > i and cur.strip().startswith('"'):
                    # Adjacent-string-concat form: "..." \n "..."
                    buf.append(cur.strip().strip('"').replace("\\n", "\n"))
                    if cur.rstrip().endswith(")"):
                        break
                if j > i and lines[j].strip() == ")" and buf:
                    break
                j += 1
            # Nearest enclosing condition, looking upward.
            cond = ""
            for k in range(i, max(0, i - 40), -1):
                s = lines[k].strip()
                if s.startswith("if ") or s.startswith("elif "):
                    cond = s
                    break
            blocks.append(
                {
                    "line": i + 1,
                    "cond": cond,
                    "text": _unescape("\n".join(buf)),
                }
            )
            i = j + 1
            continue
        # Stop once we leave the builder.
        if re.match(r"^def \w", ln) and i > core_end + 5:
            break
        i += 1
    return blocks


# ── Append classification is DERIVED, never hand-written ─────────────────────
# An append lands in the shared cached prefix iff its gating flag is canonically
# ON. The canonical live values are the CANON dict in validate_deploy.py (the
# same dict the deploy gate asserts the real Modal secret against), so this map
# self-corrects the day a flag flips instead of rotting into a stale comment.
#   STATIC  — flag canonically ON, no per-job input  -> in EVERY cached prefix
#   PER-JOB — gated on per-job state (premium, policy, source_language)
#   DARK    — flag absent from CANON (unset) -> not in the live prefix at all
_CANON_RE = re.compile(r'"(PROMPTLY_[A-Z0-9_]+)"\s*:\s*"([^"]*)"')
_FLAG_RE = re.compile(r"PROMPTLY_[A-Z0-9_]+")
# Conditions that depend on per-job inputs, not just a flag.
_PERJOB_TOKENS = ("source_language", "is_premium", "premium", "_ep_lines", "_pol_off")


def load_canon(path="validate_deploy.py"):
    """Parse the canonical live secret values out of the deploy gate."""
    try:
        with open(path, encoding="utf-8") as fh:
            src = fh.read()
    except OSError:
        return {}
    start = src.find("    CANON = {")
    if start < 0:
        return {}
    return dict(_CANON_RE.findall(src[start:src.find("}", start)]))


def resolve_flag(cond, enablers):
    """Flag name a condition ultimately reads — directly or via an `_x_enabled()`."""
    m = _FLAG_RE.search(cond)
    if m:
        return m.group(0)
    for fn, flag in enablers.items():
        if fn in cond:
            return flag
    return None


def load_enablers(src):
    """Map `_foo_enabled` -> the PROMPTLY_ flag its body reads."""
    out = {}
    for m in re.finditer(r"^def (_\w+)\(\):\n(.*?)(?=^def |\Z)", src, re.S | re.M):
        name, body = m.group(1), m.group(2)
        if "enabled" not in name:
            continue
        f = _FLAG_RE.search(body)
        if f:
            out[name] = f.group(0)
    return out


def classify(cond, canon, enablers):
    flag = resolve_flag(cond, enablers)
    if any(t in cond for t in _PERJOB_TOKENS):
        return "PER-JOB", flag
    if flag is None:
        return "STATIC", None
    if flag not in canon:
        return "DARK", flag
    return ("STATIC" if canon[flag] not in ("", "0", "false", "off") else "DARK"), flag


def build_map():
    lines = _read_lines()
    core_start, core_end, core = extract_core(lines)
    sections = split_sections(core)
    appends = extract_appends(lines, core_end)

    canon = load_canon()
    enablers = load_enablers("\n".join(lines))
    for b in appends:
        b["class"], b["flag"] = classify(b["cond"], canon, enablers)
    static = [b for b in appends if b["class"] == "STATIC"]
    perjob = [b for b in appends if b["class"] != "STATIC"]

    baseline_chars = sum(len(t) for _, t in sections) + sum(len(b["text"]) for b in static)
    cpt = CHARS_PER_TOKEN          # FROZEN — see the constant's note

    rows = [
        {"kind": "core", "label": lbl, "chars": len(t), "tokens": round(len(t) / cpt)}
        for lbl, t in sections
    ]
    rows += [
        {
            "kind": "static-tail",
            "label": (b["text"].strip().split("\n")[0][:52] or f"append@{b['line']}"),
            "chars": len(b["text"]),
            "tokens": round(len(b["text"]) / cpt),
            "line": b["line"],
        }
        for b in static
    ]
    forks = [
        {
            "kind": b["class"],
            "label": (b["text"].strip().split("\n")[0][:52] or f"append@{b['line']}"),
            "chars": len(b["text"]),
            "tokens": round(len(b["text"]) / cpt),
            "line": b["line"],
            "flag": b["flag"] or "-",
        }
        for b in perjob
    ]
    return {
        "core_lines": [core_start, core_end],
        "chars_per_token": round(cpt, 4),
        "baseline_chars": baseline_chars,
        "baseline_tokens": VERTEX_BASELINE_TOKENS,
        "rows": rows,
        "forks": forks,
        "sections": {lbl: t for lbl, t in sections},
    }


def main():
    m = build_map()
    if "--section" in sys.argv:
        want = sys.argv[sys.argv.index("--section") + 1]
        for lbl, txt in m["sections"].items():
            if want.lower() in lbl.lower():
                sys.stdout.write(txt)
                return
        raise SystemExit(f"no section matching {want!r}; have: {list(m['sections'])}")
    if "--json" in sys.argv:
        m.pop("sections")
        print(json.dumps(m, indent=2))
        return

    print(f"CACHED PREFIX — per-section token map   (handler.py:{m['core_lines'][0]}-{m['core_lines'][1]} + static tail)")
    _cut = VERTEX_BASELINE_TOKENS - sum(r["tokens"] for r in m["rows"])
    print(f"calibration: FROZEN at {BASELINE_CHARS:,} chars / {m['baseline_tokens']:,} Vertex "
          f"tokens = {m['chars_per_token']} chars/token (Phase-3 start)")
    print(f"cut so far:  {_cut:+,} tokens  "
          f"({100.0 * _cut / VERTEX_BASELINE_TOKENS:+.2f}% of the cached prefix)\n")
    print(f"{'tok':>7}  {'chars':>7}  {'kind':<12} section")
    print("-" * 88)
    for r in sorted(m["rows"], key=lambda r: -r["tokens"]):
        print(f"{r['tokens']:>7,}  {r['chars']:>7,}  {r['kind']:<12} {r['label']}")
    print("-" * 88)
    tot = sum(r["tokens"] for r in m["rows"])
    print(f"{tot:>7,}  {sum(r['chars'] for r in m['rows']):>7,}  {'BASELINE':<12} "
          f"(Vertex authoritative {m['baseline_tokens']:,})")
    if m["forks"]:
        print("\nNOT IN THE SHARED BASELINE (per-job cache forks + dark flags):")
        print(f"{'tok':>7}  {'chars':>7}  {'class':<8} {'flag':<28} block")
        for r in sorted(m["forks"], key=lambda r: -r["tokens"]):
            print(f"{r['tokens']:>7,}  {r['chars']:>7,}  {r['kind']:<8} {r['flag']:<28} "
                  f"L{r['line']} {r['label'][:44]}")


if __name__ == "__main__":
    main()
