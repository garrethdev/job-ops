import { requireAuth } from "../lib/auth.js";
import { patchLead } from "../lib/supa.js";

export default async function handler(req, res) {
  if (!requireAuth(req, res)) return;
  const id = req.query.id;
  const notes = String((req.body && req.body.notes) || "").slice(0, 4000);
  try {
    const updated = await patchLead(id, { notes });
    if (!updated) return res.status(404).json({ error: "lead not found" });
    res.json({ lead: updated });
  } catch (e) {
    res.status(502).json({ error: String(e.message || e) });
  }
}
