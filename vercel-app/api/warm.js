import { requireAuth } from "../lib/auth.js";
import { getLead, patchLead } from "../lib/supa.js";

// POST /api/warm?id=<leadId>  body: {warm: true|false}
// Toggle the "warm" star — a manual flag independent of stage. Drives the Warm tab.
export default async function handler(req, res) {
  if (!requireAuth(req, res)) return;
  const id = req.query.id;
  const warm = !!(req.body && req.body.warm);
  try {
    const lead = await getLead(id);
    if (!lead) return res.status(404).json({ error: "lead not found" });
    const updated = await patchLead(id, { warm });
    res.json({ lead: updated });
  } catch (e) {
    res.status(502).json({ error: String(e.message || e) });
  }
}
