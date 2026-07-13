import { requireAuth } from "../lib/auth.js";
import { getLead, patchLead } from "../lib/supa.js";
import { isStage } from "../lib/stage.js";

// POST /api/stage?id=<leadId>  body: {stage: "new"|"wip"|"reached_out"}
// Sets the lead's workflow stage. Moving to 'reached_out' stamps outreached_at
// (today's date); moving away from it clears the date.
export default async function handler(req, res) {
  if (!requireAuth(req, res)) return;
  const id = req.query.id;
  const stage = String((req.body && req.body.stage) || "");
  if (!isStage(stage)) {
    return res.status(400).json({ error: `invalid stage: ${stage}` });
  }
  try {
    const lead = await getLead(id);
    if (!lead) return res.status(404).json({ error: "lead not found" });
    const patch = { stage };
    if (stage === "reached_out") {
      patch.outreached_at = lead.outreached_at || new Date().toISOString();
    } else {
      patch.outreached_at = null;
    }
    const updated = await patchLead(id, patch);
    res.json({ lead: updated });
  } catch (e) {
    res.status(502).json({ error: String(e.message || e) });
  }
}
