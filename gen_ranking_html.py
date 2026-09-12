#!/usr/bin/env python3
"""Emit CAPABILITY_RANKING.html from CAPABILITY_RANKING.json. Never hand-typed."""
import html
import json

D = json.load(open("CAPABILITY_RANKING.json"))
rows, corpus, ref = D["rows"], D["corpus"], D["reference"]

TIERS = [
    ("BUILDABLE NOW", "now", "Nothing to build",
     "The component and the placement path both ship. These were never placed "
     "because the corpus that teaches the agent could not hear them."),
    ("ROUTE", "route", "Needs a route, not a build",
     "The component is rendered, tested and in VALID_MG_TYPES. What is missing "
     "is a path from a ruling to it — the same mechanism as the card "
     "conditions: the agent names what the moment is, the harness derives the "
     "component."),
    ("CAPTION LAYER", "layer", "One capability, not three",
     "All three are the caption layer, which already runs on every job. What is "
     "missing is per-word control exposed to the ruling surface."),
    ("BEHAVIOUR", "behav", "Reachable component, wrong behaviour",
     "StatCard is one of the only two components the agent can reach today. The "
     "corpus says the number ticks; the component renders it static."),
    ("BUILD", "build", "Genuinely new work",
     "Nothing close ships. These are the only entries on this page that are a "
     "build in the ordinary sense."),
    ("NOT A PIPELINE JOB", "src", "In the source, not the edit",
     "A prop held on camera, a gesture, a framing choice. These are shooting "
     "notes — no edit can add them."),
    ("OBSERVATION", "obs", "One editor, once",
     "Seen in a single video of ten. Not a capability gap by the corpus's own "
     "standard: the discovery statistic is videos, not occurrences."),
]
GROUP = {"ROUTE?": "ROUTE"}


def bar(n, cls):
    seg = "".join(
        f'<i class="{cls}{" on" if i < n else ""}"></i>' for i in range(10))
    return f'<span class="bar">{seg}</span>'


parts = []
for i, (key, cls, tag, blurb) in enumerate(TIERS, 1):
    grp = [r for r in rows if GROUP.get(r["status"], r["status"]) == key]
    if not grp:
        continue
    parts.append(f'''
<section class="tier t-{cls}">
  <header class="tier-h">
    <span class="ord">{i}</span>
    <div>
      <h2>{html.escape(key.title() if key != "BUILDABLE NOW" else "Buildable now")}</h2>
      <p class="tag">{html.escape(tag)} · {len(grp)} famil{"y" if len(grp)==1 else "ies"}</p>
    </div>
  </header>
  <p class="blurb">{html.escape(blurb)}</p>
  <ol class="rows">''')
    for r in grp:
        corro = r["evidence"] == "CORROBORATED"
        mark = ('<span class="corro" title="found independently by both '
                'readers">both arms</span>' if corro else
                f'<span class="single">{"heard only" if r["arms"]=="heard" else "silent only"}</span>')
        q = ' <span class="q" title="nearest component is not the same move">approx</span>' \
            if r["status"] == "ROUTE?" else ""
        parts.append(f'''
    <li class="row">
      <div class="demand">
        <b>{r["users"]:,}</b><span class="u">users</span>
        <span class="pct">{r["pct"]:.1f}%</span>
      </div>
      <div class="supply">
        <span class="arm"><span class="al">silent</span>{bar(r["sil"], "s")}<span class="an">{r["sil"]}/10</span></span>
        <span class="arm"><span class="al">heard</span>{bar(r["heard"], "h")}<span class="an">{r["heard"]}/10</span></span>
        {mark}
      </div>
      <div class="what">
        <h3>{html.escape(r["family"])}{q}</h3>
        <p class="how">{html.escape(r["how"])}</p>
        <p class="near"><span class="nl">nearest</span> <code>{html.escape(r["nearest"])}</code></p>
      </div>
    </li>''')
    parts.append("  </ol>\n</section>")

BODY = "\n".join(parts)

HTML = f'''<title>Capability Ranking</title>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@600;800&family=Source+Sans+3:wght@400;600&family=JetBrains+Mono:wght@400;600&display=swap">
<style>
:root {{
  --ground:#F4F2ED; --surface:#FFFFFF; --sunk:#EAE7E0;
  --ink:#16201F; --ink-2:#4A5856; --muted:#778482; --line:#D8D4CB;
  --signal:#B4762A;
  --now:#1F8F68; --route:#B4762A; --layer:#4C63C4; --behav:#8B54B8; --build:#B9503F;
  --disp:"Archivo",system-ui,sans-serif;
  --body:"Source Sans 3",system-ui,sans-serif;
  --mono:"JetBrains Mono",ui-monospace,Menlo,monospace;
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    --ground:#0D1315; --surface:#141D1F; --sunk:#0A1011;
    --ink:#E3EAE8; --ink-2:#A7B6B4; --muted:#7D8C8B; --line:#243033;
    --signal:#E8A33D;
    --now:#43BE8E; --route:#E8A33D; --layer:#7D93EC; --behav:#B989E0; --build:#DE7563;
  }}
}}
:root[data-theme="dark"] {{
  --ground:#0D1315; --surface:#141D1F; --sunk:#0A1011;
  --ink:#E3EAE8; --ink-2:#A7B6B4; --muted:#7D8C8B; --line:#243033;
  --signal:#E8A33D;
  --now:#43BE8E; --route:#E8A33D; --layer:#7D93EC; --behav:#B989E0; --build:#DE7563;
}}
*{{box-sizing:border-box}}
body{{background:var(--ground);color:var(--ink);font-family:var(--body);
  font-size:16px;line-height:1.5;margin:0;padding-block:40px;padding-left:20px;
  padding-right:20px;-webkit-font-smoothing:antialiased}}
.wrap{{max-width:1000px;margin:0 auto}}
h1{{font-family:var(--disp);font-weight:800;font-size:clamp(28px,5vw,44px);
  line-height:1.04;letter-spacing:-.022em;margin:0 0 14px;text-wrap:balance}}
.lede{{font-size:18px;color:var(--ink-2);max-width:62ch;margin:0 0 26px}}
.lede b{{color:var(--ink)}}
.den{{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 30px;padding:0;list-style:none}}
.den li{{font-family:var(--mono);font-size:12px;color:var(--ink-2);
  background:var(--sunk);border:1px solid var(--line);border-radius:3px;
  padding:6px 10px;font-variant-numeric:tabular-nums}}
.den b{{color:var(--ink);font-weight:600}}
.headline{{background:var(--surface);border:1px solid var(--line);
  border-left:3px solid var(--signal);border-radius:4px;padding:20px 22px;
  margin:0 0 40px;display:grid;grid-template-columns:repeat(3,1fr);gap:20px}}
.headline div{{min-width:0}}
.headline b{{font-family:var(--disp);font-weight:800;font-size:34px;
  display:block;line-height:1;letter-spacing:-.02em;
  font-variant-numeric:tabular-nums}}
.headline span{{font-size:13px;color:var(--muted);display:block;margin-top:6px}}
.headline .hi b{{color:var(--signal)}}
.hnote{{grid-column:1/-1;font-size:14px;color:var(--ink-2);margin:2px 0 0;
  padding-top:14px;border-top:1px solid var(--line)}}
.tier{{margin:0 0 34px}}
.tier-h{{display:flex;gap:14px;align-items:center;margin:0 0 6px}}
.ord{{font-family:var(--disp);font-weight:800;font-size:15px;flex:none;
  width:28px;height:28px;border-radius:50%;display:grid;place-items:center;
  color:var(--ground);background:var(--tc)}}
.tier h2{{font-family:var(--disp);font-weight:600;font-size:20px;margin:0;
  letter-spacing:-.01em}}
.tag{{margin:1px 0 0;font-size:13px;color:var(--tc);font-weight:600}}
.blurb{{margin:0 0 14px;font-size:14.5px;color:var(--ink-2);max-width:74ch}}
.t-now{{--tc:var(--now)}} .t-route{{--tc:var(--route)}}
.t-layer{{--tc:var(--layer)}} .t-behav{{--tc:var(--behav)}} .t-build{{--tc:var(--build)}}
.rows{{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:1px;
  background:var(--line);border:1px solid var(--line);border-radius:4px;overflow:hidden}}
.row{{background:var(--surface);display:grid;
  grid-template-columns:86px 132px 1fr;gap:18px;padding:14px 16px;align-items:start}}
.demand{{text-align:right;font-variant-numeric:tabular-nums}}
.demand b{{font-family:var(--disp);font-weight:800;font-size:19px;display:block;
  line-height:1.1}}
.demand .u{{font-size:11px;color:var(--muted);display:block}}
.demand .pct{{font-family:var(--mono);font-size:12px;color:var(--tc);
  font-weight:600;display:block;margin-top:3px}}
.supply{{display:flex;flex-direction:column;gap:4px}}
.arm{{display:flex;align-items:center;gap:6px}}
.al{{font-size:10px;color:var(--muted);width:34px;flex:none;letter-spacing:.04em;
  text-transform:uppercase}}
.bar{{display:flex;gap:1.5px;flex:none}}
.bar i{{width:5px;height:11px;border-radius:1px;background:var(--sunk);
  border:1px solid var(--line)}}
.bar i.on{{background:var(--tc);border-color:var(--tc)}}
.an{{font-family:var(--mono);font-size:10.5px;color:var(--ink-2);
  font-variant-numeric:tabular-nums}}
.corro,.single{{font-family:var(--mono);font-size:10px;letter-spacing:.03em;
  margin-top:2px}}
.corro{{color:var(--tc);font-weight:600}}
.single{{color:var(--muted)}}
.what{{min-width:0}}
.what h3{{font-family:var(--disp);font-weight:600;font-size:16px;margin:0 0 3px;
  letter-spacing:-.005em;text-wrap:balance}}
.q{{font-family:var(--mono);font-size:10px;color:var(--muted);
  border:1px solid var(--line);border-radius:2px;padding:1px 4px;
  vertical-align:2px;font-weight:400}}
.how{{margin:0 0 6px;font-size:14px;color:var(--ink-2)}}
.near{{margin:0;font-size:12px}}
.nl{{font-size:10px;text-transform:uppercase;letter-spacing:.06em;
  color:var(--muted);margin-right:5px}}
.near code{{font-family:var(--mono);font-size:12px;color:var(--ink);
  background:var(--sunk);border:1px solid var(--line);border-radius:2px;
  padding:1px 5px}}
footer{{margin-top:44px;padding-top:20px;border-top:1px solid var(--line);
  font-size:13px;color:var(--muted);max-width:78ch}}
footer p{{margin:0 0 9px}}
footer b{{color:var(--ink-2);font-weight:600}}
footer code{{font-family:var(--mono);font-size:12px}}
@media (max-width:640px){{
  .headline{{grid-template-columns:1fr 1fr}}
  .row{{grid-template-columns:1fr;gap:10px}}
  .demand{{text-align:left;display:flex;align-items:baseline;gap:7px}}
  .demand .u,.demand .pct{{display:inline;margin:0}}
}}
@media (prefers-reduced-motion:reduce){{*{{animation:none!important;transition:none!important}}}}
</style>

<div class="wrap">
<h1>What the examples do, and what users ask for</h1>
<p class="lede">Every capability the pipeline cannot currently place, ranked by
<b>evidence</b> — how many of the ten reference videos use it — against
<b>demand</b> — how many real users ask for it by name. Supply is shown per
reader, because two readers saw different things.</p>

<ul class="den">
  <li><b>{ref["videos"]}</b> reference videos · two independent readings</li>
  <li><b>{corpus["jobs"]:,}</b> requests · <b>{corpus["distinct_texts"]:,}</b> distinct · <b>{corpus["users"]:,}</b> users</li>
  <li>demand counted across <b>users</b>, not requests</li>
  <li><b>{len(rows)}</b> of <b>{len(rows)}</b> discovered families assessed</li>
</ul>

<div class="headline">
  <div><b>31</b><span>motion-graphics components ship</span></div>
  <div class="hi"><b>2</b><span>the agent can reach today</span></div>
  <div><b>29</b><span>rendered, tested, unreachable</span></div>
  <p class="hnote"><code>derive_card_type</code> returns only <code>StatCard</code>
  or <code>PullQuote</code>. The largest category below is not missing
  capability — it is capability with no route from a ruling to the component.</p>
</div>

{BODY}

<footer>
  <p><b>Supply</b> — the ten reference videos, read twice and merged without
  collapsing. Arm A: claude-sonnet-5 over silent frames, 173 names, richer on
  visual craft. Arm B: gemini-2.5-pro over the clip with audio, 136 names, the
  only arm that can hear. Neither is a superset; a family both arms found is
  marked <b>both arms</b> and is stronger evidence than either alone.</p>
  <p><b>Demand</b> — <code>video_jobs.vibe_input</code>, {corpus["jobs"]:,} non-empty
  requests, whitespace and case normalised, counted as distinct users. Matched
  by word-boundary patterns in several languages; every match is auditable in
  <code>demand_by_family.json</code>.</p>
  <p><b>What is not here</b> — three families the references use that are not a
  pipeline job at all: a phone held as a prop, a direct-to-camera gesture, an
  over-the-shoulder framing. Those live in the source footage.</p>
</footer>
</div>
'''
open("CAPABILITY_RANKING.html", "w").write(HTML)
print(f"wrote CAPABILITY_RANKING.html  {len(HTML):,} bytes, {len(rows)} families")
