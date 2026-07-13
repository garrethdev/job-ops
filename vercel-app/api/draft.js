import { requireAuth } from "../lib/auth.js";
import { getLead, patchLead } from "../lib/supa.js";
import { createLabeledDraft } from "../lib/gmail.js";

// POST /api/draft?id=<leadId>  body: {subject, body, to?}
// Saves the (edited) email as a labeled Gmail draft and moves the lead to
// 'wip' (Working). The email content comes from the client — this endpoint no
// longer calls the LLM; use POST /api/craft to generate, edit, then save here.
export default async function handler(req, res) {
  if (!requireAuth(req, res)) return;
  const id = req.query.id;
  const b = req.body || {};
  const subject = String(b.subject || "").trim();
  const body = String(b.body || "").trim();
  if (!subject || !body) {
    return res.status(400).json({ error: "subject and body are required" });
  }
  try {
    const lead = await getLead(id);
    if (!lead) return res.status(404).json({ error: "lead not found" });

    const to = String(b.to || (lead.contact && lead.contact.email) || "").trim();
    const draft = await createLabeledDraft({ to, subject, body });

    // Prepared outreach -> Working. Co-write outreached_at:null so we can never
    // strand a (wip, outreached_at-set) pair if a stage change interleaved.
    // Notes are left untouched (no provenance clutter, no lost-update on notes).
    let updated = lead;
    if (lead.stage === "new") {
      updated = await patchLead(id, { stage: "wip", outreached_at: null });
    }

    res.json({ lead: updated, draft, to: to || "(no email on lead — fill in To: in Gmail)" });
  } catch (e) {
    res.status(502).json({ error: `draft: ${e.message || e}` });
  }
}
