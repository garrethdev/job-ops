import { requireAuth } from "../lib/auth.js";
import { getLead, patchLead } from "../lib/supa.js";
import { findContact } from "../lib/apollo.js";

export default async function handler(req, res) {
  if (!requireAuth(req, res)) return;
  const id = req.query.id;
  try {
    const lead = await getLead(id);
    if (!lead) return res.status(404).json({ error: "lead not found" });
    // Already revealed -> don't spend another Apollo credit.
    if (lead.contact && lead.contact.linkedin) {
      return res.json({ lead, meta: { credits_used: 0, cached: true } });
    }
    const { contact, meta } = await findContact(lead.company, lead.lane);
    if (!contact) return res.json({ lead, meta });
    const patch = { contact };
    if (lead.status === "new") patch.status = "enriched";
    const updated = await patchLead(id, patch);
    res.json({ lead: updated, meta });
  } catch (e) {
    res.status(502).json({ error: `apollo: ${e.message || e}` });
  }
}
