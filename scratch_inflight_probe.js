// READ-ONLY: how many user jobs are actually in flight right now, and how old.
// Deploy-safety measurement for the quiet-window rule. No writes, no Modal spend.
const fs = require('fs');
const path = '/Users/zaclibman/content-studio/.env.local';
const env = {};
for (const line of fs.readFileSync(path, 'utf8').split('\n')) {
  const m = line.match(/^([A-Z_0-9]+)=(.*)$/);
  if (m) env[m[1]] = m[2].replace(/^["']|["']$/g, '').trim();
}
const { createClient } = require('/Users/zaclibman/content-studio/node_modules/@supabase/supabase-js');
const sb = createClient(env.SUPABASE_URL, env.SUPABASE_SERVICE_ROLE_KEY);

(async () => {
  const now = Date.now();
  const { data, error } = await sb
    .from('video_jobs')
    .select('id,status,created_at,updated_at')
    .in('status', ['processing', 'pending', 'queued'])
    .order('created_at', { ascending: false })
    .limit(200);
  if (error) { console.error('QUERY FAILED:', error.message); process.exit(1); }
  const byStatus = {};
  let recent = 0;
  for (const r of data) {
    byStatus[r.status] = (byStatus[r.status] || 0) + 1;
    const ageMin = (now - new Date(r.created_at).getTime()) / 60000;
    if (ageMin < 20) recent++;
  }
  console.log('in-flight rows by status:', JSON.stringify(byStatus));
  console.log('started within last 20 min (the orphan-risk cohort):', recent);
  const ages = data.slice(0, 8).map(r => Math.round((now - new Date(r.created_at).getTime()) / 60000));
  console.log('ages (min) of 8 newest in-flight:', ages.join(', ') || 'none');
})();
