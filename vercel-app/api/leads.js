import { requireAuth } from "../lib/auth.js";
import { listLeads } from "../lib/supa.js";

export default async function handler(req, res) {
  if (!requireAuth(req, res)) return;
  try {
    const leads = await listLeads();
    res.json({ leads, apollo_ready: !!process.env.APOLLO_API_KEY });
  } catch (e) {
    res.status(502).json({ error: String(e.message || e) });
  }
}
