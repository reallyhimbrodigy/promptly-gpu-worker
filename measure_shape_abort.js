'use strict';
// 🌀 S-DEGEN MEASUREMENT — shape-aware stream abort (DEGEN-LEVER-A).
//
// Two questions, two sources:
//   (1) burn-seconds per degen BEFORE vs AFTER the shape-abort deploy:
//       video_jobs.result.stage_timings.gemini_wasted_degen (shape aborts keep
//       aborted=True, so the same field counts them — no schema change).
//   (2) abort latency + per-fire savings + residual 16k aborts:
//       s3://thisismybucketagainwooo/divergences/{job_id}.jsonl —
//       action=shape_abort records carry {shape, period, run_len,
//       tokens_at_abort, rate_tok_s, est_saved_s}; action=gemini_degen_tail
//       records whose class still reads "streamed output crossed 16000 tok"
//       are the residual (document-structure loops the discriminant
//       deliberately does not chase).
//
// Usage:  node measure_shape_abort.js [DEPLOY_ISO]
//   DEPLOY_ISO = the shape-abort deploy timestamp (default below; the
//   orchestrator sets it at merge/deploy).
const { execSync } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

const DEPLOY = process.argv[2] || '2026-07-26T00:00:00Z'; // ← set at deploy
const SINCE = '2026-07-14T00:00:00Z';
const BUCKET = 'thisismybucketagainwooo';

const env = fs.readFileSync('/Users/zaclibman/content-studio/.env.local', 'utf8')
  .split('\n').reduce((a, l) => { const m = l.match(/^([A-Z_]+)=(.*)$/); if (m) a[m[1]] = m[2].replace(/^["']|["']$/g, ''); return a; }, {});
const { createClient } = require('/Users/zaclibman/content-studio/node_modules/@supabase/supabase-js');
const sb = createClient(env.SUPABASE_URL || env.NEXT_PUBLIC_SUPABASE_URL, env.SUPABASE_SERVICE_ROLE_KEY, { auth: { persistSession: false } });

const pctl = (v, q) => { const s = [...v].sort((a, z) => a - z); return s.length ? s[Math.min(s.length - 1, Math.floor(q * s.length))] : null; };

(async () => {
  // ── (1) gemini_wasted_degen distribution, split at DEPLOY ─────────────────
  const rows = [];
  for (let off = 0; ; off += 1000) {
    const { data, error } = await sb.from('video_jobs')
      .select('id,status,result,created_at')
      .gte('created_at', SINCE)
      .order('created_at', { ascending: false }).range(off, off + 999);
    if (error) { console.error('ERR', error.message); process.exit(1); }
    const d = data || [];
    for (const r of d) {
      const st = (r.result || {}).stage_timings || {};
      if (typeof st.gemini_call === 'number') {
        rows.push({ id: r.id, t: r.created_at, wasted: st.gemini_wasted_degen || 0 });
      }
    }
    if (d.length < 1000) break;
  }
  for (const [name, sel] of [['BEFORE deploy', rows.filter(r => r.t < DEPLOY)],
                             ['AFTER  deploy', rows.filter(r => r.t >= DEPLOY)]]) {
    const degen = sel.filter(r => r.wasted > 0).map(r => r.wasted);
    console.log(`${name}: jobs=${sel.length} degen-affected=${degen.length} ` +
      `(${sel.length ? (100 * degen.length / sel.length).toFixed(1) : 0}%)  ` +
      `wasted p50=${pctl(degen, 0.5)}s p90=${pctl(degen, 0.9)}s ` +
      `total=${degen.reduce((a, b) => a + b, 0).toFixed(0)}s`);
  }

  // ── (2) shape_abort divergence records + residual 16k aborts ─────────────
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'shapeabort-'));
  execSync(`aws s3 sync s3://${BUCKET}/divergences/ ${tmp}/ --quiet`, { stdio: 'inherit' });
  const shape = [], residual = [];
  for (const f of fs.readdirSync(tmp)) {
    const lines = fs.readFileSync(path.join(tmp, f), 'utf8').split('\n');
    for (const line of lines) {
      if (line.includes('"shape_abort"')) {
        try { shape.push({ job: f.replace('.jsonl', ''), ...JSON.parse(line) }); } catch (e) {}
      } else if (line.includes('"gemini_degen_tail"') && line.includes('streamed output crossed')) {
        try { const r = JSON.parse(line); residual.push({ job: f.replace('.jsonl', ''), t: r.t }); } catch (e) {}
      }
    }
  }
  console.log(`\nshape_abort fires: ${shape.length}`);
  const saved = shape.map(r => (r.original || {}).est_saved_s || 0);
  const toks = shape.map(r => (r.original || {}).tokens_at_abort || 0);
  const byShape = {};
  for (const r of shape) { const s = (r.original || {}).shape || '?'; byShape[s] = (byShape[s] || 0) + 1; }
  console.log(`  by shape: ${JSON.stringify(byShape)}`);
  console.log(`  tokens_at_abort p50=${pctl(toks, 0.5)} p90=${pctl(toks, 0.9)}`);
  console.log(`  est_saved_s p50=${pctl(saved, 0.5)} total=${saved.reduce((a, b) => a + b, 0).toFixed(0)}s`);
  console.log(`residual 16k aborts (post-deploy, doc-structure-loop class expected ~3%): ` +
    `${residual.filter(r => r.t && new Date(r.t * 1000).toISOString() >= DEPLOY).length} ` +
    `(all-time ${residual.length})`);
  fs.rmSync(tmp, { recursive: true, force: true });
})();
