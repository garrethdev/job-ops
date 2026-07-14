import { requireAuth } from "../lib/auth.js";
import { insertLead } from "../lib/supa.js";
import { buildManualRow } from "../lib/manual_lead.js";

// POST /api/add  body: {title, company, lane?, url?, location?, comp?, description?, notes?, fit?}
// Adds a lead entered by hand in the dashboard. id matches the pipeline so it
// dedupes against a scraped version of the same role.
export default async function handler(req, res) {
  if (!requireAuth(req, res)) return;
  let row;
  try {
    row = buildManualRow(req.body || {}, new Date().toISOString());
  } catch (e) {
    return res.status(400).json({ error: e.message || String(e) });
  }
  try {
    const lead = await insertLead(row);
    res.json({ lead });
  } catch (e) {
    res.status(502).json({ error: `add: ${e.message || e}` });
  }
}
