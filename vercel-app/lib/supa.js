// Supabase access via PostgREST, using the SERVICE key (server-side only, bypasses
// RLS). The table has RLS on with no policies, so nothing else can touch it.

const URL = process.env.SUPABASE_URL;
const KEY = process.env.SUPABASE_SERVICE_KEY;

function headers(extra) {
  return { apikey: KEY, Authorization: `Bearer ${KEY}`, "Content-Type": "application/json", ...(extra || {}) };
}

export async function listLeads() {
  // Hide rejected leads from the board (soft-delete keeps them for learning).
  const q = "select=*&status=neq.rejected&order=fit_score.desc,last_seen.desc";
  const r = await fetch(`${URL}/rest/v1/jobops_leads?${q}`, { headers: headers() });
  if (!r.ok) throw new Error(`supabase list ${r.status}: ${await r.text()}`);
  return r.json();
}

export async function insertLead(row) {
  const r = await fetch(`${URL}/rest/v1/jobops_leads`, {
    method: "POST",
    headers: headers({ Prefer: "return=representation,resolution=merge-duplicates" }),
    body: JSON.stringify([row]),
  });
  if (!r.ok) throw new Error(`supabase insert ${r.status}: ${await r.text()}`);
  const a = await r.json();
  return a[0] || row;
}

export async function getLead(id) {
  const r = await fetch(`${URL}/rest/v1/jobops_leads?id=eq.${encodeURIComponent(id)}&select=*`, { headers: headers() });
  const a = await r.json();
  return a[0] || null;
}

export async function patchLead(id, patch) {
  patch.updated_at = new Date().toISOString();
  const r = await fetch(`${URL}/rest/v1/jobops_leads?id=eq.${encodeURIComponent(id)}`, {
    method: "PATCH", headers: headers({ Prefer: "return=representation" }), body: JSON.stringify(patch),
  });
  if (!r.ok) throw new Error(`supabase patch ${r.status}: ${await r.text()}`);
  const a = await r.json();
  return a[0] || null;
}
