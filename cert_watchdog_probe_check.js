// The "and it COUNTED" half of the watchdog probe [Rule 1].
//
// A kill with no telemetry is a container that vanished for unexplained reasons
// — strictly worse than no watchdog at all. This asserts the fired row exists
// and carries every field the exit is supposed to report.
//
//   node cert_watchdog_probe_check.js <probe_job_id>
require('dotenv').config({ path: process.env.ENV_FILE || '/Users/zaclibman/content-studio/.env.local' });
const { createClient } = require('@supabase/supabase-js');

const probeId = process.argv[2];
if (!probeId) { console.error('usage: node cert_watchdog_probe_check.js <probe_job_id>'); process.exit(2); }

const REQUIRED = ['waited_s', 'last_stage', 'terminal_write_attempted', 'held_core_s',
                  'recovered_lower', 'recovered_upper'];

(async () => {
  const sb = createClient(process.env.SUPABASE_URL, process.env.SUPABASE_SERVICE_ROLE_KEY);
  let row = null;
  for (let i = 0; i < 12 && !row; i++) {
    const { data } = await sb.from('analytics_events')
      .select('props, created_at').eq('event', 'post_upload_watchdog_fired')
      .order('created_at', { ascending: false }).limit(40);
    row = (data || []).find((e) => (e.props || {}).job_id === probeId) || null;
    if (!row) await new Promise((r) => setTimeout(r, 2500));
  }
  if (!row) {
    console.error(`WATCHDOG PROBE (count half): FAIL — no post_upload_watchdog_fired row for ${probeId}.`);
    console.error('  It killed the container and wrote nothing. That is worse than not firing.');
    process.exit(1);
  }
  const p = row.props || {};
  console.log('  fired row:', JSON.stringify(p, null, 2));
  const missing = REQUIRED.filter((k) => !(k in p));
  if (missing.length) {
    console.error(`WATCHDOG PROBE (count half): FAIL — telemetry missing ${JSON.stringify(missing)}`);
    process.exit(1);
  }
  // The gate already removed the bare terminal write once; assert it stayed removed.
  if (p.terminal_write_attempted !== false) {
    console.error('WATCHDOG PROBE (count half): FAIL — it attempted a bare terminal write, '
      + 'which is the thin-envelope defect the deploy gate caught and removed.');
    process.exit(1);
  }
  if (!(Number(p.waited_s) > 0)) {
    console.error(`WATCHDOG PROBE (count half): FAIL — waited_s=${p.waited_s} is not a real elapsed time.`);
    process.exit(1);
  }
  console.log(`\nWATCHDOG PROBE (count half): PASS — waited=${p.waited_s}s stage=${p.last_stage} `
    + `held=${p.held_core_s} core-s  recovered_vs_repair=${p.recovered_upper} core-s`);
})();
