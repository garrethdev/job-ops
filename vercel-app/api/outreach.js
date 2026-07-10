import { requireAuth } from "../lib/auth.js";
import { getLead, patchLead } from "../lib/supa.js";

// POST /api/outreach?id=<leadId> — toggle the "reached out" mark.
// Not set -> stamp outreached_at = now. Already set -> clear it.
export default async function handler(req, res) {
  if (!requireAuth(req, res)) return;
  const id = req.query.id;
  try {
    const lead = await getLead(id);
    if (!lead) return res.status(404).json({ error: "lead not found" });
    const outreached_at = lead.outreached_at ? null : new Date().toISOString();
    const updated = await patchLead(id, { outreached_at });
    res.json({ lead: updated });
  } catch (e) {
    res.status(502).json({ error: String(e.message || e) });
  }
}
