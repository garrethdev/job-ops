import { requireAuth } from "../lib/auth.js";
import { patchLead } from "../lib/supa.js";

// Soft-delete: mark rejected + hide from the board, but KEEP the row. Every
// reject is a negative example the scorer can learn from later.
export default async function handler(req, res) {
  if (!requireAuth(req, res)) return;
  const id = req.query.id;
  try {
    const updated = await patchLead(id, { status: "rejected" });
    if (!updated) return res.status(404).json({ error: "lead not found" });
    res.json({ ok: true });
  } catch (e) {
    res.status(502).json({ error: String(e.message || e) });
  }
}
